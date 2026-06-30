import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from app.integrations.chat_service.controllers import (
    chat_controller as integration_chat_controller,
    procurement_specialist_controller,
    supplier_controller as integration_supplier_controller, 
)
# from app.integrations.chat_service.database.db import client

from fastapi.middleware.cors import CORSMiddleware
import logging
from app.routes import auth, po, supplier, admin, delegation, userpref, chat, ai_controller
from app.utils.postgres_db import initialize_database


app = FastAPI(
    title="SCM Procurement Mock Server",
    version="1.0.0"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth.router)
app.include_router(po.router)
app.include_router(supplier.router)
app.include_router(admin.router)
app.include_router(delegation.router)
app.include_router(userpref.router)
app.include_router(chat.router)
app.include_router(ai_controller.router)
#app.include_router(query_chat.router)

@app.get("/seed")
def seed_db():
    logging.info(f"Starting seeding the database....")
    initialize_database()
    logging.info(f"Database seeding completed successfully!")

    return {"status": "Success"}

@app.get("/health")
def health():
    return {"status": "UP"}


app.include_router(procurement_specialist_controller.router)
app.include_router(integration_supplier_controller.router)
app.include_router(integration_chat_controller.router)
