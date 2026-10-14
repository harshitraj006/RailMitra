# RailMitra 🚆

**Smart Railway Seat Exchange & Family Seating System (Hackathon MVP)**

RailMitra is a consent-based peer-to-peer seat exchange platform designed for Indian Railways passengers and families traveling together. It transforms informal, uncoordinated berth swapping into a secure, transparent, and TTE-authorized digital experience.

> **PROTOTYPE BOUNDARY DISCLAIMER**  
> *Prototype using a simulated reservation dataset. Not the official Indian Railways reservation chart or database. Official use would require authorization from Indian Railways.*

---

## 🌟 Key Features

1. **Simulated Journey & OTP Verification**: Instant itinerary validation against train charts with salted SHA-256 hashed 6-digit OTP verification, session token issuance, and 10-minute lockout protection.
2. **Pure Algorithmic Matching Engine**: Ranks candidate co-passengers by segment overlap, proximity score, coach distance, and berth preference (**Best Match** vs **Possible Match**).
3. **Vulnerable Passenger Protection**: Senior citizens (age 60+) and passengers requiring lower berths are strictly protected from worse berth offers.
4. **Independent Consent & State Machine**: Double-confirmation requirement — only the target's own authenticated session can accept. State machine rejects illegal transitions with HTTP 409.
5. **Anti-Harassment Quota**: Max 3 exchange requests per journey per passenger. Duplicate requests to the same candidate are blocked.
6. **Segment-Aware Expiry**: Exchanges automatically expire at the earlier destination station with return-to-berth reminders and effective seating reversion.
7. **Family Group Requests**: Linked multi-berth exchanges for families booked across different coaches with per-member quota checks and live confirmation progress.
8. **TTE Inspection Portal**: Real-time review queue, side-by-side allocation review, approval/rejection/clarification actions, live coach seating chart, and immutable audit logs.
9. **Digital Exchange Slip & Cryptographic QR**: Tamper-evident SHA-256 slip with offline client-side QR generation and public read-only verification endpoint (`/api/verify/{token}`).
10. **Zero Build Step Frontend**: Responsive vanilla HTML5/CSS3/ES6 interface with dark mode, accessibility, and multilingual support (English, Hindi, Kannada).

---

## 🏗️ Architecture

```mermaid
graph TD
    subgraph "Frontend Clients (Vanilla JS / CSS)"
        PassengerApp["Passenger Web App<br/>(static/index.html)"]
        TTEDashboard["TTE Portal<br/>(static/tte.html)"]
        DigitalSlip["Exchange Slip & QR<br/>(static/slip.html)"]
        DemoTools["Demo Controls<br/>(static/demo.html)"]
    end

    subgraph "FastAPI Backend (Asynchronous)"
        API["FastAPI REST & WebSocket Hub (/ws)"]
        AuthRouter["Auth & OTP Router (/api/otp)"]
        MatchEngine["Matching Engine (/api/match)"]
        ConsentRouter["Consent & State Machine (/api/requests)"]
        TTERouter["TTE Router (/api/tte)"]
        GroupRouter["Group Router (/api/group-requests)"]
        SimulationRouter["Simulation & Expiry (/api/demo)"]
    end

    subgraph "Business Logic Services"
        AuditSvc["Audit Service (AuditLog)"]
        NotifySvc["Notify Service (SMS/Email/App)"]
        StateSvc["State Transition Validator"]
        WSManager["WebSocket Connection Manager"]
        ExpirySvc["Train Expiry & Seating Engine"]
    end

    subgraph "Data Storage"
        DB[("SQLite (Default) / PostgreSQL<br/>SQLAlchemy 2.0 Async")]
    end

    PassengerApp --> API
    TTEDashboard --> API
    DigitalSlip --> API
    DemoTools --> API

    API --> AuthRouter
    API --> MatchEngine
    API --> ConsentRouter
    API --> TTERouter
    API --> GroupRouter
    API --> SimulationRouter

    ConsentRouter --> StateSvc
    ConsentRouter --> AuditSvc
    ConsentRouter --> NotifySvc
    ConsentRouter --> WSManager

    TTERouter --> AuditSvc
    TTERouter --> WSManager
    SimulationRouter --> ExpirySvc
    ExpirySvc --> WSManager

    AuthRouter --> DB
    ConsentRouter --> DB
    TTERouter --> DB
    AuditSvc --> DB
```

---

## 🚀 Quickstart Guide

### 1. Requirements
- Python 3.11+
- Virtualenv (`python3 -m venv .venv`)

