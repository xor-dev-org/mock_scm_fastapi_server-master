from pydantic import BaseModel, EmailStr, Field

class ProcurementSpecialistCreate(BaseModel):
    email: EmailStr

class SupplierCreate(BaseModel):
    email: EmailStr
    name: str
    supplier_code: str = Field(alias="supplierCode")
    organization_name: str = Field(alias="organizationName")
    address: str
    city: str
    state: str
    pincode: str
    country: str

class StartChatThread(BaseModel):
    from_email: EmailStr = Field(alias="fromEmail")
    from_name: str = Field(alias="fromName")
    to_email: EmailStr = Field(alias="toEmail")
    to_name: str = Field(alias="toName")
    po_number: str | None = Field(default=None, alias="poNumber")

class AddChatParticipant(BaseModel):
    email: EmailStr
    name: str
    from_email: EmailStr = Field(alias="fromEmail")
