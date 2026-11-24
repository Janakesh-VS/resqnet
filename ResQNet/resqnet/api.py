import os
import sys
import json
import uuid
import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

VENV_PKGS = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv", "Lib", "site-packages")
if os.path.exists(VENV_PKGS) and VENV_PKGS not in sys.path:
    sys.path.append(VENV_PKGS)

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse

from resqnet.db import get_db_connection, init_db, DB_PATH
from resqnet.pipeline import ChiefCoordinatorPipeline

app = FastAPI(
    title="ResQNet API",
    description="Agentic AI-Powered Disaster Relief Coordination and Resource Management System with Integrated Animal Emergency Response",
    version="1.0.0"
)

# Enable CORS for React PWA frontend on any port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = ChiefCoordinatorPipeline()

# Pydantic Request Models
class EmergencyReportCreate(BaseModel):
    type: str = "human" # human or animal
    title: str
    description: Optional[str] = ""
    disaster_type: Optional[str] = "Flood"
    location_name: str
    latitude: float
    longitude: float
    affected_families: Optional[int] = 0
    affected_individuals: Optional[int] = 0
    animal_species: Optional[str] = None
    animal_count: Optional[int] = 0
    resources_needed: Optional[List[str]] = []
    created_by: Optional[str] = "USR_CITIZEN1"

class CoordinatorApprovalPayload(BaseModel):
    coordinator_id: str = "USR_COORD"
    approved_priority: Optional[str] = None
    approved_allocations: Optional[List[Dict[str, Any]]] = None
    approved_dispatches: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = ""

class CoordinatorOverridePayload(BaseModel):
    coordinator_id: str = "USR_COORD"
    override_priority: Optional[str] = None
    override_status: Optional[str] = "Dispatched"
    reason: str
    custom_instructions: Optional[str] = ""

class DeliveryAcknowledgePayload(BaseModel):
    qr_code: str
    recipient_ack: bool = True
    ack_signature: Optional[str] = "Citizen Signature (Confirmed)"
    ack_notes: Optional[str] = ""

class InventoryItemCreate(BaseModel):
    ngo_id: str
    item_name: str
    category: str
    quantity: int
    unit: str = "units"
    location_name: str
    latitude: Optional[float] = 13.0827
    longitude: Optional[float] = 80.2707

@app.on_event("startup")
async def on_startup():
    await init_db()

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "system": "ResQNet Agentic Coordination", "db": "SQLite (aiosqlite)"}

# ----------------- USERS -----------------
@app.get("/api/users")
async def get_users(role: Optional[str] = None):
    db = await get_db_connection()
    try:
        if role:
            cursor = await db.execute("SELECT * FROM users WHERE role = ?", (role,))
        else:
            cursor = await db.execute("SELECT * FROM users")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()

# ----------------- REQUESTS & WORKFLOW -----------------
@app.get("/api/requests")
async def list_requests(status: Optional[str] = None, type: Optional[str] = None):
    db = await get_db_connection()
    try:
        query = "SELECT * FROM requests WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if type:
            query += " AND type = ?"
            params.append(type)
        query += " ORDER BY created_at DESC"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("resources_needed"):
                try:
                    d["resources_needed"] = json.loads(d["resources_needed"])
                except Exception:
                    pass
            result.append(d)
        return result
    finally:
        await db.close()

