from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from pydantic import BaseModel, Field

from app.services.acs_chat import acs_chat_adapter
from app.services.chat_store import (
    add_message_record,
    create_session_record,
    filter_user_sessions,
    find_existing_session,
    find_po,
    find_user,
    list_purchase_orders,
    list_suppliers,
    list_users,
    load_messages,
    load_sessions,
    load_user_map,
    now_iso,
    paginate,
    save_messages,
    save_sessions,
    save_user_map,
)
from app.services.realtime import realtime_gateway
from app.utils.auth import decode_token, extract_bearer_token

router = APIRouter(prefix="/chat", tags=["Chat"])

ALLOWED_CHAT_TYPES = {"PS_SUPPLIER", "PS_PS"}


class ChatSessionCreateRequest(BaseModel):
    chat_type: Literal["PS_SUPPLIER", "PS_PS"]
    participant_ids: List[str] = Field(default_factory=list)
    po_id: Optional[str] = None
    title: Optional[str] = None


class ChatSearchOrCreateRequest(ChatSessionCreateRequest):
    pass


class ChatMessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MarkReadRequest(BaseModel):
    last_read_message_id: Optional[str] = None


def _current_user(authorization: Optional[str]) -> Dict:
    try:
        token = extract_bearer_token(authorization)
        payload = decode_token(token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user id")

    user = find_user(user_id)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "role": user.get("role"),
    }


def _build_participants(participant_ids: List[str]) -> List[Dict]:
    participants = []

    for participant_id in sorted(set(participant_ids)):
        user = find_user(participant_id)

        if not user:
            raise HTTPException(status_code=404, detail=f"Participant not found: {participant_id}")

        participants.append(
            {
                "user_id": user.get("id"),
                "name": user.get("name"),
                "role": user.get("role"),
            }
        )

    return participants


def _participant_ids(session: Dict) -> List[str]:
    return [participant.get("user_id") for participant in session.get("participants", [])]


def _assert_session_access(session: Dict, user_id: str) -> None:
    if user_id not in _participant_ids(session):
        raise HTTPException(status_code=403, detail="Forbidden to access this chat session")


def _validate_chat_creation(
    request: ChatSessionCreateRequest,
    current_user: Dict,
    participants: List[Dict],
) -> Optional[Dict]:
    if request.chat_type not in ALLOWED_CHAT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported chat_type")

    if len(participants) != 2:
        raise HTTPException(status_code=400, detail="Only one-to-one chat is supported")

    po = None

    if request.chat_type == "PS_SUPPLIER":
        if not request.po_id:
            raise HTTPException(status_code=400, detail="po_id is required for PS_SUPPLIER chat")

        roles = {participant.get("role") for participant in participants}
        if roles != {"PROCUREMENT_SPECIALIST", "SUPPLIER"}:
            raise HTTPException(status_code=400, detail="PS_SUPPLIER requires one PS and one Supplier")

        po = find_po(request.po_id)
        if not po:
            raise HTTPException(status_code=404, detail="PO not found")

        supplier_id = po.get("supplier_id")
        ps_user = next((p for p in participants if p.get("role") == "PROCUREMENT_SPECIALIST"), None)
        supplier_user = next((p for p in participants if p.get("role") == "SUPPLIER"), None)

        if not ps_user or not supplier_user:
            raise HTTPException(status_code=400, detail="Invalid participants")

        if ps_user.get("user_id") != po.get("procurement_specialist_id"):
            raise HTTPException(status_code=403, detail="PS is not assigned to the PO")

        if supplier_user.get("user_id") != supplier_id:
            raise HTTPException(status_code=403, detail="Supplier is not assigned to the PO")

    if request.chat_type == "PS_PS":
        if any(participant.get("role") != "PROCUREMENT_SPECIALIST" for participant in participants):
            raise HTTPException(status_code=400, detail="PS_PS requires PS-only participants")

        if request.po_id:
            po = find_po(request.po_id)
            if not po:
                raise HTTPException(status_code=404, detail="PO not found")

            related_ps_ids = {po.get("procurement_specialist_id")}
            if po.get("delegated_user_id"):
                related_ps_ids.add(po.get("delegated_user_id"))

            candidate_ids = {participant.get("user_id") for participant in participants}
            if not candidate_ids.intersection(related_ps_ids):
                raise HTTPException(
                    status_code=403,
                    detail="PO-linked PS_PS chat requires at least one PO-related participant",
                )

    if current_user.get("id") not in {participant.get("user_id") for participant in participants}:
        raise HTTPException(status_code=403, detail="Current user must be a chat participant")

    return po


