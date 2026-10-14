# RailMitra – Smart Railway Seat Exchange & Family Seating System

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **PROTOTYPE BOUNDARY DISCLAIMER:**  
> Prototype using a simulated reservation dataset. Not the official Indian Railways reservation chart or database. Official use would require authorization from Indian Railways. The app never claims live railway access and never writes to official systems. Match categories are project-defined preferences, not official railway rules.

---

## 🚆 Overview

When families book train tickets together in India, they often end up with berths scattered across different coaches or distant bays. Co-passengers frequently swap berths informally, leading to unrecorded seat occupancy, disputes with late-boarding passengers, lack of independent consent, and zero visibility for the Train Ticket Examiner (TTE).

**RailMitra** solves this by providing:
1. **Consent-Based Seat Exchanges:** Co-passengers receive digital requests displaying exact berth details and independently confirm via OTP verification.
2. **Deterministic Matching Engine:** Identifies *Best Matches* (identical destination and feasible segment) and *Possible Matches* (destination differing by 1–3 stops), prioritizing co-coach proximity and respecting vulnerable passengers (e.g., age 60+ or requiring lower berths).
3. **Automated Segment Expiry:** Exchanges expire at the earlier destination, notifying passengers to return to their original berths before new passengers board.
4. **TTE Verification & Dashboard:** Train Ticket Examiners inspect dual-consented requests, approve/reject them, and view an immutable audit trail.
5. **Family Group Coordination:** Coordinated multi-seat swaps executed collectively with quota tracking.

---

## 🛠️ Technology Stack

- **Backend:** Python 3.11+, FastAPI (async), Uvicorn
- **Database / ORM:** SQLAlchemy 2.0 (Async), SQLite (`aiosqlite`) for local dev, PostgreSQL (`asyncpg`) for production
- **Validation:** Pydantic v2 & Pydantic Settings
- **Testing:** Pytest, Pytest-Asyncio, HTTPX
- **Frontend (Later Parts):** Modern HTML5, Vanilla CSS3, JavaScript served via `/static`

---

## 📁 Project Structure

```
railmitra/
├── app/
│   ├── __init__.py
│   ├── config.py           # Application settings & environment variables
│   ├── database.py         # Async SQLAlchemy 2.x engine & session
│   ├── errors.py           # Standardized error responses ({detail, code})
│   ├── models.py           # SQLAlchemy declarative ORM models
│   ├── schemas.py          # Pydantic v2 request & response schemas
│   ├── seed.py             # Idempotent database seeder with worked examples
│   ├── main.py             # FastAPI app shell, lifespan, middleware, health
│   ├── routers/            # API route controllers (Parts 2 & 3)
│   ├── services/           # Business logic & matching engine (Parts 2 & 3)
│   └── ws/                 # Realtime WebSocket handlers (Part 3)
├── static/                 # Static HTML/CSS/JS assets
├── tests/
│   ├── __init__.py
│   └── test_seed.py        # Seed & worked-example verification tests
├── docs/
│   └── implementation_plan.md # Architectural plan, data model, APIs, screens
├── .env.example            # Sample environment variables
├── .gitignore              # Git ignore rules
├── docker-compose.yml      # Optional PostgreSQL service
├── PROJECT_CONTEXT.md      # Single source of truth & business rules
├── requirements.txt        # Python package dependencies
└── README.md               # Project documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Setup Virtual Environment & Install Dependencies
```bash
# Clone the repository and navigate inside
git clone <repo-url>
cd RailMitra

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the sample environment file:
```bash
cp .env.example .env
```
Default configuration parameters:
- `DEMO_MODE=true`
- `TTE_KEY=tte-demo-key`
- `OTP_EXPIRY_MINUTES=5`
- `OTP_MAX_ATTEMPTS=3`
- `OTP_LOCK_MINUTES=10`
- `REQUEST_LIMIT=3`
- `DATABASE_URL=sqlite+aiosqlite:///./railmitra.db`

### 4. Run the Application
```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```
Open your browser and navigate to:
- **Application Landing:** [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Probe:** [http://localhost:8000/health](http://localhost:8000/health)

### 5. Running with PostgreSQL (Docker Compose)
To use PostgreSQL instead of SQLite:
```bash
docker compose up -d
```
Update `DATABASE_URL` in `.env`:
```env
DATABASE_URL=postgresql+asyncpg://railmitra:railmitra_password@localhost:5432/railmitra
```

---

## 🧪 Running Tests

Execute the automated test suite with pytest:
```bash
source .venv/bin/activate
pytest -v
```

---

## 📋 Worked Example Dataset

The seed dataset incorporates the reference hackathon scenario:
- **Asha Sharma** (`PNR1000001`): Coach S2, Berth 14 (UPPER), S1 → S4 (Family group: *Asha's family*)
- **Meera Sharma** (`PNR1000002`): Coach S2, Berth 41 (LOWER, age 62), S1 → S4 (*Asha's family*)
- **Kiran Patel** (`PNR1000003`): Coach S2, Berth 43 (UPPER), S1 → S4 (Best Match for Asha)
- **Ravi Verma** (`PNR1000004`): Coach S2, Berth 46 (LOWER), S1 → S5 (Possible Match for Asha)
- **Vikram Singh** (`PNR1000005`): Coach S2, Berth 50, S1 → S3 (Expires at S3)
- **Neha Gupta** (`PNR1000006`): Coach S2, Berth 25, S2 → S4
- **Sunita Roy** (`PNR1000007`): Coach S2, Berth 32, S3 → S5 (Minimal overlap)
- **Verma Family** (5 passengers): Split across coaches S1 and S3
- **Out-of-Scope Passengers:** `PNR1000098` on Train T-202 and `PNR1000099` on a future journey date.
