import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field

from app.integrations.chat_service.database.db import chat_collection
from app.integrations.chat_service.dto.procurement_specialist import AddChatParticipant, StartChatThread
from app.integrations.chat_service.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


class MarkChatReadRequest(BaseModel):
    email: EmailStr
    thread_id: str = Field(min_length=1)
    last_read_message_id: str = Field(min_length=1)


def _extract_acs_user_id(user) -> str:
    if hasattr(user, "raw_id") and user.raw_id:
        return user.raw_id
    if hasattr(user, "id") and user.id:
        return user.id
    return str(user)


def _build_bootstrap_item(chat: dict, current_email: str, chat_service: ChatService) -> Optional[dict]:
    participant_details = chat.get("participant_details", {})
    current_details = participant_details.get(current_email)

    if not current_details or not current_details.get("acs_user_id"):
        return None

    participants = chat.get("participants", []) or []
    counterpart_email = next((participant for participant in participants if participant != current_email), None)
    counterpart_details = participant_details.get(counterpart_email or "", {})

    return {
        "threadId": chat.get("thread_id"),
        "token": chat_service.create_token_from_user_id(current_details["acs_user_id"]),
        "acsUserId": current_details["acs_user_id"],
        "endpoint": chat_service.endpoint_url,
        "poNumber": chat.get("po_number"),
        "participants": participants,
        "lastReadMessageId": (chat.get("last_read_message_ids") or {}).get(current_email),
        "currentParticipant": {
            "email": current_email,
            "name": current_details.get("name"),
            "acsUserId": current_details.get("acs_user_id"),
        },
        "counterpart": {
            "email": counterpart_email,
            "name": counterpart_details.get("name"),
            "acsUserId": counterpart_details.get("acs_user_id"),
        },
    }


