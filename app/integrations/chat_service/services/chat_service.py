import base64
import binascii
import os
from typing import List, Optional, Tuple

from azure.core.credentials import AccessToken
from azure.communication.chat import ChatClient, ChatParticipant, ChatThreadClient, CommunicationTokenCredential
from azure.communication.identity import CommunicationIdentityClient, CommunicationUserIdentifier


class ChatService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChatService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        connection_string = os.getenv("AZURE_COMMUNICATION_CONNECTION_STRING") or os.getenv("ACS_CONNECTION_STRING")
        endpoint_url = os.getenv("AZURE_COMMUNICATION_ENDPOINT")

        self._identity_client = None
        self._user = None

        if not connection_string:
            raise ValueError(
                "Azure Communication connection string is missing. "
                "Set AZURE_COMMUNICATION_CONNECTION_STRING or ACS_CONNECTION_STRING."
            )

        self._validate_connection_string(connection_string)

        if not endpoint_url:
            endpoint_url = self._extract_endpoint_from_connection_string(connection_string)

        if not endpoint_url:
            raise ValueError(
                "Azure Communication endpoint is missing. "
                "Set AZURE_COMMUNICATION_ENDPOINT or include endpoint=... in the connection string."
            )

        self.endpoint_url = endpoint_url
        try:
            self._identity_client = CommunicationIdentityClient.from_connection_string(connection_string)
        except Exception as exc:
            raise ValueError(
                "Invalid Azure Communication connection string. "
                "Check endpoint and base64 access key formatting."
            ) from exc

    @staticmethod
    def _extract_endpoint_from_connection_string(connection_string: str) -> Optional[str]:
        for segment in connection_string.split(";"):
            key, _, value = segment.partition("=")
            if key.strip().lower() == "endpoint":
                return value.strip() or None
        return None

    @staticmethod
    def _extract_access_key(connection_string: str) -> Optional[str]:
        for segment in connection_string.split(";"):
            key, _, value = segment.partition("=")
            if key.strip().lower() == "accesskey":
                return value.strip() or None
        return None

    @classmethod
    def _validate_connection_string(cls, connection_string: str) -> None:
        try:
            connection_string.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError(
                "Azure Communication connection string contains non-ASCII characters. "
                "This usually means the access key was copied with an ellipsis or smart punctuation."
            ) from exc

        access_key = cls._extract_access_key(connection_string)
        if not access_key:
            raise ValueError("Azure Communication connection string is missing accesskey=...")

        try:
            base64.b64decode(access_key, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                "Azure Communication access key is not valid base64. "
                "Use the full key from the Azure portal without truncation."
            ) from exc

    @property
    def identity_client(self) -> CommunicationIdentityClient:
        return self._identity_client
    
    @property
    def user(self) -> CommunicationUserIdentifier:
        if self._user is None:
            self._user = self.identity_client.create_user()
        return self._user

    def create_user(self) -> CommunicationUserIdentifier:
        created_user = self.identity_client.create_user()
        return created_user

    def create_token(self, user: CommunicationUserIdentifier, scopes: Optional[List[str]] = None) -> AccessToken:
        if scopes is None:
            scopes = ["chat"]
        return self.identity_client.get_token(user, scopes=scopes)

    def create_chat_thread(
        self,
        starter_acs_user_id: str,
        topic: Optional[str] = None,
        starter_display_name: Optional[str] = None,
        participant_acs_ids: Optional[List[str]] = None,
        participant_display_names: Optional[dict[str, str]] = None,
    ) -> Tuple[ChatThreadClient, str]:
        """Start a chat thread and return the thread client plus the starter token."""
        starter_user = CommunicationUserIdentifier(starter_acs_user_id)
        starter = ChatParticipant(
            identifier=starter_user,
            display_name=starter_display_name or starter_acs_user_id,
        )
        token_response = self.create_token(starter_user)
        token = token_response.token
        token_credential = CommunicationTokenCredential(token)
        chat_client = ChatClient(endpoint=self.endpoint_url, credential=token_credential)

        thread_participants = [starter]
        for acs_user_id in participant_acs_ids or []:
            if acs_user_id == starter_acs_user_id:
                continue

            thread_participants.append(
                ChatParticipant(
                    identifier=CommunicationUserIdentifier(acs_user_id),
                    display_name=(participant_display_names or {}).get(acs_user_id, acs_user_id),
                )
            )

        thread_result = chat_client.create_chat_thread(topic, thread_participants=thread_participants)
        return chat_client.get_chat_thread_client(thread_result.chat_thread.id), token

    def add_participant(self, thread_id: str, token: str, acs_user_id: str, display_name: Optional[str] = None):
        """Invite or add a remote participant to an existing chat thread."""
        participant_user = CommunicationUserIdentifier(acs_user_id)
        participant = ChatParticipant(
            identifier=participant_user,
            display_name=display_name or acs_user_id,
        )

        token_credential = CommunicationTokenCredential(token)
        chat_client = ChatClient(endpoint=self.endpoint_url, credential=token_credential)

        thread_client = chat_client.get_chat_thread_client(thread_id)
        return thread_client.add_participants([participant])
 
    def create_token_from_user_id(self, acs_user_id: str) -> str:
        user = CommunicationUserIdentifier(acs_user_id)

        token = self.identity_client.get_token(
            user,
            scopes=["chat"]
        )

        return token.token