def _to_session_response(session: Dict, current_user_id: str) -> Dict:
    response = dict(session)
    response["unread_count"] = session.get("unread_count_by_user", {}).get(current_user_id, 0)
    return response


def _suggest_users(current_user: Dict, query: str, chat_type: Optional[str]) -> List[Dict]:
    users = list_users()
    suppliers = list_suppliers()
    q = query.lower()

    candidates: List[Dict] = []

    if current_user.get("role") == "SUPPLIER":
        candidates = [u for u in users if u.get("role") == "PROCUREMENT_SPECIALIST"]
    else:
        if chat_type == "PS_SUPPLIER":
            candidates = suppliers
        elif chat_type == "PS_PS":
            candidates = [u for u in users if u.get("role") == "PROCUREMENT_SPECIALIST"]
        else:
            candidates = suppliers + [u for u in users if u.get("role") == "PROCUREMENT_SPECIALIST"]

    out = []
    for candidate in candidates:
        if candidate.get("id") == current_user.get("id"):
            continue

        haystacks = [candidate.get("id", ""), candidate.get("name", ""), candidate.get("email", "")]
        if q and not any(q in str(value).lower() for value in haystacks):
            continue

        out.append(
            {
                "user_id": candidate.get("id"),
                "name": candidate.get("name"),
                "role": candidate.get("role"),
            }
        )

    return out[:10]


def _suggest_pos(current_user: Dict, query: str) -> List[Dict]:
    pos = list_purchase_orders()
    q = query.lower()

    visible = []

    for po in pos:
        if current_user.get("role") == "SUPPLIER":
            if po.get("supplier_id") != current_user.get("id"):
                continue
        elif current_user.get("role") == "PROCUREMENT_SPECIALIST":
            if po.get("procurement_specialist_id") != current_user.get("id"):
                continue

        if q and q not in po.get("po_number", "").lower() and q not in po.get("supplier_name", "").lower():
            continue

        visible.append(
            {
                "po_id": po.get("id"),
                "po_number": po.get("po_number"),
                "supplier_id": po.get("supplier_id"),
                "procurement_specialist_id": po.get("procurement_specialist_id"),
            }
        )

    return visible[:10]


def _find_session_or_404(session_id: str) -> Dict:
    sessions = load_sessions()
    session = next((item for item in sessions if item.get("id") == session_id), None)

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    return session


@router.post("/sessions")
def create_chat_session(
    request: ChatSessionCreateRequest,
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)

    participant_ids = [current_user.get("id")] + request.participant_ids
    participant_ids = sorted(set(participant_ids))

    participants = _build_participants(participant_ids)
    po = _validate_chat_creation(request, current_user, participants)

    sessions = load_sessions()
    existing = find_existing_session(sessions, request.chat_type, participant_ids, request.po_id)
    if existing:
        return {
            "created": False,
            "session": _to_session_response(existing, current_user.get("id")),
        }

    user_map = load_user_map()
    participant_acs_ids = []

    for participant in participants:
        acs_user = acs_chat_adapter.ensure_user(participant.get("user_id"), user_map)
        user_map[participant.get("user_id")] = {
            "internal_user_id": participant.get("user_id"),
            "acs_user_id": acs_user.get("acs_user_id"),
            "acs_access_token": acs_user.get("acs_access_token"),
            "token_expires_on": acs_user.get("token_expires_on"),
        }
        participant_acs_ids.append(acs_user.get("acs_user_id"))

    save_user_map(user_map)

    po_number = po.get("po_number") if po else None
    topic = request.title or f"{request.chat_type}:{po_number or 'GENERAL'}"
    thread_result = acs_chat_adapter.create_thread(topic=topic, participant_acs_ids=participant_acs_ids)

    session = create_session_record(
        chat_type=request.chat_type,
        po_id=request.po_id,
        po_number=po_number,
        participants=participants,
        created_by=current_user.get("id"),
        acs_thread_id=thread_result.get("thread_id"),
        provider=thread_result.get("provider"),
    )

    sessions.append(session)
    save_sessions(sessions)

    return {
        "created": True,
        "session": _to_session_response(session, current_user.get("id")),
    }


