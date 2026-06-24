import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.integrations.chat_service.database.db import chat_collection
from app.integrations.chat_service.dto.procurement_specialist import AddChatParticipant, StartChatThread
from app.integrations.chat_service.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


def _extract_acs_user_id(user) -> str:
    if hasattr(user, "raw_id") and user.raw_id:
      return user.raw_id
    if hasattr(user, "id") and user.id:
      return user.id
    return str(user)


@router.post("/", status_code=201, description="Start a chat thread")
async def start_chat_thread(payload: StartChatThread):
    chat_service = ChatService()
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

        return {
            "status": "Success",
            "created": False,
            "data": {
                "threadId": existing_chat["thread_id"],
                "token": requester_details["token"],
                "acsUserId": requester_details["acs_user_id"],
                "endpoint": chat_service.endpoint_url,
                "poNumber": existing_chat.get("po_number"),
                "participants": existing_chat.get("participants", []),
            },
        }

    logging.info("Creating a new ACS-backed chat thread for PO %s", payload.po_number)

    starter_user = chat_service.identity_client.create_user()
    remote_user = chat_service.identity_client.create_user()

    starter_token = chat_service.create_token(starter_user).token
    remote_token = chat_service.create_token(remote_user).token

    starter_acs_user_id = _extract_acs_user_id(starter_user)
    remote_acs_user_id = _extract_acs_user_id(remote_user)

    topic = payload.po_number or "Test Thread"

    chat_thread_client, _ = chat_service.create_chat_thread(
        starter_acs_user_id=starter_acs_user_id,
        topic=topic,
        starter_display_name=payload.from_name,
        participant_acs_ids=[remote_acs_user_id],
        participant_display_names={remote_acs_user_id: payload.to_name},
    )

    new_chat = {
        "id": str(uuid.uuid4()),
        "thread_id": chat_thread_client.thread_id,
        "po_number": payload.po_number,
        "participants": [payload.from_email, payload.to_email],
        "participant_details": {
            payload.from_email: {
                "name": payload.from_name,
                "acs_user_id": starter_acs_user_id,
                "token": starter_token,
            },
            payload.to_email: {
                "name": payload.to_name,
                "acs_user_id": remote_acs_user_id,
                "token": remote_token,
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
        },
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
    token = participant_details.get(payload.from_email, participant_details.get(starter_email, {})).get("token")

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
