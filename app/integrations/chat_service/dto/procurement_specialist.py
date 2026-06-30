from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _AliasBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ProcurementSpecialistCreate(_AliasBaseModel):
    email: EmailStr


class SupplierCreate(_AliasBaseModel):
    email: EmailStr
    name: str
    supplier_code: str = Field(validation_alias="supplierCode", serialization_alias="supplierCode")
    organization_name: str = Field(validation_alias="organizationName", serialization_alias="organizationName")
    address: str
    city: str
    state: str
    pincode: str
    country: str


class StartChatThread(_AliasBaseModel):
    from_email: EmailStr = Field(validation_alias="fromEmail", serialization_alias="fromEmail")
    from_name: str = Field(validation_alias="fromName", serialization_alias="fromName")
    to_email: EmailStr = Field(validation_alias="toEmail", serialization_alias="toEmail")
    to_name: str = Field(validation_alias="toName", serialization_alias="toName")
    po_number: Optional[str] = Field(default=None, validation_alias="poNumber", serialization_alias="poNumber")


class AddChatParticipant(_AliasBaseModel):
    email: EmailStr
    name: str
    from_email: EmailStr = Field(validation_alias="fromEmail", serialization_alias="fromEmail")
