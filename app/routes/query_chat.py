# from fastapi import APIRouter
# from pydantic import BaseModel

# from app.services.query_chat_service import ask_question

# router = APIRouter(
#     prefix="/query-chat",
#     tags=["Query Chat"]
# )


# class ChatRequest(BaseModel):
#     question: str


# @router.post("/ask")
# def ask(request: ChatRequest):

#     return ask_question(
#         request.question
#     )