@router.post("/sessions/search-or-create")
def search_or_create_chat_session(
    request: ChatSearchOrCreateRequest,
    authorization: Optional[str] = Header(default=None),
):
    return create_chat_session(request=request, authorization=authorization)


@router.get("/sessions")
def list_chat_sessions(
    page: int = 1,
    page_size: int = 20,
    chat_type: Optional[str] = None,
    po_id: Optional[str] = None,
    search: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)

    sessions = load_sessions()

    filtered = filter_user_sessions(
        sessions=sessions,
        user_id=current_user.get("id"),
        chat_type=chat_type,
        po_id=po_id,
        search=search,
    )

    total, items = paginate(filtered, page, page_size)

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "data": [_to_session_response(item, current_user.get("id")) for item in items],
    }


@router.get("/sessions/search")
def search_chat_sessions(
    q: str = Query(default=""),
    chat_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)

    sessions = load_sessions()

    filtered = filter_user_sessions(
        sessions=sessions,
        user_id=current_user.get("id"),
        chat_type=chat_type,
        search=q,
    )

    total, items = paginate(filtered, page, page_size)

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "sessions": [_to_session_response(item, current_user.get("id")) for item in items],
        "suggestions": {
            "users": _suggest_users(current_user, q, chat_type),
            "purchase_orders": _suggest_pos(current_user, q),
        },
    }


@router.get("/sessions/{session_id}/messages")
def get_chat_messages(
    session_id: str,
    page: int = 1,
    page_size: int = 50,
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)

    session = _find_session_or_404(session_id)
    _assert_session_access(session, current_user.get("id"))

    messages = [m for m in load_messages() if m.get("session_id") == session_id]
    messages.sort(key=lambda item: item.get("created_at") or "")

    total, items = paginate(messages, page, page_size)

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "data": items,
    }


@router.post("/sessions/{session_id}/messages")
async def send_chat_message(
    session_id: str,
    request: ChatMessageCreateRequest,
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)

    sessions = load_sessions()
    session_index = next((index for index, item in enumerate(sessions) if item.get("id") == session_id), None)

    if session_index is None:
        raise HTTPException(status_code=404, detail="Chat session not found")

    session = sessions[session_index]
    _assert_session_access(session, current_user.get("id"))

    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    acs_result = acs_chat_adapter.send_message(
        thread_id=session.get("acs_thread_id"),
        content=content,
        sender_display_name=current_user.get("name") or current_user.get("id"),
    )

    messages = load_messages()
    message_entry = add_message_record(
        messages=messages,
        session_id=session_id,
        acs_message_id=acs_result.get("message_id"),
        sender_id=current_user.get("id"),
        sender_name=current_user.get("name") or current_user.get("id"),
        content=content,
        provider=acs_result.get("provider"),
    )
    save_messages(messages)

    unread_count = dict(session.get("unread_count_by_user") or {})
    recipient_ids = []

    for participant_id in _participant_ids(session):
        if participant_id == current_user.get("id"):
            unread_count[participant_id] = 0
            continue

        unread_count[participant_id] = int(unread_count.get(participant_id, 0)) + 1
        recipient_ids.append(participant_id)

    session["unread_count_by_user"] = unread_count
    session["last_message_at"] = message_entry.get("created_at")
    session["last_message_preview"] = content[:200]
    session["updated_at"] = message_entry.get("created_at")
    sessions[session_index] = session
    save_sessions(sessions)

    notification = {
        "type": "CHAT_NEW_MESSAGE",
        "session_id": session_id,
        "chat_type": session.get("chat_type"),
        "po_id": session.get("po_id"),
        "sender": {
            "id": current_user.get("id"),
            "name": current_user.get("name"),
        },
        "preview": content[:200],
        "timestamp": message_entry.get("created_at"),
    }

    await realtime_gateway.notify_users(recipient_ids, notification)

    return {
        "message": message_entry,
        "session": _to_session_response(session, current_user.get("id")),
    }


