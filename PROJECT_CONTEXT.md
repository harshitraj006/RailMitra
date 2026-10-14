# RailMitra – Smart Railway Seat Exchange & Family Seating System

## PRODUCT
RailMitra is a smart railway seat exchange & family seating system (hackathon MVP).

**Problem:** Families booking together often get berths in different coaches or far apart, so they ask co-passengers to swap informally. These swaps are unrecorded, invisible to the TTE, consent isn't independent, a later-boarding passenger may find their berth occupied, strangers can be pestered repeatedly, and families needing several swaps have no coordinated way to do it.

**Solution:** Passengers send consent-based exchange requests to suitable co-passengers. The other passenger reviews the exact berth details and confirms independently from their own device with OTP verification. The TTE reviews on a dashboard. Exchanges expire at the earlier destination with a reminder to return to the original berth. Every action is audit-logged.

## PROTOTYPE BOUNDARY
> **Disclaimer Footer (on every page):**
> "Prototype using a simulated reservation dataset. Not the official Indian Railways reservation chart or database. Official use would require authorization from Indian Railways."
> The app never claims live railway access and never writes to official systems. Match categories are project-defined preferences, not official railway rules.

---

## BUSINESS RULES

### R1 Validation
Validate PNR, train number, date, stations, coach and berth against the simulated dataset only.

### R2 Identity
User enters a PNR, receives a simulated OTP (6 digits, stored hashed, 5 min expiry, max 3 attempts then 10 min lock). In `DEMO_MODE` show the code in a visible demo banner and the console. On success the server issues a session token. Protected endpoints identify the acting passenger by header `X-Session-Token`; one token = one passenger. TTE uses header `X-TTE-Key`. Role-based access: passenger vs TTE.

### R3 Request limit
Each passenger may send at most 3 requests per journey. Accepted, declined, cancelled and expired all count. The same requester cannot request the same target twice. In a group every member has their own limit (a group of 5 can send up to 15). Limit restarts on the next journey. The 4th request returns HTTP 429; a repeat returns 409.

### R4 Matching
Candidates are on the same train and date, not the requester, not in the requester's group. Compute the overlapping journey segment using route order; exclude if no overlap.
- **BEST MATCH:** same destination and feasible segment.
- **POSSIBLE MATCH:** destination differs by 1 to 3 stops along the route and a direct exchange is feasible.
- **Not eligible:** different train/date, no overlap, incompatible berth needs (never offer a worse berth type to a passenger aged 60+ or flagged `needs_lower_berth`), or the requester.
- **Rank:** Best before Possible, then same coach, then smaller berth-number distance to the requester (or nearest family member), then smaller destination gap.
- Each result carries a human-readable "why" and a proximity score.
- Never expose candidates' PNR/phone/email; show first name, coach, berth, type and segment only. Matching is a pure, well-tested module.

### R5 Consent
The target sees the offered coach, berth number, berth type and segment and may accept or decline without penalty. Only the target's own session may respond (others get 403). A request never reaches the TTE queue with only one side's confirmation. The requester can cancel only while `PENDING_CONSENT`; a cancelled request still counts toward the limit.

### R6 Segment and expiry
An exchange applies only while both passengers are on the train together.
- `start_station` = later boarding station
- `expiry_station` = EARLIER destination station
At expiry mark the request `EXPIRED` and notify both: "Please return to your original berth: Coach X, Berth N." A demo endpoint advances the simulated train station by station, triggering expiry. The UI must say reminders support compliance but cannot physically enforce it.

### R7 Group requests
Linked exchanges submitted together. Check every member's limit individually; if any would exceed, reject the whole group request with details. The group is `FULLY_CONFIRMED` only when every affected passenger consents. If no complete arrangement exists, report what is missing and offer partial options; never auto-finalize partial results. Show live group progress ("3 of 4 confirmed").

### R8 TTE dashboard
Shows original vs proposed allocation, segment, expiry station, both consents, group info, review status. Approve, reject or clarify with note. Approval blocked with 409 unless both consents exist. Decisions notify both passengers.

