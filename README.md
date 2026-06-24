# SCM Procurement Mock Server (FastAPI)

## Features
- MSAL-like login for Procurement Specialist and Admin
- Supplier custom authentication
- Purchase Order CRUD APIs
- Azure Communication Services chat integration
- PostgreSQL persistence for users, suppliers, purchase orders, delegations, and chat metadata
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

## Database Configuration (PostgreSQL)

Application data is now persisted in PostgreSQL (not JSON files at runtime).

Set this environment variable before running:

- `DATABASE_URL` (example: `postgresql+psycopg://postgres:postgres@localhost:5432/scm_procurement`)

Seed JSON files under `data/` are used only to initialize empty tables on first startup.

## Azure Configuration (Chat Integrations)

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
- Runtime persistence is PostgreSQL
- JSON files are seed-only inputs
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

## Excel Seed Workflow
- Purchase order seed data is generated locally from an Excel file into `data/purchase_orders.json`
- Do not commit `.xlsx`/`.xls` source files to GitHub
- Use `OPEN_PO_EXCEL_PATH` or run `python scripts/seed_purchase_orders_from_excel.py <path-to-xlsx>` to regenerate JSON

---