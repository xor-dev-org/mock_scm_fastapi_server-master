# Frontend Changes for Backend Chat Integration

This document lists what frontend should implement later, based on the backend chat APIs now added.

## Scope and Constraints
- Do not change procurement domain flows outside chat screens and notification indicators.
- Support two chat types:
  - `PS_SUPPLIER`: must be linked to a PO (`po_id` mandatory).
  - `PS_PS`: optional PO link (`po_id` optional).
- Realtime notifications should prefer Azure SignalR based flow and fall back to websocket if needed.

## New Backend APIs to Consume
- `POST /chat/sessions`
  - Create chat session.
  - Request:
    - `chat_type`: `PS_SUPPLIER` | `PS_PS`
    - `participant_ids`: string[] (server auto-includes current user)
    - `po_id`: optional for `PS_PS`, required for `PS_SUPPLIER`
    - `title`: optional
- `POST /chat/sessions/search-or-create`
  - Same payload as create; returns existing session if already present.
- `GET /chat/sessions`
  - List sessions for current user.
  - Query filters: `page`, `page_size`, `chat_type`, `po_id`, `search`
- `GET /chat/sessions/search`
  - Returns matching sessions plus suggestions for user and PO search.
  - Query: `q`, `chat_type`, `page`, `page_size`
- `GET /chat/sessions/{session_id}/messages`
  - Paginated message list.
- `POST /chat/sessions/{session_id}/messages`
  - Send new message.
- `POST /chat/sessions/{session_id}/read`
  - Mark unread count for current user as read.
- `GET /chat/realtime/bootstrap`
  - Returns SignalR details and websocket fallback path.

## API Client Additions
Add a new service module matching existing frontend service patterns:
- `src/api/services/chatService.ts`

Recommended client functions:
- `listSessions(params)`
- `searchSessions(params)`
- `createSession(payload)`
- `searchOrCreateSession(payload)`
- `listMessages(sessionId, params)`
- `sendMessage(sessionId, payload)`
- `markRead(sessionId, payload)`
- `getRealtimeBootstrap()`

## Data Types to Add
Add chat-specific types in `src/api/types.ts` or `src/models/index.ts`:
- `ChatType = 'PS_SUPPLIER' | 'PS_PS'`
- `ChatParticipant`
- `ChatSession`
- `ChatMessage`
- `ChatSessionListResponse`
- `ChatSearchResponse`
- `RealtimeBootstrapResponse`

Important fields from session payload:
- `id`
- `chat_type`
- `po_id`
- `po_number`
- `participants[]`
- `last_message_preview`
- `last_message_at`
- `unread_count` (computed for current user)

## UI Work Items
- Replace chat placeholder page with 3-panel flow on desktop and stacked flow on mobile:
  - Session list
  - Active conversation messages
  - Context details (participants, PO link)
- Add search input with two modes:
  - Search existing sessions
  - Search participants/PO to start new session
- Add create chat dialog/sheet:
  - Type selector (`PS_SUPPLIER` / `PS_PS`)
  - Participant picker
  - PO selector (required only for `PS_SUPPLIER`)
- Add unread badges:
  - Sidebar chat menu badge
  - Optional top header bell badge

## Realtime Integration Plan
1. On app start (after auth), call `GET /chat/realtime/bootstrap`.
2. If `signalr.enabled=true`, connect through frontend SignalR client/hub config.
3. If SignalR unavailable, connect to websocket fallback endpoint from bootstrap.
4. Handle incoming events:
   - `CHAT_NEW_MESSAGE`
   - `CHAT_EVENTGRID_MESSAGE`
5. On each new message event:
   - Update session preview/time ordering
   - Increment unread badge if session is not currently open
   - Optionally trigger toast/snackbar alert

## Session List Behavior Rules
- Default ordering: latest activity first.
- Show unread count and last message preview.
- For `PS_SUPPLIER`, display PO number prominently.
- For `PS_PS`, show participant names and optional PO chip if linked.

## Message Thread Behavior Rules
- Load paginated history on session open.
- When sending message:
  - Optimistically render pending message
  - Replace pending with server message on success
  - Rollback and show error on failure
- On thread focus, call `POST /chat/sessions/{session_id}/read`.

## Security/Authorization UX Notes
- Backend enforces strict PO assignment for `PS_SUPPLIER`.
- Frontend should surface backend 403 errors clearly, for example:
  - "Selected users are not assigned to this PO."
- Hide invalid create options based on current user role where possible.

## Suggested Frontend File Touchpoints
- `src/pages/Chat.tsx`
- `src/api/services/chatService.ts` (new)
- `src/api/types.ts` or `src/models/index.ts`
- `src/components/layout/Sidebar.tsx` (chat unread badge)
- `src/components/layout/Header.tsx` (optional notification icon/badge)
- `src/app/slices/` (new chat slice if using Redux for chat state)

## Microservice-Friendly Frontend Notes
Keep API client usage behind service interfaces to simplify future endpoint migration.
If chat backend moves to separate service later, frontend should only need base URL/service config changes.
