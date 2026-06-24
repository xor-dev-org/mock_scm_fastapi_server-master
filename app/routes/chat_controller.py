import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.database.db import get_db
from auth_service.database.model import Chat
from auth_service.dto.procurement_specialist import AddChatParticipant, StartChatThread
from auth_service.services.chat_service import ChatService
from auth_service.services.websocket_service import WebSocketConnectionManager

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/", status_code=201, description="Start a chat thread")
async def start_chat_thread(payload: StartChatThread, db: AsyncSession = Depends(get_db)):
    query = select(Chat).where(Chat.participants.contains(payload.from_email, payload.to_email))
    result = await db.execute(query)
    chats = list(result.scalars().all())

    thread_id, token = None, None

    if len(chats) == 0:
        logging.info(f"Creating a new thread")
        chat_thread_client, token = ChatService().create_chat_thread(payload.from_email, "Test Thread", payload.from_name)
        new_chat = Chat(
            thread_id=chat_thread_client.thread_id,
            participants=[payload.from_email, payload.to_email], 
            token=token
        )

        db.add(new_chat)
        await db.commit()
        await db.refresh(new_chat)

        thread_id = chat_thread_client.thread_id
    else:
        logging.info(f"Using the previously created thread ID")
        thread_id = chats[0].thread_id
        token = chats[0].token

    logging.info(f"Sending thread_id over websocket to the remote participant.")

    remote_participant = payload.to_email
    ws_payload = {
        "message": "chat.start",
        "thread_id": thread_id,
        "participants": [payload.from_email],
        "token": token
    }

    WebSocketConnectionManager().send_private_message(ws_payload, remote_participant)

    return {"status": "Success", "message": "Chat session created successfully"}

@router.patch("/add", status_code=200, description="Add a participant to a chat")
async def add_participant(payload: AddChatParticipant, db: AsyncSession = Depends(get_db)):
    query = select(Chat).where(Chat.participants.contains(payload.from_email, payload.email))
    result = await db.execute(query)
    chats = list(result.scalars().all())

    if len(chats) == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Chat thread does not exists in the database"
        )
    
    thread_id = chats[0].thread_id
    token = chats[0].token
    ChatService().add_participant(thread_id, token, payload.email, payload.name)

    return {"status": "Success", "message": "Participant added successfully", "data": {"threadId": thread_id, "token": token}}