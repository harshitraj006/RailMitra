# RailMitra – 3-Minute Judge-Friendly Demo Walkthrough ⏱️

**Target Time:** 3 minutes  
**Goal:** Demonstrate the complete end-to-end seat exchange flow, showing independent consent, TTE oversight, cryptographic QR slips, anti-spam protections, and station-by-station expiry.

---

## 🎬 Prerequisites Setup (10 seconds before start)
1. Ensure the backend server is running: `http://127.0.0.1:8000`.
2. Open two browser windows side by side (e.g. Window 1: Asha / Window 2: Kiran) or use two tabs.
3. Open a third tab for the **TTE Dashboard**: `http://127.0.0.1:8000/static/tte.html`.
4. Open a fourth tab for **Demo Controls**: `http://127.0.0.1:8000/static/demo.html`.

---

## 🏁 Walkthrough Steps

### 0:00 – 0:30 | The Hook & Problem Statement
- **Action:** Open `http://127.0.0.1:8000/static/index.html`. Point out the clean Indian Railways-inspired design, dark mode toggle, and language selector (English / Hindi / Kannada).
- **Talking Point:**  
  > *"Every day across Indian Railways, families and co-passengers ask strangers to swap berths informally. These swaps are unrecorded, invisible to the TTE, pressure solo travelers, cause disputes when passengers board later, and split families across coaches. RailMitra replaces informal awkwardness with a secure, consent-based digital exchange platform."*

---

### 0:30 – 1:00 | Act 1: Passenger Login & Algorithmic Matching (Asha)
- **Action:**
  1. Click the preset button **"Asha (S2-14)"** and click **"Validate Journey & Request OTP"**.
  2. Explain: *"The system validates the simulated PNR `PNR1000001` against Train 12951. An OTP is simulated and displayed in the demo banner."*
  3. Enter the 6-digit OTP and click **"Verify & Enter"**.
- **Talking Point:**  
  > *"On Asha's home dashboard, she sees her coach (S2, Berth 14 Upper), her route tracker from S1 to S4, her co-passengers in her booking, and her request quota: 0 of 3 used."*
- **Action:**
  4. Scroll down to **"Eligible Exchange Candidates"**.
  5. Point out **Kiran Patel (Coach S2, Berth 43 Upper)** classified with a green **"Best Match"** badge and human-readable reason (*"Same destination S4 and exact feasible segment S1 to S4"*).
  6. Point out how senior citizen **Meera Sharma (Age 62)** is never offered an uncomfortable berth swap.
  7. Click **"Request Exchange"** on Kiran's card.
  8. In the confirmation modal, note the segment expiry notice: *"Valid until S4, then return to Berth 14"*. Click **"Send Request"**.
  9. Show that Asha's quota immediately updates to **"1 of 3 requests used"**.

---

### 1:00 – 1:30 | Act 2: Independent Consent from Co-Passenger (Kiran)
- **Action:**
  1. Open a new window or incognito tab (or log out and quick-login as **Kiran (S2-43)**).
  2. Validate PNR `PNR1000003`, enter OTP, and click **"Verify & Enter"**.
  3. Click on the **"Incoming Requests"** tab.
- **Talking Point:**  
  > *"Because session tokens are isolated per tab, Kiran reviews the exact details independently on his own device. He sees Asha's offer: Coach S2, Berth 14 in exchange for his Coach S2, Berth 43."*
- **Action:**
  4. Click **"Accept Exchange"**.
  5. The status changes to **"Accepted by Passenger (Awaiting TTE Review)"**.

---

### 1:30 – 2:00 | Act 3: Train Ticket Examiner (TTE) Authorization
- **Action:**
  1. Switch to the **TTE Dashboard** tab (`http://127.0.0.1:8000/static/tte.html`).
  2. Key `tte-demo-key` is already prefilled. Point out the live request card:
     - Side-by-side comparison of **Original vs Proposed** allocation.
     - Both passenger consent ticks: Requester ✅, Target ✅.
- **Talking Point:**  
  > *"Crucially, the TTE cannot approve an exchange unless BOTH passengers have independently consented. If consent is missing, the approve button is disabled with an explanatory tooltip."*
- **Action:**
  3. Click **"Approve Exchange ✓"**, type an optional note (*"ID verified on train"*), and confirm.
  4. Switch to the **"Coach Seating Chart"** tab and select **Coach S2**: demonstrate how effective seating dynamically updates, displaying Asha and Kiran in their new exchanged berths!

---

### 2:00 – 2:30 | Act 4: Digital Exchange Slip & Cryptographic QR
- **Action:**
  1. Click **"Inspect Slip & QR 🎫"** (or open `http://127.0.0.1:8000/static/slip.html?request_id=1`).
  2. Point out the official digital slip:
     - Record Slip ID, train number, passenger names, original vs exchanged berth.
     - Clear disclaimer: *"RailMitra record – not an official Indian Railways document."*
     - The client-side rendered **QR Code**.
  3. Click **"Open Public Verification Page ↗"** (opens `/api/verify/{token}`).
- **Talking Point:**  
  > *"Anyone—a fellow passenger or checking staff—can scan the QR code to verify the cryptographic token. Notice that our public verification API strictly respects privacy: zero PNR numbers, zero phone numbers, and zero emails are exposed."*

---

### 2:30 – 3:00 | Act 5: Train Movement & Automatic Expiry Simulation
- **Action:**
  1. Switch to **Demo Controls** (`http://127.0.0.1:8000/static/demo.html`).
  2. Look at the train position tracker (currently at **S1**).
  3. Click **"Advance to S4"** (the destination of Kiran and expiry station of the exchange).
  4. Notice the result box: *"Train is now at S4. Expired exchanges: 1. Notifications dispatched: 2."*
  5. Switch back to Asha's tab: show the real-time notification pop-up via WebSocket:
     > *"Your seat exchange has expired. Please return to your original berth: Coach S2, Berth 14."*
  6. Switch back to the TTE Coach Seating chart: show that berths have reverted to original allocations!

---

### 3:00 | Wrap-up Pitch Summary
- **Talking Point:**  
  > *"In under 3 minutes, we demonstrated a complete lifecycle: algorithmic matching with vulnerable passenger safeguards, independent double-consent, anti-spam caps, TTE authorization, cryptographic QR slips, and automatic segment expiry. RailMitra provides dignity, safety, and coordination to train travel across India."*