### R9 Audit
Every state change writes a timestamped `AuditLog` row. TTE can view the trail per request.

### R10 Notifications
In-app plus simulated SMS/email printed to the console for request received, accepted, declined, TTE decision, expiry reminder.

### R11 Privacy
Minimum data only (PNR, train, date, stations, coach, berth). No payment or ID-document data. Contact details masked and simulated.

---

## REQUEST STATUSES
- `PENDING_CONSENT`
- `ACCEPTED_BY_PASSENGER`
- `DECLINED`
- `CANCELLED`
- `EXPIRED`
- `TTE_APPROVED`
- `TTE_REJECTED`
- `CLARIFICATION_REQUESTED`

---

## API SURFACE
Error shape is standardized across all endpoints: `{ "detail": "message", "code": "ERROR_CODE" }`.
HTTP status codes used: 400 (Bad Request), 403 (Forbidden), 404 (Not Found), 409 (Conflict), 423 (Locked / OTP lock), 429 (Too Many Requests).

- `POST /api/journey/validate`
- `POST /api/otp/send`
- `POST /api/otp/verify`
- `GET /api/me`
- `GET /api/match`
- `POST /api/requests`
- `GET /api/requests/mine`
- `GET /api/requests/incoming`
- `GET /api/requests/remaining`
- `POST /api/requests/{id}/respond`
- `POST /api/requests/{id}/cancel`
- `POST /api/group-requests`
- `GET /api/group-requests/{id}`
- `GET /api/notifications`
- `POST /api/notifications/{id}/read`
- `GET /api/tte/requests`
- `POST /api/tte/requests/{id}/review`
- `GET /api/tte/audit`
- `GET /api/requests/{id}/slip`
- `POST /api/demo/advance_train`
- `POST /api/demo/reset`
- `GET /health`
- `WS /ws`

---

## BUILD PLAN
- **Part 1:** Foundation (Stack setup, architecture plan, database models, schemas, idempotent seed dataset with worked examples, error handling, health endpoint, seed verification tests).
- **Part 2:** Core engine APIs (Journey validation, OTP auth, session handling, matching engine pure logic and tests, single exchange request creation and remaining limits).
- **Part 3:** Consent, expiry, groups, TTE, audit, realtime (Exchange response/cancellation, group requests, train progress simulation & station expiry, TTE dashboard APIs, audit trail, WebSocket updates).
- **Part 4:** Frontend, QR slip, i18n, dark mode, browser verification, docs (Responsive UI, passenger portal, TTE dashboard, exchange slip with QR code, dark mode toggle, English/Hindi language toggle, browser subagent testing, deployment guide).

---

## PROGRESS
- **Part 1:** COMPLETED (Foundation & Seed Verification)
  - Full implementation plan authored in `docs/implementation_plan.md`.
  - Git repository initialized.
  - Async stack configured (FastAPI, SQLAlchemy 2.0 async with `aiosqlite`/`asyncpg`, Pydantic v2).
  - Complete data models in `app/models.py` with indexes and foreign keys.
  - All Pydantic request/response schemas created in `app/schemas.py`.
  - Idempotent seed data in `app/seed.py` matching the worked-example specifications (Asha, Meera, Kiran, Ravi, Vikram, Verma family of 5, out-of-scope passengers, TTE user).
  - Global error handling returning standardized `{detail, code}` shape.
  - Health check endpoint `GET /health` and static files mounted.
  - Automated tests in `tests/test_seed.py` passing (9/9 tests passed).
  - Swagger UI verified in browser at `/docs`.
- **Part 2:** PENDING (Core Engine APIs: Journey validation, OTP auth, matching engine pure logic, exchange requests creation)
- **Part 3:** PENDING (Consent, expiry, groups, TTE dashboard, audit, realtime WebSockets)
- **Part 4:** PENDING (Frontend UI, QR slip, i18n, dark mode, browser verification)

