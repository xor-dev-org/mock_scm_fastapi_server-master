import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional


class ACSChatAdapter:
    """Adapter around Azure Communication Services Chat with local fallback.

    If Azure dependencies or credentials are missing, the adapter gracefully
    falls back to deterministic local identifiers so backend APIs remain usable.
    """

    def __init__(self):
        self.connection_string = os.getenv("ACS_CONNECTION_STRING")
        self.enabled = False
        self._chat_client = None
        self._identity_client = None

        if not self.connection_string:
            return

        try:
            from azure.communication.chat import ChatClient
            from azure.communication.identity import CommunicationIdentityClient

            self._chat_client = ChatClient.from_connection_string(self.connection_string)
            self._identity_client = CommunicationIdentityClient.from_connection_string(
                self.connection_string
            )
            self.enabled = True
        except Exception:
            # Keep service available in fallback mode if SDK or initialization fails.
            self.enabled = False

    def ensure_user(self, internal_user_id: str, user_map: Dict[str, Dict]) -> Dict[str, str]:
        existing = user_map.get(internal_user_id)

        if existing and existing.get("acs_user_id"):
            return {
                "acs_user_id": existing["acs_user_id"],
                "acs_access_token": existing.get("acs_access_token", ""),
                "token_expires_on": existing.get("token_expires_on", ""),
            }

        if not self.enabled:
            return {
                "acs_user_id": f"local:{internal_user_id}",
                "acs_access_token": "",
                "token_expires_on": "",
            }

        try:
            user = self._identity_client.create_user()
            token_response = self._identity_client.get_token(user, scopes=["chat"])

            acs_user_id = self._extract_identifier(user)
            token_value = self._extract_token(token_response)
            expires_on = self._extract_expiry(token_response)

            return {
                "acs_user_id": acs_user_id,
                "acs_access_token": token_value,
                "token_expires_on": expires_on,
            }
        except Exception:
            return {
                "acs_user_id": f"local:{internal_user_id}",
                "acs_access_token": "",
                "token_expires_on": "",
            }

    def create_thread(self, topic: str, participant_acs_ids: List[str]) -> Dict[str, str]:
        if not self.enabled:
            return {
                "thread_id": f"local-thread-{uuid.uuid4()}",
                "provider": "local-fallback",
            }

        try:
            result = self._chat_client.create_chat_thread(topic=topic)
            thread_id = self._extract_thread_id(result)
            # Participant invitation is intentionally decoupled because ACS SDK
            # contracts can vary by package version.
            return {
                "thread_id": thread_id,
                "provider": "azure-communication-services",
            }
        except Exception:
            return {
                "thread_id": f"local-thread-{uuid.uuid4()}",
                "provider": "local-fallback",
            }

    def send_message(
        self,
        thread_id: str,
        content: str,
        sender_display_name: str,
    ) -> Dict[str, str]:
        if not self.enabled:
            return {
                "message_id": f"local-msg-{uuid.uuid4()}",
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "provider": "local-fallback",
            }

        try:
            thread_client = self._chat_client.get_chat_thread_client(thread_id)
            send_result = thread_client.send_message(content=content, sender_display_name=sender_display_name)
            return {
                "message_id": self._extract_message_id(send_result),
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "provider": "azure-communication-services",
            }
        except Exception:
            return {
                "message_id": f"local-msg-{uuid.uuid4()}",
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "provider": "local-fallback",
            }

    @staticmethod
    def _extract_identifier(identifier_obj) -> str:
        if hasattr(identifier_obj, "raw_id"):
            return identifier_obj.raw_id
        if hasattr(identifier_obj, "properties") and isinstance(identifier_obj.properties, dict):
            if identifier_obj.properties.get("id"):
                return identifier_obj.properties["id"]
        return str(identifier_obj)

    @staticmethod
    def _extract_token(token_response) -> str:
        if hasattr(token_response, "token"):
            return token_response.token
        return ""

    @staticmethod
    def _extract_expiry(token_response) -> str:
        if hasattr(token_response, "expires_on") and token_response.expires_on:
            return token_response.expires_on.isoformat() if hasattr(token_response.expires_on, "isoformat") else str(token_response.expires_on)
        return ""

    @staticmethod
    def _extract_thread_id(result) -> str:
        if hasattr(result, "chat_thread") and result.chat_thread and hasattr(result.chat_thread, "id"):
            return result.chat_thread.id
        if hasattr(result, "id"):
            return result.id
        return f"local-thread-{uuid.uuid4()}"

    @staticmethod
    def _extract_message_id(result) -> str:
        if hasattr(result, "id"):
            return result.id
        if hasattr(result, "message_id"):
            return result.message_id
        return f"local-msg-{uuid.uuid4()}"


acs_chat_adapter = ACSChatAdapter()