@app.get("/api/requests/{request_id}")
async def get_request_detail(request_id: str):
    db = await get_db_connection()
    try:
        cursor = await db.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        req = await cursor.fetchone()
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        req_dict = dict(req)
        if req_dict.get("resources_needed"):
            try:
                req_dict["resources_needed"] = json.loads(req_dict["resources_needed"])
            except Exception:
                pass

        # Events
        c_events = await db.execute("SELECT * FROM request_events WHERE request_id = ? ORDER BY created_at ASC", (request_id,))
        events = [dict(e) for e in await c_events.fetchall()]

        # Agent runs
        c_runs = await db.execute("SELECT * FROM agent_runs WHERE request_id = ? ORDER BY created_at ASC", (request_id,))
        agent_runs = []
        for r in await c_runs.fetchall():
            run_dict = dict(r)
            try:
                run_dict["output_data"] = json.loads(run_dict["output_data"])
            except Exception:
                pass
            agent_runs.append(run_dict)

        # Allocations
        c_alloc = await db.execute("SELECT * FROM allocations WHERE request_id = ?", (request_id,))
        allocations = [dict(a) for a in await c_alloc.fetchall()]

        # Dispatches
        c_disp = await db.execute("""
            SELECT d.*, v.name as volunteer_name, v.phone as volunteer_phone, v.vet_license_no
            FROM dispatches d
            JOIN volunteers v ON d.volunteer_id = v.id
            WHERE d.request_id = ?
        """, (request_id,))
        dispatches = [dict(d) for d in await c_disp.fetchall()]

        # Packages
        c_pkg = await db.execute("SELECT * FROM packages WHERE request_id = ?", (request_id,))
        packages = [dict(p) for p in await c_pkg.fetchall()]

        return {
            "request": req_dict,
            "events": events,
            "agent_runs": agent_runs,
            "allocations": allocations,
            "dispatches": dispatches,
            "packages": packages
        }
    finally:
        await db.close()

