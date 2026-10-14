# RailMitra Implementation Plan (Part 1 - 4)

## 1. System Architecture
RailMitra is built with a high-performance, modular full-stack architecture:
- **Backend Service:** FastAPI (Python 3.11+) asynchronous framework providing REST and WebSocket endpoints.
- **Database Layer:** SQLAlchemy 2.0 async engine (`sqlite+aiosqlite` for local dev/testing, `postgresql+asyncpg` for production via `DATABASE_URL`).
- **Data Modeling & Validation:** Pydantic v2 schemas providing strict data validation, serialization, and OpenAPI documentation generation.
- **State Management & Audit Trail:** Immutable audit logs (`AuditLog`) tracking transitions across requests and confirmations.
- **Real-Time Notification & Synch:** WebSockets (`/ws`) broadcasting request updates, expiry alerts, and TTE reviews to connected sessions.
- **Frontend Layer:** Vanilla HTML5, modern CSS3 (with responsive layout, glassmorphic dark/light aesthetics, Indian Railways branding cues), and modular JS communicating with REST & WS endpoints.

```
+-------------------------------------------------------------------------+
|                              Frontend UI                                |
|  +--------------------+   +---------------------+   +----------------+  |
|  | Passenger Portal   |   | Family Group Coord. |   | TTE Dashboard  |  |
|  +--------------------+   +---------------------+   +----------------+  |
+------------------------------------+------------------------------------+
                                     |  HTTP REST & WebSocket
                                     v
+-------------------------------------------------------------------------+
|                        FastAPI Backend Engine                           |
|  +------------------+  +-------------------+  +-----------------------+ |
|  | Auth & Session   |  | Matching Engine   |  | Consent & Expiry Svc  | |
|  +------------------+  +-------------------+  +-----------------------+ |
|  +------------------+  +-------------------+  +-----------------------+ |
|  | TTE Admin & Audit|  | Realtime WS Hub   |  | Simulated Rail Engine | |
|  +------------------+  +-------------------+  +-----------------------+ |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                       SQLAlchemy 2.x Async ORM                          |
|             (SQLite railmitra.db / PostgreSQL Container)                |
+-------------------------------------------------------------------------+
```

---

## 2. Data Model Design
- **Train:** Train master info, route stations in sequential JSON array.
- **Passenger:** Simulated passenger records with PNR, train assignment, coach, berth, station segment, age, lower berth necessity, and group affiliation.
- **Group:** Family or travel group linking multiple passengers under one reference.
- **GroupRequest:** Multi-party exchange request linking multiple individual exchanges.
- **ExchangeRequest:** Seat exchange request between requester and target with category (`BEST`/`POSSIBLE`), segment, and status lifecycle.
- **OTPCode:** Simulated 6-digit OTP with secure SHA-256 hash, attempt counting, and exponential/temporary lockout.
- **Session:** Bearer token session identifying authenticated passenger.
- **Confirmation:** Formal affirmative or negative consent from passenger device session.
- **TTEReview:** TTE sign-off, rejection, or clarification note.
- **Notification:** User-facing notifications (in-app and simulated SMS/email).
- **AuditLog:** Complete audit trail tracking entity state changes.

---

## 3. API Surface Specification
1. **Journey & Auth:**
   - `POST /api/journey/validate`: Validate PNR and train itinerary.
   - `POST /api/otp/send`: Issue simulated 6-digit OTP.
   - `POST /api/otp/verify`: Verify OTP, return session token `X-Session-Token`.
   - `GET /api/me`: Get active passenger profile and journey details.
2. **Matching Engine:**
   - `GET /api/match`: Pure candidate search engine yielding ranked Best/Possible matches with "why" descriptions and proximity scores.
3. **Seat Exchange Requests:**
   - `POST /api/requests`: Submit exchange request to co-passenger (subject to 3-request journey cap).
   - `GET /api/requests/mine`: Retrieve requests sent by user.
   - `GET /api/requests/incoming`: Retrieve requests received by user.
   - `GET /api/requests/remaining`: Check remaining request quota (out of 3).
   - `POST /api/requests/{id}/respond`: Accept or decline incoming exchange request.
   - `POST /api/requests/{id}/cancel`: Cancel pending exchange request.
