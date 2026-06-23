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
        connection_string = os.getenv("AZURE_COMMUNICATION_CONNECTION_STRING")
        endpoint_url  = os.getenv("AZURE_COMMUNICATION_ENDPOINT")

        if not connection_string:
            raise ValueError("AZURE_COMMUNICATION_CONNECTION_STRING environment variable is required")
        
        if not endpoint_url:
            raise ValueError("AZURE_COMMUNICATION_ENDPOINT environment variable is required")

        self.endpoint_url = endpoint_url
        self._identity_client = CommunicationIdentityClient.from_connection_string(connection_string)
        self._user = self._identity_client.create_user()

    @property
    def identity_client(self) -> CommunicationIdentityClient:
        return self._identity_client
    
    @property
    def user(self) -> CommunicationUserIdentifier:
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
    ) -> Tuple[ChatThreadClient, str]:
        """Start a chat session and return the new thread client."""
        starter_user = CommunicationUserIdentifier(starter_acs_user_id)
        starter = ChatParticipant(
            identifier=starter_user,
            display_name=starter_display_name or starter_acs_user_id,
        )
        token_response = self.create_token(starter_user)
        token = token_response.token
        token_credential = CommunicationTokenCredential(token)
        chat_client = ChatClient(endpoint=self.endpoint_url, credential=token_credential)

        thread_result = chat_client.create_chat_thread(topic, thread_participants=[starter])
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
 