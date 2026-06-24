from pydantic import BaseModel, EmailStr, Field

class StartChatThread(BaseModel):
    from_email: EmailStr = Field(alias="fromEmail")
    from_name: str = Field(alias="fromName")
    to_email: EmailStr = Field(alias="toEmail")
    to_name: str = Field(alias="toName")

class AddChatParticipant(BaseModel):
    email: EmailStr
    name: str
    from_email: EmailStr = Field(alias="fromEmail")