4. **Group Operations:**
   - `POST /api/group-requests`: Link family requests together.
   - `GET /api/group-requests/{id}`: Live status of family group exchange.
5. **Notifications & Realtime:**
   - `GET /api/notifications`: List passenger notifications.
   - `POST /api/notifications/{id}/read`: Mark notification read.
   - `WS /ws`: Real-time updates via WebSocket.
6. **TTE Operations:**
   - `GET /api/tte/requests`: TTE dashboard queue of confirmed exchanges.
   - `POST /api/tte/requests/{id}/review`: Approve, reject, or request clarification.
   - `GET /api/tte/audit`: View complete audit trail.
7. **Exchange Slips & Verification:**
   - `GET /api/requests/{id}/slip`: Generate digital exchange slip with QR code representation.
8. **Demo Utilities & Health:**
   - `POST /api/demo/advance_train`: Advance train position station-by-station to test expiry.
   - `POST /api/demo/reset`: Re-seed database to known reference state.
   - `GET /health`: Health and readiness probe.

---

## 4. Screen / User Interface List
- **Screen 1: Landing & PNR Verification:** PNR search, journey card, simulated OTP modal with demo banner display.
- **Screen 2: Passenger Berth & Match Discovery:** Interactive coach layout indicator, list of ranked Best Matches and Possible Matches with proximity badges and "why" explanations.
- **Screen 3: Outgoing & Incoming Exchange Requests:** Request management card, accept/decline action triggers, quota indicator (e.g. "2 of 3 requests remaining").
- **Screen 4: Group Family Coordination:** Multi-seat visualizer showing family berths across coaches and linked swap confirmations.
- **Screen 5: Approved Exchange Slip:** Digital boarding exchange slip with QR code, original vs current berth, and expiry station warning banner.
- **Screen 6: TTE Dashboard:** Real-time stream of pending approvals, side-by-side berth comparison, consent verification flags, action modal with audit drawer.
- **Screen 7: Station Advance & Simulation Control Bar:** Sticky demo bar to simulate train station arrivals, trigger auto-expiry alerts, and reset data.

---

## 5. Risk Assessment & Mitigation
| Risk | Severity | Mitigation Strategy |
|---|---|---|
| Passenger harassment / spamming | High | Strict limit of 3 requests per journey, repeat requests to same candidate blocked with 409, no private contact info disclosed. |
| Incompatible berth swaps for vulnerable passengers | High | Business rule R4 strictly forbids proposing middle/upper berths to passengers aged 60+ or flagged `needs_lower_berth`. |
| Berth occupation conflict after earlier destination | High | Station overlap calculation sets strict `expiry_station`; simulation auto-expires swaps at earlier stop and emits push return reminders. |
| Unauthorized swap by third party | Medium | Two-factor verification: simulated OTP per passenger, separate device session token required for consent. |
| TTE out of loop | Medium | Exchange slip is only valid upon TTE approval; TTE queue only accepts dual-consented requests. |
| Unofficial system confusion | Medium | Prominent prototype boundary disclaimer on every screen, slips, and documentation. |

---

## 6. Test Plan
- **Unit & Logic Tests:**
  - Route station segment intersection algorithm.
  - Candidate matching filter and ranking comparator.
  - Quota counter & lockout calculation.
- **Database & Seed Verification (Part 1):**
  - Verify seed generation idempotence.
  - Verify worked-example entities: Asha (S2-14), Meera (S2-41), Kiran (S2-43), Ravi (S2-46), Vikram (S2-50), Neha, Sunita, second family of 5, out-of-scope train T-202, different journey date passenger.
- **API Integration Tests (Parts 2 & 3):**
  - Validation & OTP flow, token issuance.
  - Match response format, categorization, and sorting.
  - Single & group request lifecycle.
  - TTE approval prerequisite enforcement.
  - Station advance triggering expiry.
- **E2E & UI Verification (Part 4):**
  - Browser subagent automated navigation across passenger and TTE workflows.
