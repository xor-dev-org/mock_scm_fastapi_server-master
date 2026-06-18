# Chat Service API Reference

## Base URL

```text
http://localhost:8000
```

## Auth

All chat APIs require bearer token.

```http
Authorization: Bearer <access_token>
```

---

## Chat Types

- `PS_SUPPLIER`: Chat between Procurement Specialist and Supplier. Must be PO-linked.
- `PS_PS`: Chat between two Procurement Specialists. PO link is optional.

---

## 1. Create Chat Session

### Endpoint

```http
POST /chat/sessions
```

### Request

```json
{
  "chat_type": "PS_SUPPLIER",
  "participant_ids": ["SUP-001"],
  "po_id": "683f8fda-2c9b-4252-99c5-cf2ca7b65e89",
  "title": "PO-10001 discussion"
}
```

### Success

```json
{
  "created": true,
  "session": {
    "id": "f4a7c5fe-7c2f-49b6-b8a8-1f533ddc345f",
    "chat_type": "PS_SUPPLIER",
    "po_id": "683f8fda-2c9b-4252-99c5-cf2ca7b65e89",
    "po_number": "PO-10001",
    "participants": [
      {"user_id": "PS-001", "name": "Procurement Specialist 1", "role": "PROCUREMENT_SPECIALIST"},
      {"user_id": "SUP-001", "name": "Supplier 1", "role": "SUPPLIER"}
    ],
    "last_message_preview": "",
    "last_message_at": null,
    "unread_count": 0,
    "status": "ACTIVE"
  }
}
```

### Common Errors

```json
{"detail": "po_id is required for PS_SUPPLIER chat"}
```

```json
{"detail": "PS is not assigned to the PO"}
```

```json
{"detail": "Supplier is not assigned to the PO"}
```

---

## 2. Search or Create Session

### Endpoint

```http
POST /chat/sessions/search-or-create
```

### Request

Same schema as `POST /chat/sessions`.

### Success

```json
{
  "created": false,
  "session": {
    "id": "f4a7c5fe-7c2f-49b6-b8a8-1f533ddc345f"
  }
}
```

---

## 3. List My Sessions

### Endpoint

```http
GET /chat/sessions
```

### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| page | int | No | Default = 1 |
| page_size | int | No | Default = 20 |
| chat_type | string | No | `PS_SUPPLIER` or `PS_PS` |
| po_id | string | No | Filter PO-linked sessions |
| search | string | No | Search by PO number, participant, message preview |

### Success

```json
{
  "page": 1,
  "page_size": 20,
  "total": 2,
  "data": [
    {
      "id": "f4a7c5fe-7c2f-49b6-b8a8-1f533ddc345f",
      "chat_type": "PS_SUPPLIER",
      "po_number": "PO-10001",
      "last_message_preview": "Please confirm delivery date",
      "last_message_at": "2026-06-18T08:20:00+00:00",
      "unread_count": 1
    }
  ]
}
```

---

## 4. Search Sessions + Initiation Suggestions

### Endpoint

```http
GET /chat/sessions/search?q=po-10001&chat_type=PS_SUPPLIER&page=1&page_size=20
```

### Success

```json
{
  "page": 1,
  "page_size": 20,
  "total": 1,
  "sessions": [
    {
      "id": "f4a7c5fe-7c2f-49b6-b8a8-1f533ddc345f",
      "chat_type": "PS_SUPPLIER",
      "po_number": "PO-10001"
    }
  ],
  "suggestions": {
    "users": [
      {"user_id": "SUP-001", "name": "Supplier 1", "role": "SUPPLIER"}
    ],
    "purchase_orders": [
      {
        "po_id": "683f8fda-2c9b-4252-99c5-cf2ca7b65e89",
        "po_number": "PO-10001",
        "supplier_id": "SUP-001",
        "procurement_specialist_id": "PS-001"
      }
    ]
  }
}
```

---

## 5. Get Session Messages

### Endpoint

```http
GET /chat/sessions/{session_id}/messages?page=1&page_size=50
```

### Success

```json
{
  "page": 1,
  "page_size": 50,
  "total": 2,
  "data": [
    {
      "id": "f2ad56bc-df5d-479e-a3ce-a9b97ec38c58",
      "session_id": "f4a7c5fe-7c2f-49b6-b8a8-1f533ddc345f",
      "acs_message_id": "local-msg-f0b31fd7-b974-467a-ab8f-9c8de57ba72e",
      "sender_id": "PS-001",
      "sender_name": "Procurement Specialist 1",
      "content": "Please confirm delivery date",
      "provider": "local-fallback",
      "created_at": "2026-06-18T08:20:00+00:00"
    }
  ]
}
```

---

## 6. Send Message

### Endpoint

```http
POST /chat/sessions/{session_id}/messages
```

### Request

```json
{
  "content": "Confirmed. Delivery by next Tuesday."
}
```

### Success

```json
{
  "message": {
    "id": "0344e2eb-2b03-4a87-89c9-5741b250f82f",
    "session_id": "f4a7c5fe-7c2f-49b6-b8a8-1f533ddc345f",
    "content": "Confirmed. Delivery by next Tuesday."
  },
  "session": {
    "id": "f4a7c5fe-7c2f-49b6-b8a8-1f533ddc345f",
    "last_message_preview": "Confirmed. Delivery by next Tuesday.",
    "unread_count": 0
  }
}
```

---

## 7. Mark Session Read

### Endpoint

```http
POST /chat/sessions/{session_id}/read
```

### Request

```json
{
  "last_read_message_id": "0344e2eb-2b03-4a87-89c9-5741b250f82f"
}
```

### Success

```json
{
  "message": "Read state updated",
  "session": {
    "id": "f4a7c5fe-7c2f-49b6-b8a8-1f533ddc345f",
    "unread_count": 0
  },
  "last_read_message_id": "0344e2eb-2b03-4a87-89c9-5741b250f82f"
}
```

---

## 8. Realtime Bootstrap

### Endpoint

```http
GET /chat/realtime/bootstrap
```

### Success

```json
{
  "transport_preference": "azure_signalr",
  "signalr": {
    "enabled": true,
    "endpoint": "https://<signalr>.service.signalr.net",
    "hub": "procurementchat"
  },
  "websocket_fallback": {
    "enabled": true,
    "url": "/chat/realtime/ws?access_token=<JWT>"
  },
  "event_grid": {
    "ingestion_endpoint": "/chat/realtime/events",
    "supported_event_types": [
      "Microsoft.EventGrid.SubscriptionValidationEvent",
      "Microsoft.Communication.ChatMessageReceivedInThread"
    ]
  },
  "current_user": {
    "id": "PS-001",
    "role": "PROCUREMENT_SPECIALIST"
  }
}
```

---

## 9. Event Grid Ingestion (Backend to Backend)

### Endpoint

```http
POST /chat/realtime/events
```

Used by Azure Event Grid subscription for ACS chat events.

---

## 10. WebSocket Fallback

### Endpoint

```text
ws://localhost:8000/chat/realtime/ws?access_token=<JWT>
```

Supports ping/pong and notification push when SignalR is unavailable.
