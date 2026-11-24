# ResQNet — K! Hacks 4.0 Demo

> **Agentic AI-Powered Disaster Relief Coordination & Resource Management System with Integrated Animal Emergency Response**  
> Team: **OBSIDYNE** (Amrita Vishwa Vidyapeetham, Chennai)  
> Track: Disaster Relief & Humanitarian Tech  
> References: Matches architecture, user roles, 6-step workflow, and design in `Obsidyne_KHacks4.pptx`.

---

## 🚀 Quick Start (Zero Setup)

Run the single startup script to automatically initialize the SQLite database, seed Tamil Nadu flood emergency scenarios, and serve the FastAPI REST API + React PWA:

```bash
python start.py
```

Then open your browser at:
- **Application & Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive API Docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

To run the automated end-to-end smoke tests:
```bash
python tests/smoke_test.py
```

---

## 🔑 Demo Roles & Pre-Seeded Credentials

| Role | Name | Email | Organization / Focus |
|---|---|---|---|
| **Chief Coordinator** | Dr. Rajesh Sundaram | `coordinator@resqnet.org` | Tamil Nadu Disaster Management Authority (TNDMA) |
| **Citizen (Affected)** | Murugan Velu | `citizen@resqnet.org` | Village A Resident Welfare (Madhavaram Flood Basin) |
| **NGO Relief Officer** | Red Cross Relief TN | `ngo@resqnet.org` | Indian Red Cross Society Chennai Hub |
| **Field Volunteer** | Karthik Raja | `volunteer@resqnet.org` | First Aid, Boat Operations, Food Distribution |
| **Certified Veterinarian** | Dr. Shalini Swaminathan (BVSc) | `vet@resqnet.org` | TANUVAS / Blue Cross (`TN-VET-2024-9982`) |

---

## 🔄 6-Step Multi-Agent Workflow (Slide 3 & 4)

1. **Report:** Citizens submit human or animal emergencies via the PWA (or queue offline).
2. **Validate:** `Request Analysis Agent` extracts structured fields and flags spatial/semantic duplicates.
3. **Prioritise:** `Priority Assessment Agent` scores urgency (Critical, High, Medium, Low) and marks `requires_human_review: true`.
4. **Match:**
   - `Resource Allocation Agent`: Matches supplies from NGO inventory and alerts when shortages occur.
   - `Volunteer Coordination Agent`: Matches responder skills & proximity; **strictly enforces certified veterinary responders (`is_vet = 1`, `vet_license_no`) for animal emergency cases**.
5. **Dispatch:** **Human Approval Gate** — inventory deduction and responder dispatches remain blocked until the Coordinator clicks **Approve**. Once approved, stock is reserved and a delivery QR code package is minted.
6. **Acknowledge:** Recipient confirms delivery via QR scan / digital signature, completing the traceable chain of custody and closing the ticket.

---

## 📱 4 Integrated React PWA Interfaces

1. **Coordinator Dashboard & Map:** Live OpenStreetMap / Leaflet map, side-by-side specialist AI JSON recommendations, stock shortage warnings, and Human-in-the-Loop decision gate.
2. **Citizen Emergency Portal:** Human & Animal emergency intake forms with live **"Simulate Offline Mode"** toggle, local queue storage in `localStorage`, auto-sync when back online, and QR delivery acknowledgement.
3. **NGO Inventory Console:** Real-time relief warehouse stock ledger with automated reservation on coordinator approval.
4. **Volunteer & Vet Responder App:** Field responder view with skill-matched tasks and QR code pass simulator for on-site delivery verification.
5. **End-to-End Audit Drawer:** Tamper-evident ledger tracking all human approval events (`request_events`) and AI outputs (`agent_runs`).