@router.post("/sessions/{session_id}/read")
def mark_session_read(
    session_id: str,
    request: MarkReadRequest,
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)

    sessions = load_sessions()
    session_index = next((index for index, item in enumerate(sessions) if item.get("id") == session_id), None)

    if session_index is None:
        raise HTTPException(status_code=404, detail="Chat session not found")

    session = sessions[session_index]
    _assert_session_access(session, current_user.get("id"))

    unread_count = dict(session.get("unread_count_by_user") or {})
    unread_count[current_user.get("id")] = 0
    session["unread_count_by_user"] = unread_count
    session["updated_at"] = now_iso()
    sessions[session_index] = session
    save_sessions(sessions)

    return {
        "message": "Read state updated",
        "session": _to_session_response(session, current_user.get("id")),
        "last_read_message_id": request.last_read_message_id,
    }


@router.get("/realtime/bootstrap")
def get_realtime_bootstrap(authorization: Optional[str] = Header(default=None)):
    current_user = _current_user(authorization)

    return {
        "transport_preference": "azure_signalr",
        "signalr": {
            "enabled": realtime_gateway.signalr_enabled,
            "endpoint": realtime_gateway.signalr_endpoint,
            "hub": realtime_gateway.signalr_hub,
        },
        "websocket_fallback": {
            "enabled": True,
            "url": "/chat/realtime/ws?access_token=<JWT>",
        },
        "event_grid": {
            "ingestion_endpoint": "/chat/realtime/events",
            "supported_event_types": [
                "Microsoft.EventGrid.SubscriptionValidationEvent",
                "Microsoft.Communication.ChatMessageReceivedInThread",
            ],
        },
        "current_user": {
            "id": current_user.get("id"),
            "role": current_user.get("role"),
        },
    }


@router.websocket("/realtime/ws")
async def chat_realtime_ws(websocket: WebSocket, access_token: str = Query(default="")):
    if not access_token:
        await websocket.close(code=1008)
        return

    try:
        payload = decode_token(access_token)
    except JWTError:
        await websocket.close(code=1008)
        return

    user_id = payload.get("sub")

    if not user_id:
        await websocket.close(code=1008)
        return

    await realtime_gateway.connect(user_id, websocket)

    try:
        await websocket.send_json({"type": "CONNECTED", "user_id": user_id})

        while True:
            message = await websocket.receive_text()

            if message.strip().lower() == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        realtime_gateway.disconnect(user_id, websocket)
    except Exception:
        realtime_gateway.disconnect(user_id, websocket)


@router.post("/realtime/events")
async def ingest_event_grid_events(events: List[Dict]):
    for event in events:
        event_type = event.get("eventType")

        if event_type == "Microsoft.EventGrid.SubscriptionValidationEvent":
            data = event.get("data") or {}
            return {"validationResponse": data.get("validationCode")}

        if event_type != "Microsoft.Communication.ChatMessageReceivedInThread":
            continue

        data = event.get("data") or {}
        thread_id = data.get("threadId")

        if not thread_id:
            continue

        sessions = load_sessions()
        session = next((item for item in sessions if item.get("acs_thread_id") == thread_id), None)

        if not session:
            continue

        participants = _participant_ids(session)
        payload = {
            "type": "CHAT_EVENTGRID_MESSAGE",
            "session_id": session.get("id"),
            "chat_type": session.get("chat_type"),
            "po_id": session.get("po_id"),
            "preview": (data.get("message") or "")[:200],
            "timestamp": data.get("createdOn"),
        }

        await realtime_gateway.notify_users(participants, payload)

    return {"status": "accepted", "processed": len(events)}