@router.post("/", status_code=201, description="Start a chat thread")
async def start_chat_thread(payload: StartChatThread):
    try:
        chat_service = ChatService()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Azure Communication configuration error: {exc}",
        ) from exc

    participant_key = sorted([payload.from_email, payload.to_email])

    existing_chat = chat_collection.find_one(
        {
            "participants": {"$all": participant_key},
            "po_number": payload.po_number,
        }
    )

    if existing_chat:
        participant_details = existing_chat.get("participant_details", {})
        requester_details = participant_details.get(payload.from_email)

        if not requester_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat exists but the current participant is not linked to it",
            )

        acs_user_id = requester_details["acs_user_id"]

        token = chat_service.create_token_from_user_id(
            acs_user_id
        )

        return {
            "status": "Success",
            "created": False,
            "data": {
                "threadId": existing_chat["thread_id"],
                "token": token,
                "acsUserId": acs_user_id,
                "endpoint": chat_service.endpoint_url,
                "poNumber": existing_chat.get("po_number"),
                "participants": existing_chat.get("participants", []),
                "lastReadMessageId": (existing_chat.get("last_read_message_ids") or {}).get(payload.from_email),
            },
        }

    logging.info("Creating a new ACS-backed chat thread for PO %s", payload.po_number)

    try:
        starter_user = chat_service.identity_client.create_user()
        remote_user = chat_service.identity_client.create_user()

        starter_token = chat_service.create_token(starter_user).token
        remote_token = chat_service.create_token(remote_user).token
    except Exception as exc:
        logging.exception("ACS user/token creation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Failed to create Azure Communication user/token. "
                f"Check ACS endpoint/access key. Provider error: {exc}"
            ),
        ) from exc

    starter_acs_user_id = _extract_acs_user_id(starter_user)
    remote_acs_user_id = _extract_acs_user_id(remote_user)

    topic = payload.po_number or "Test Thread"

    try:
        chat_thread_client, _ = chat_service.create_chat_thread(
            starter_acs_user_id=starter_acs_user_id,
            topic=topic,
            starter_display_name=payload.from_name,
            participant_acs_ids=[remote_acs_user_id],
            participant_display_names={remote_acs_user_id: payload.to_name},
        )
    except Exception as exc:
        logging.exception("ACS chat thread creation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create Azure Communication chat thread. Provider error: {exc}",
        ) from exc

    new_chat = {
        "id": str(uuid.uuid4()),
        "thread_id": chat_thread_client.thread_id,
        "po_number": payload.po_number,
        "participants": [payload.from_email, payload.to_email],
        "last_read_message_ids": {
            payload.from_email: None,
            payload.to_email: None,
        },
        "participant_details": {
            payload.from_email: {
                "name": payload.from_name,
                "acs_user_id": starter_acs_user_id,
            },
            payload.to_email: {
                "name": payload.to_name,
                "acs_user_id": remote_acs_user_id,
            },
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    chat_collection.insert_one(new_chat)

    return {
        "status": "Success",
        "created": True,
        "data": {
            "threadId": chat_thread_client.thread_id,
            "token": starter_token,
            "acsUserId": starter_acs_user_id,
            "endpoint": chat_service.endpoint_url,
            "poNumber": payload.po_number,
            "participants": [payload.from_email, payload.to_email],
            "lastReadMessageId": None,
        },
    }


@router.post("/read", status_code=200, description="Mark an ACS chat thread as read")
async def mark_chat_read(payload: MarkChatReadRequest):
    chats = chat_collection.find_many()
    chat = next((item for item in chats if item.get("thread_id") == payload.thread_id), None)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat thread not found",
        )

    participants = chat.get("participants", []) or []
    if payload.email not in participants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current participant is not part of this thread",
        )

    last_read_message_ids = dict(chat.get("last_read_message_ids") or {})
    last_read_message_ids[payload.email] = payload.last_read_message_id
    chat["last_read_message_ids"] = last_read_message_ids
    chat["updated_at"] = datetime.now(timezone.utc).isoformat()

    updated_chat = chat_collection.update_one(
        {"thread_id": payload.thread_id},
        {
            "last_read_message_ids": last_read_message_ids,
            "updated_at": chat["updated_at"],
        },
    )

    if not updated_chat:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist read state",
        )

    return {
        "status": "Success",
        "message": "Read state updated",
        "data": {
            "threadId": payload.thread_id,
            "email": payload.email,
            "lastReadMessageId": payload.last_read_message_id,
        },
    }


@router.get("/bootstrap", status_code=200, description="List all chat threads for a participant")
async def bootstrap_chats(email: EmailStr = Query(..., description="Current participant email")):
    chat_service = ChatService()
    chats = chat_collection.find_many()

    bootstrap_items = []
    for chat in chats:
        participants = chat.get("participants", []) or []
        if email not in participants:
            continue

        bootstrap_item = _build_bootstrap_item(chat, str(email), chat_service)
        if bootstrap_item:
            bootstrap_items.append(bootstrap_item)

    return {
        "status": "Success",
        "data": bootstrap_items,
    }


@router.patch("/add", status_code=200, description="Add a participant to a chat")
async def add_participant(payload: AddChatParticipant):

    existing_chat = chat_collection.find_one({
        "participants": {
            "$all": [payload.from_email, payload.email]
        }
    })

    if not existing_chat:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat thread does not exists in the database"
        )

    thread_id = existing_chat["thread_id"]
    participant_details = existing_chat.get("participant_details", {})
    starter_email = existing_chat.get("participants", [payload.from_email])[0]
    acs_user_id = participant_details.get(
        payload.from_email,
        participant_details.get(starter_email, {})
    ).get("acs_user_id")

    token = ChatService().create_token_from_user_id(
        acs_user_id
    )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat token not available for this thread",
        )

    ChatService().add_participant(
        thread_id,
        token,
        payload.email,
        payload.name
    )

    return {
        "status": "Success",
        "message": "Participant added successfully",
        "data": {
            "threadId": thread_id,
            "token": token
        }
    }