@app.post("/api/requests")
async def create_request(payload: EmergencyReportCreate):
    """
    Step 1 (Report) & Trigger Agent Pipeline (Validate, Prioritise, Match, Propose)
    """
    db = await get_db_connection()
    try:
        req_id = f"REQ{int(datetime.datetime.now().timestamp() * 1000) % 1000000:06d}"
        resources_json = json.dumps(payload.resources_needed or [])

        # Fetch existing requests for duplicate check
        c_ex = await db.execute("SELECT id, location_name, latitude, longitude, title FROM requests")
        existing = [dict(r) for r in await c_ex.fetchall()]

        # Fetch inventories and volunteers for match
        c_inv = await db.execute("SELECT * FROM inventory_items")
        inv_list = [dict(r) for r in await c_inv.fetchall()]

        c_vol = await db.execute("SELECT * FROM volunteers")
        vol_list = [dict(r) for r in await c_vol.fetchall()]

        raw_req = {
            "id": req_id,
            "type": payload.type,
            "title": payload.title,
            "description": payload.description,
            "disaster_type": payload.disaster_type,
            "location_name": payload.location_name,
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "affected_families": payload.affected_families,
            "affected_individuals": payload.affected_individuals,
            "animal_species": payload.animal_species,
            "animal_count": payload.animal_count,
            "resources_needed": payload.resources_needed
        }

        # Run multi-agent pipeline
        pipeline_output = pipeline.execute_full_pipeline(raw_req, existing, inv_list, vol_list)
        step_outputs = pipeline_output["step_outputs"]

        analysis = step_outputs["1_request_analysis"]
        priority_res = step_outputs["2_priority_assessment"]
        resource_res = step_outputs["3_resource_allocation"]
        vol_res = step_outputs["4_volunteer_coordination"]

        is_duplicate = analysis["duplicate_check"]["is_duplicate"]
        dup_of = analysis["duplicate_check"]["duplicate_of"]
        rec_priority = priority_res["recommended_priority"]

        # Insert Request
        await db.execute("""
            INSERT INTO requests (
                id, type, title, description, disaster_type, status, priority,
                location_name, latitude, longitude, affected_families, affected_individuals,
                animal_species, animal_count, resources_needed, duplicate_flag, duplicate_of,
                requires_human_review, created_by
            ) VALUES (?, ?, ?, ?, ?, 'Reported', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            req_id, payload.type, payload.title, payload.description, payload.disaster_type,
            rec_priority, payload.location_name, payload.latitude, payload.longitude,
            payload.affected_families, payload.affected_individuals,
            payload.animal_species, payload.animal_count,
            resources_json, 1 if is_duplicate else 0, dup_of, payload.created_by
        ))

        # Log Report event
        await db.execute("""
            INSERT INTO request_events (request_id, event_type, actor_id, actor_role, details)
            VALUES (?, 'Report', ?, 'citizen', ?)
        """, (req_id, payload.created_by, json.dumps({"title": payload.title, "type": payload.type})))

        # Log Agent runs
        agent_steps = [
            ("Request Analysis", "Request Analysis Agent", analysis),
            ("Priority Assessment", "Priority Assessment Agent", priority_res),
            ("Resource Allocation", "Resource Allocation Agent", resource_res),
            ("Volunteer Coordination", "Volunteer Coordination Agent", vol_res),
            ("Delivery Monitor", "Delivery Monitoring Agent", step_outputs["5_delivery_monitor"])
        ]
        for sname, aname, data in agent_steps:
            await db.execute("""
                INSERT INTO agent_runs (id, request_id, step_name, agent_name, input_data, output_data, human_approved)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
            """, (f"RUN_{req_id}_{sname.replace(' ', '_')}", req_id, sname, aname, json.dumps(raw_req), json.dumps(data)))

        await db.commit()

        return {
            "status": "success",
            "request_id": req_id,
            "pipeline_verdict": pipeline_output["chief_coordinator_verdict"],
            "agent_runs": step_outputs
        }
    finally:
        await db.close()

# ----------------- HUMAN APPROVAL GATE -----------------
@app.post("/api/requests/{request_id}/approve")
async def approve_request_and_dispatch(request_id: str, payload: CoordinatorApprovalPayload):
    """
    HUMAN APPROVAL GATE:
    Coordinator approves AI recommendations. This atomic action:
    1. Updates request status to 'Dispatched' (or 'Matched')
    2. Enforces inventory deduction / reservations
    3. Confirms volunteer / certified vet dispatch
    4. Generates delivery QR package
    5. Logs human approval into agent_runs and request_events
    """
    db = await get_db_connection()
    try:
        cursor = await db.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        req = await cursor.fetchone()
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        req_dict = dict(req)

        # 1. Update priority if coordinator adjusted it
        final_priority = payload.approved_priority or req_dict["priority"]
        await db.execute("""
            UPDATE requests
            SET priority = ?, status = 'Dispatched', requires_human_review = 0, approved_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (final_priority, payload.coordinator_id, request_id))

        # 2. Process Approved Allocations and reserve stock
        created_allocations = []
        if payload.approved_allocations:
            for item in payload.approved_allocations:
                alloc_id = f"ALC_{uuid.uuid4().hex[:8]}"
                item_id = item.get("item_id")
                qty = int(item.get("allocated_quantity", 0))
                if item_id and qty > 0:
                    # Deduct/reserve from inventory
                    await db.execute("""
                        UPDATE inventory_items
                        SET reserved_quantity = reserved_quantity + ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (qty, item_id))

                    await db.execute("""
                        INSERT INTO allocations (id, request_id, item_id, item_name, quantity, status, approved_by, notes)
                        VALUES (?, ?, ?, ?, ?, 'Approved', ?, ?)
                    """, (alloc_id, request_id, item_id, item.get("item_name", "Supply"), qty, payload.coordinator_id, payload.notes))
                    created_allocations.append({"id": alloc_id, "item": item.get("item_name"), "quantity": qty})

        # 3. Process Approved Dispatches
        created_dispatches = []
        dispatch_id = None
        if payload.approved_dispatches:
            for d in payload.approved_dispatches:
                dispatch_id = f"DSP_{uuid.uuid4().hex[:8]}"
                vol_id = d.get("volunteer_id")
                role_type = d.get("role_type", "volunteer")
                await db.execute("""
                    INSERT INTO dispatches (id, request_id, volunteer_id, assigned_by, status, role_type, instructions)
                    VALUES (?, ?, ?, ?, 'Assigned', ?, ?)
                """, (dispatch_id, request_id, vol_id, payload.coordinator_id, role_type, payload.notes or "Urgent flood dispatch"))
                
                # Update volunteer availability
                await db.execute("UPDATE volunteers SET is_available = 0 WHERE id = ?", (vol_id,))
                created_dispatches.append({"id": dispatch_id, "volunteer_id": vol_id, "role_type": role_type})

        # 4. Generate QR Package for Delivery Acknowledgment
        pkg_id = f"PKG_{uuid.uuid4().hex[:8]}"
        qr_code = f"RESQ-{request_id}-{uuid.uuid4().hex[:6].upper()}"
        items_summary = json.dumps(created_allocations)
        await db.execute("""
            INSERT INTO packages (id, request_id, dispatch_id, qr_code, items_summary, delivery_status, recipient_ack)
            VALUES (?, ?, ?, ?, ?, 'Prepared', 0)
        """, (pkg_id, request_id, dispatch_id, qr_code, items_summary))

        # 5. Log Approval Event & Agent Run Status
        await db.execute("""
            INSERT INTO request_events (request_id, event_type, actor_id, actor_role, details)
            VALUES (?, 'HumanApprove', ?, 'coordinator', ?)
        """, (request_id, payload.coordinator_id, json.dumps({
            "approved_priority": final_priority,
            "allocations_count": len(created_allocations),
            "dispatches_count": len(created_dispatches),
            "qr_code": qr_code,
            "notes": payload.notes
        })))

        await db.execute("""
            UPDATE agent_runs
            SET human_approved = 1, human_notes = ?
            WHERE request_id = ?
        """, (payload.notes or "Approved by Human Coordinator", request_id))

        await db.commit()

        return {
            "status": "approved_and_dispatched",
            "request_id": request_id,
            "priority": final_priority,
            "package_qr": qr_code,
            "allocations": created_allocations,
            "dispatches": created_dispatches
        }
    finally:
        await db.close()

@app.post("/api/requests/{request_id}/override")
async def override_request(request_id: str, payload: CoordinatorOverridePayload):
    """
    HUMAN OVERRIDE GATE:
    Coordinator manually overrides AI recommendation, urgency tier, or workflow routing.
    Records immutable reason to request_events and agent_runs.
    """
    db = await get_db_connection()
    try:
        cursor = await db.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        req = await cursor.fetchone()
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        req_dict = dict(req)

        new_priority = payload.override_priority or req_dict["priority"]
        new_status = payload.override_status or "Dispatched"

        await db.execute("""
            UPDATE requests
            SET priority = ?, status = ?, requires_human_review = 0, approved_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_priority, new_status, payload.coordinator_id, request_id))

        # Log HumanOverride event
        await db.execute("""
            INSERT INTO request_events (request_id, event_type, actor_id, actor_role, details)
            VALUES (?, 'HumanOverride', ?, 'coordinator', ?)
        """, (request_id, payload.coordinator_id, json.dumps({
            "previous_priority": req_dict["priority"],
            "new_priority": new_priority,
            "new_status": new_status,
            "reason": payload.reason,
            "custom_instructions": payload.custom_instructions
        })))

        await db.execute("""
            UPDATE agent_runs
            SET human_approved = 0, human_notes = ?
            WHERE request_id = ?
        """, (f"OVERRIDDEN by Coordinator: {payload.reason}", request_id))

        await db.commit()

        return {
            "status": "overridden",
            "request_id": request_id,
            "new_priority": new_priority,
            "new_status": new_status,
            "reason": payload.reason
        }
    finally:
        await db.close()

