import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.database.models import Chat, ChatUserMapCollection
from app.dto.chat_dto import AddChatParticipant, StartChatThread
from app.services.chat_service import ChatService
from app.services.websocket_service import WebSocketConnectionManager

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_chat_service() -> ChatService:
    try:
        return ChatService()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


async def _get_or_create_acs_identity(db: AsyncSession, chat_service: ChatService, internal_user_id: str) -> str:
    """Return the persisted ACS identity for an app user, creating one on first use.

    Each app user must reuse the same ACS identity across every thread; treating
    their email as if it were already a raw ACS id (the previous behavior) fails
    because ACS only issues tokens for identities it created via create_user().
    """
    result = await db.execute(
        select(ChatUserMapCollection).where(ChatUserMapCollection.internal_user_id == internal_user_id)
    )
    mapping = result.scalar_one_or_none()
    if mapping:
        return mapping.data["acs_user_id"]

    acs_user = chat_service.create_user()
    mapping = ChatUserMapCollection(
        id=str(uuid.uuid4()),
        internal_user_id=internal_user_id,
        data={"acs_user_id": acs_user.properties["id"]},
    )
    db.add(mapping)
    await db.commit()
    return mapping.data["acs_user_id"]


@router.post("/", status_code=201, description="Start a chat thread")
async def start_chat_thread(payload: StartChatThread, db: AsyncSession = Depends(get_db)):
    chat_service = _get_chat_service()

    participants = [payload.from_email, payload.to_email]
    query = select(Chat).where(Chat.participants.contains(participants))
    result = await db.execute(query)
    chat = result.scalars().first()

    caller_acs_id = await _get_or_create_acs_identity(db, chat_service, payload.from_email)

    if chat is None:
        logging.info("Creating a new thread")
        chat_thread_client, caller_token = chat_service.create_chat_thread(
            caller_acs_id, "Test Thread", payload.from_name
        )

        chat = Chat(
            thread_id=chat_thread_client.thread_id,
            # participants[0] is the creator - the only confirmed ACS thread
            # member until the other party is added (see the else branch below).
            participants=participants,
            token=caller_token,
        )
        db.add(chat)
        await db.commit()
        await db.refresh(chat)
    else:
        logging.info("Using the previously created thread ID")
        creator_email = chat.participants[0]

        if payload.from_email == creator_email:
            # Caller is the original creator and is already an ACS thread
            # member; mint a fresh token rather than trusting the one stored
            # at creation time, since it may have expired.
            caller_token = chat_service.mint_token(caller_acs_id)
        else:
            # Caller is the other party and may not have joined the ACS thread
            # yet (that normally happens via /add) - ensure membership here
            # too, since either side may call this endpoint first.
            creator_acs_id = await _get_or_create_acs_identity(db, chat_service, creator_email)
            inviter_token = chat_service.mint_token(creator_acs_id)
            caller_token = chat_service.add_participant(
                chat.thread_id, inviter_token, caller_acs_id, payload.from_name
            )

    thread_id = chat.thread_id

    logging.info("Notifying the remote participant over websocket")
    ws_payload = {
        "message": "chat.start",
        "thread_id": thread_id,
        "from_email": payload.from_email,
        "from_name": payload.from_name,
    }
    participant_notified = await WebSocketConnectionManager().send_private_message(ws_payload, payload.to_email)
    if not participant_notified:
        logging.warning(f"{payload.to_email} is not currently connected; they can still call /chat/add once online")

    return {
        "status": "Success",
        "message": "Chat session created successfully",
        "data": {"threadId": thread_id, "token": caller_token, "participantNotified": participant_notified},
    }

@router.patch("/add", status_code=200, description="Add a participant to a chat")
async def add_participant(payload: AddChatParticipant, db: AsyncSession = Depends(get_db)):
    chat_service = _get_chat_service()

    query = select(Chat).where(Chat.participants.contains([payload.from_email, payload.email]))
    result = await db.execute(query)
    chat = result.scalars().first()

    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat thread does not exist")

    # The inviter must already be a thread member; mint a fresh token rather than
    # trusting the one stored at thread-creation time, since it may have expired.
    creator_email = chat.participants[0]
    creator_acs_id = await _get_or_create_acs_identity(db, chat_service, creator_email)
    inviter_token = chat_service.mint_token(creator_acs_id)

    new_participant_acs_id = await _get_or_create_acs_identity(db, chat_service, payload.email)
    participant_token = chat_service.add_participant(
        chat.thread_id, inviter_token, new_participant_acs_id, payload.name
    )

    return {
        "status": "Success",
        "message": "Participant added successfully",
        "data": {"threadId": chat.thread_id, "token": participant_token},
    }