
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi import WebSocket, WebSocketDisconnect

from fastapi.middleware.cors import CORSMiddleware
import logging
from app.database.db import Base, engine
from app.routes import auth, admin, chat_controller, misc_controller, ai_controller
from app.services.websocket_service import WebSocketConnectionManager


app = FastAPI(
    title="SCM Procurement Mock Server",
    version="1.0.0"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup logic (Runs on startup)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield # The application runs here while paused
    
    # Cleanup logic (Runs on shutdown, if needed)
    await engine.dispose()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

manager = WebSocketConnectionManager()

# Endpoint for clients to establish their connection
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    logging.info(f"Establishing a websocket connection with user {user_id}")
    await manager.connect(user_id, websocket)
    
    try:
        while True:
            # Keep connection open and handle incoming messages if necessary
            data = await websocket.receive_text()
            logging.info(f"Received the following message from {user_id}: {data}")
    except WebSocketDisconnect as e:
        logging.error(f"Websocket disconnected for user {user_id}: {e}")
        manager.disconnect(user_id)

app.include_router(auth.router)
# app.include_router(po.router)
# app.include_router(supplier.router)
app.include_router(admin.router)
# app.include_router(delegation.router)
# app.include_router(userpref.router)
# app.include_router(chat.router)
app.include_router(chat_controller.router)
app.include_router(misc_controller.router)
app.include_router(ai_controller.router)


@app.get("/health")
def health():
    return {"status": "UP"}

manager = WebSocketConnectionManager()


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id)


# @app.on_event("shutdown")
# def shutdown_event():
#     try:
#         client.close()
#     except Exception:
#         pass