# ----------------- RECIPIENT ACKNOWLEDGEMENT & QR -----------------
@app.post("/api/deliveries/acknowledge")
async def acknowledge_delivery(payload: DeliveryAcknowledgePayload):
    """
    Step 6 (Acknowledge): Recipient confirms delivery via QR code scan or portal button.
    This closes the verified chain of custody and transitions ticket to 'Acknowledged' -> 'Closed'.
    """
    db = await get_db_connection()
    try:
        cursor = await db.execute("SELECT * FROM packages WHERE qr_code = ?", (payload.qr_code,))
        pkg = await cursor.fetchone()
        if not pkg:
            raise HTTPException(status_code=404, detail="Package QR code invalid or not found")
        pkg_dict = dict(pkg)
        req_id = pkg_dict["request_id"]

        now = datetime.datetime.now().isoformat()
        # Mark package acknowledged
        await db.execute("""
            UPDATE packages
            SET delivery_status = 'Acknowledged', recipient_ack = 1, ack_signature = ?, ack_notes = ?, ack_timestamp = ?
            WHERE qr_code = ?
        """, (payload.ack_signature, payload.ack_notes, now, payload.qr_code))

        # Mark request Acknowledged / Closed
        await db.execute("""
            UPDATE requests
            SET status = 'Acknowledged', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (req_id,))

        # Free volunteer
        if pkg_dict.get("dispatch_id"):
            await db.execute("""
                UPDATE dispatches SET status = 'Completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (pkg_dict["dispatch_id"],))
            cursor_d = await db.execute("SELECT volunteer_id FROM dispatches WHERE id = ?", (pkg_dict["dispatch_id"],))
            disp_row = await cursor_d.fetchone()
            if disp_row:
                await db.execute("UPDATE volunteers SET is_available = 1 WHERE id = ?", (disp_row["volunteer_id"],))

        # Log event
        await db.execute("""
            INSERT INTO request_events (request_id, event_type, actor_id, actor_role, details)
            VALUES (?, 'Acknowledge', 'RECIPIENT', 'citizen', ?)
        """, (req_id, json.dumps({"qr_code": payload.qr_code, "signature": payload.ack_signature, "timestamp": now})))

        await db.commit()

        return {
            "status": "acknowledged",
            "request_id": req_id,
            "qr_code": payload.qr_code,
            "message": "Delivery successfully acknowledged by recipient. Chain of custody complete!"
        }
    finally:
        await db.close()

# ----------------- INVENTORY -----------------
@app.get("/api/inventory")
async def list_inventory():
    db = await get_db_connection()
    try:
        cursor = await db.execute("SELECT * FROM inventory_items ORDER BY category, item_name")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()

@app.post("/api/inventory")
async def add_inventory_item(item: InventoryItemCreate):
    db = await get_db_connection()
    try:
        inv_id = f"INV_{uuid.uuid4().hex[:8]}"
        await db.execute("""
            INSERT INTO inventory_items (id, ngo_id, item_name, category, quantity, reserved_quantity, unit, location_name, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        """, (inv_id, item.ngo_id, item.item_name, item.category, item.quantity, item.unit, item.location_name, item.latitude, item.longitude))
        await db.commit()
        return {"status": "created", "id": inv_id}
    finally:
        await db.close()

# ----------------- VOLUNTEERS -----------------
@app.get("/api/volunteers")
async def list_volunteers(is_vet: Optional[int] = None):
    db = await get_db_connection()
    try:
        if is_vet is not None:
            cursor = await db.execute("SELECT * FROM volunteers WHERE is_vet = ?", (is_vet,))
        else:
            cursor = await db.execute("SELECT * FROM volunteers")
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("skills"):
                try:
                    d["skills"] = json.loads(d["skills"])
                except Exception:
                    pass
            result.append(d)
        return result
    finally:
        await db.close()

@app.get("/api/volunteers/{volunteer_id}/tasks")
async def get_volunteer_tasks(volunteer_id: str):
    db = await get_db_connection()
    try:
        cursor = await db.execute("""
            SELECT d.*, r.title, r.type as emergency_type, r.description, r.priority, r.location_name, r.latitude, r.longitude,
                   p.qr_code, p.delivery_status, p.recipient_ack
            FROM dispatches d
            JOIN requests r ON d.request_id = r.id
            LEFT JOIN packages p ON p.dispatch_id = d.id
            WHERE d.volunteer_id = ?
            ORDER BY d.created_at DESC
        """, (volunteer_id,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()

# ----------------- AUDIT LOGS -----------------
@app.get("/api/audit-logs")
async def get_audit_logs(limit: int = 50):
    db = await get_db_connection()
    try:
        cursor = await db.execute("""
            SELECT e.*, r.title, r.type as request_type
            FROM request_events e
            JOIN requests r ON e.request_id = r.id
            ORDER BY e.created_at DESC
            LIMIT ?
        """, (limit,))
        events = [dict(r) for r in await cursor.fetchall()]

        cursor_runs = await db.execute("""
            SELECT a.*, r.title
            FROM agent_runs a
            JOIN requests r ON a.request_id = r.id
            ORDER BY a.created_at DESC
            LIMIT ?
        """, (limit,))
        agent_runs = []
        for r in await cursor_runs.fetchall():
            rd = dict(r)
            try:
                rd["output_data"] = json.loads(rd["output_data"])
            except Exception:
                pass
            agent_runs.append(rd)

        return {
            "request_events": events,
            "agent_runs": agent_runs
        }
    finally:
        await db.close()

# Serve static frontend if directory exists
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
