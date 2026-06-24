import logging

from fastapi import APIRouter, HTTPException, status

from app.integrations.chat_service.database.db import chat_collection
from app.integrations.chat_service.dto.procurement_specialist import AddChatParticipant, StartChatThread
from app.integrations.chat_service.services.chat_service import ChatService
from app.integrations.chat_service.services.websocket_service import WebSocketConnectionManager

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", status_code=201, description="Start a chat thread")
async def start_chat_thread(payload: StartChatThread):

    existing_chat = chat_collection.find_one({
        "participants": {
            "$all": [payload.from_email, payload.to_email]
        }
    })

    thread_id, token = None, None

    if not existing_chat:
        logging.info("Creating a new thread")

        chat_thread_client, token = ChatService().create_chat_thread(
            payload.from_email,
            "Test Thread",
            payload.from_name
        )

        new_chat = {
            "thread_id": chat_thread_client.thread_id,
            "participants": [payload.from_email, payload.to_email],
            "token": token
        }

        chat_collection.insert_one(new_chat)

        thread_id = chat_thread_client.thread_id

    else:
        logging.info("Using the previously created thread ID")
        thread_id = existing_chat["thread_id"]
        token = existing_chat["token"]

    logging.info("Sending thread_id over websocket to the remote participant.")

    remote_participant = payload.to_email

    ws_payload = {
        "message": "chat.start",
        "thread_id": thread_id,
        "participants": [payload.from_email],
        "token": token
    }

    WebSocketConnectionManager().send_private_message(
        ws_payload,
        remote_participant
    )

    return {
        "status": "Success",
        "message": "Chat session created successfully"
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
    token = existing_chat["token"]

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