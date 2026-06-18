# SCM Procurement Mock Server (FastAPI)

## Features
- MSAL-like login for Procurement Specialist and Admin
- Supplier custom authentication
- Purchase Order CRUD APIs
- Azure Communication Services chat integration
- Azure Cosmos DB storage for chat session/message metadata
- Pagination and filtering
- RBAC-ready responses
- PO relationships with Procurement Specialist and Supplier

---

## Setup

### Create virtual environment

#### Windows
```bash
python -m venv venv
venv\Scripts\activate
```

#### Linux / Mac
```bash
python -m venv venv
source venv/bin/activate
```

---

## Install dependencies

```bash
pip install -r requirements.txt
```

---

## Run server

```bash
uvicorn app.main:app --reload
```

Server URL:
http://127.0.0.1:8000

Swagger:
http://127.0.0.1:8000/docs

---

## Azure Configuration (Chat)

Chat endpoints are now backed by Azure Cosmos DB and no longer use local JSON files for chat metadata.

Set these environment variables before running:

- `AZURE_COSMOS_ENDPOINT`
- `AZURE_COSMOS_KEY`
- `AZURE_COSMOS_DATABASE` (default: `procurement`)
- `AZURE_COSMOS_CHAT_SESSIONS_CONTAINER` (default: `chat_sessions`)
- `AZURE_COSMOS_CHAT_MESSAGES_CONTAINER` (default: `chat_messages`)
- `AZURE_COSMOS_CHAT_USER_MAP_CONTAINER` (default: `chat_user_map`)
- `AZURE_COSMOS_USERS_CONTAINER` (default: `users`)
- `AZURE_COSMOS_SUPPLIERS_CONTAINER` (default: `suppliers`)
- `AZURE_COSMOS_PURCHASE_ORDERS_CONTAINER` (default: `purchase_orders`)

Optional realtime/Azure chat variables:

- `ACS_CONNECTION_STRING`
- `AZURE_SIGNALR_ENDPOINT`
- `AZURE_SIGNALR_HUB`
- `AZURE_SIGNALR_ACCESS_KEY`

---

## Auth

### Procurement Specialist / Admin
Mock MSAL login endpoint.

### Supplier
Email/password authentication.

---

## Roles
- ADMIN
- PROCUREMENT_SPECIALIST
- SUPPLIER

---

## Important Mock Notes
- JWT token is mocked
- MSAL login is simulated
- Legacy procurement APIs may still use mock JSON storage until full migration
- Chat metadata storage is Azure Cosmos DB
- RBAC information is returned in token payload

---

## Pagination Example

```bash
GET /po?page=1&page_size=10
```

---

## Filter Example

```bash
GET /po?status=APPROVED&supplier_id=SUP-001
```

---

## Seed Data
- 5 Procurement Specialists
- 5 Suppliers
- 1 Admin
- 150 Purchase Orders

---