### 2. Installation & Setup
```bash
# Clone and enter directory
git clone https://github.com/your-repo/RailMitra.git
cd RailMitra

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
- **Passenger App**: [http://127.0.0.1:8000/static/index.html](http://127.0.0.1:8000/static/index.html)
- **TTE Portal**: [http://127.0.0.1:8000/static/tte.html](http://127.0.0.1:8000/static/tte.html)
- **Demo Controls**: [http://127.0.0.1:8000/static/demo.html](http://127.0.0.1:8000/static/demo.html)
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## ⚙️ Configuration & Environment Variables

Create a `.env` file in the root directory to customize parameters:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `APP_NAME` | `RailMitra` | Application display title |
| `APP_VERSION` | `0.1.0` | Semantic version string |
| `DEMO_MODE` | `True` | Displays OTP in top banner and console |
| `TTE_KEY` | `tte-demo-key` | Shared secret header required for TTE endpoints (`X-TTE-Key`) |
| `SECRET_KEY` | `railmitra-super-secret-salt-2026` | Salt for slip cryptographic verification tokens |
| `OTP_EXPIRY_MINUTES` | `5` | Simulated OTP expiration window |
| `OTP_MAX_ATTEMPTS` | `3` | Maximum failed OTP attempts before lockout |
| `OTP_LOCK_MINUTES` | `10` | Lockout duration on 3 consecutive failed attempts |
| `REQUEST_LIMIT` | `3` | Maximum exchange requests per journey per passenger |
| `DATABASE_URL` | `sqlite+aiosqlite:///./railmitra.db` | Async database connection string |

### PostgreSQL Configuration Option
To connect to an external PostgreSQL instance, set:
```bash
DATABASE_URL=postgresql+asyncpg://railmitra_user:securepassword@localhost:5432/railmitra_db
```

---

## 🧪 Running Automated Tests

Run the full pytest suite (38 automated unit, integration, and security tests):
```bash
source .venv/bin/activate
pytest -v
```

---

## 📁 Project Structure

```
RailMitra/
├── app/
│   ├── main.py                  # FastAPI app shell & route registrations
│   ├── config.py                # Pydantic v2 settings & environment variables
│   ├── database.py              # Async engine & sessionmaker (aiosqlite / asyncpg)
│   ├── errors.py                # Standardized exception handlers
│   ├── models.py                # Declarative SQLAlchemy ORM models
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── seed.py                  # Idempotent seed data with worked personas
│   ├── routers/
│   │   ├── auth.py              # OTP dispatch & verification, session token dependency
│   │   ├── consent.py           # Incoming requests, accept/decline, cancellation
│   │   ├── groups.py            # Family multi-berth exchange requests
│   │   ├── journey.py           # Journey validation against simulated charts
│   │   ├── matching.py          # Pure matching API adapter
│   │   ├── notifications.py     # In-app passenger notifications
│   │   ├── requests.py          # Peer exchange creation & quota management
│   │   ├── simulation.py        # Station advancement & effective seating
│   │   ├── slip.py              # Digital slip & public verification endpoint
│   │   ├── tte.py               # TTE dashboard, reviews & audit trail
│   │   └── websocket.py         # Real-time WebSocket connection endpoint
│   ├── services/
│   │   ├── audit.py             # Immutable audit trail logger
│   │   ├── expiry.py            # Station-by-station train movement & expiry logic
│   │   ├── groups.py            # Family group request coordination & limit checks
│   │   ├── limits.py            # 3-request journey quota & duplicate target checks
│   │   ├── matching.py          # Pure algorithmic candidate ranking & protection
│   │   ├── notify.py            # In-app and simulated console notifications
│   │   ├── otp.py               # OTP generation, salted SHA-256 hashing & lockouts
│   │   └── state.py             # Strict request state transition machine
│   └── ws/
│       └── manager.py           # WebSocket in-memory connection manager & broadcaster
├── static/
│   ├── css/
│   │   └── app.css              # Design system with light/dark tokens & print styles
│   ├── js/
│   │   ├── api.js               # Centralized async API client (session-isolated)
│   │   ├── i18n.js              # Multilingual translations (EN, HI, KN)
│   │   ├── qrcode.js            # Standalone zero-dependency SVG QR generator
│   │   ├── ui.js                # Toasts, modals, route visualizer & theme toggler
│   │   └── ws.js                # WebSocket client with heartbeat & polling fallback
│   ├── index.html               # Passenger application
│   ├── tte.html                 # TTE inspection dashboard
│   ├── slip.html                # Digital exchange slip with print layout
│   └── demo.html                # Hackathon simulation control panel
├── tests/
│   ├── test_core.py             # Auth, lockout, sessions, and request limits
│   ├── test_flow.py             # End-to-end exchange lifecycle, state machine, and expiry
│   ├── test_groups.py           # Family group requests & quota validation
│   ├── test_matching_unit.py    # Pure matching engine unit tests
│   ├── test_seed.py             # Seed data and reservation integrity
│   ├── test_tte.py              # TTE authentication, reviews, and audit logs
│   └── test_ws.py               # WebSocket connection & heartbeat tests
├── docs/
│   ├── screenshots/             # End-to-end browser verification captures
│   └── implementation_plan.md   # Architectural blueprint
├── DEMO_SCRIPT.md               # 3-minute judge walkthrough guide
├── PITCH.md                     # Problem, solution, differentiators & roadmap
├── PROJECT_CONTEXT.md           # Product specification and progress tracker
└── requirements.txt             # Python dependencies
```

---

## 🛡️ License & Disclaimers

This software is developed strictly as a hackathon minimum viable prototype. It is not an official Indian Railways or IRCTC product. Official deployment would require formal authorization and direct integration with CRIS (Centre for Railway Information Systems).
