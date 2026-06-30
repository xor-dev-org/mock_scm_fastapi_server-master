from pydantic import BaseModel

class SqlAgentQueryRequest(BaseModel):
    query: str