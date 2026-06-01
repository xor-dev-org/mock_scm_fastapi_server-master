
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, po, supplier, admin, delegation


app = FastAPI(
    title="SCM Procurement Mock Server",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth.router)
app.include_router(po.router)
app.include_router(supplier.router)
app.include_router(admin.router)
app.include_router(delegation.router)

@app.get("/health")
def health():
    return {"status": "UP"}