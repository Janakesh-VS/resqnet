import sys
import os
import json
import asyncio

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

VENV_PKGS = os.path.join(BASE_DIR, ".venv", "Lib", "site-packages")
if os.path.exists(VENV_PKGS) and VENV_PKGS not in sys.path:
    sys.path.append(VENV_PKGS)

from resqnet.seed import seed_tamil_nadu_data
from httpx import AsyncClient, ASGITransport
from resqnet.api import app

async def run_audit_suite():
    print("=" * 65)
    print("RESQNET EXHAUSTIVE 6-STAGE WORKFLOW & END-TO-END AUDIT SUITE")
    print("=" * 65)

    # 1. Reset & Seed DB
    print("\n[PHASE 1] Initializing fresh state with Tamil Nadu flood baseline...")
    seed_tamil_nadu_data()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # -----------------------------------------------------------
        # TEST 1: Offline Capture & Sync (Human & Animal Intake)
        # -----------------------------------------------------------
        print("\n[PHASE 2] Stage 1 (Report) & Stage 2 (Validate): Offline Capture & Dedupe Verification")
        
        # Ingest new urgent human report (Village C)
        report_human = {
            "type": "human",
            "title": "Submerged Hamlet - Village C Cuddalore",
            "description": "Rising flood waters 5 feet deep. Elderly citizens trapped in community hall without food.",
            "disaster_type": "Flood",
            "location_name": "Village C, Cuddalore Delta Basin",
            "latitude": 11.7480,
            "longitude": 79.7714,
            "affected_families": 25,
            "affected_individuals": 95,
            "resources_needed": ["Drinking Water", "Food Packets", "Rescue Boat"],
            "created_by": "USR_CITIZEN1"
        }
        res_h = await client.post("/api/requests", json=report_human)
        assert res_h.status_code == 200
        h_data = res_h.json()
        req_c_id = h_data["request_id"]
        print(f"  ✓ Ingested new incident: {req_c_id} ({report_human['title']})")
        print(f"    Agent Verdict: {h_data['pipeline_verdict']['summary']}")

        # Test duplicate detection by re-submitting nearly identical request
        report_dup = dict(report_human)
        report_dup["title"] = "Emergency Village C Cuddalore"
        res_dup = await client.post("/api/requests", json=report_dup)
        assert res_dup.status_code == 200
        dup_data = res_dup.json()
        dup_analysis = dup_data["agent_runs"]["1_request_analysis"]["duplicate_check"]
        assert dup_analysis["is_duplicate"] is True
        print(f"  ✓ Duplicate Flagging Guardrail Verified: Duplicate of {dup_analysis['duplicate_of']} detected with confidence {dup_analysis['confidence']}")

        # -----------------------------------------------------------
        # TEST 2: Agent Pipeline Execution Order & Audit Logging
        # -----------------------------------------------------------
        print("\n[PHASE 3] Stage 3 (Prioritise) & Stage 4 (Match): Specialist Multi-Agent Pipeline Audit")
        d_res = await client.get(f"/api/requests/{req_c_id}")
        assert d_res.status_code == 200
        req_c_detail = d_res.json()
        runs = req_c_detail["agent_runs"]
        
        # Verify 5 distinct specialist agents recorded in agent_runs
        agent_names = [r["step_name"] for r in runs]
        expected_agents = [
            "Request Analysis", "Priority Assessment", "Resource Allocation", 
            "Volunteer Coordination", "Delivery Monitor"
        ]
        for ea in expected_agents:
            assert ea in agent_names, f"Missing agent step {ea}"
        print(f"  ✓ All 5 Specialist Agents logged in agent_runs: {agent_names}")

        # Priority agent check
        p_run = next(r for r in runs if r["step_name"] == "Priority Assessment")
        assert p_run["output_data"]["requires_human_review"] is True
        print(f"  ✓ Priority Agent: {p_run['output_data']['recommended_priority']} (Score: {p_run['output_data']['urgency_score']}) with requires_human_review: true")

        # -----------------------------------------------------------
        # TEST 3: Animal Rescue Guardrail (Strict Certified Vet Enforcement)
        # -----------------------------------------------------------
        print("\n[PHASE 4] Stage 4 (Match Animal): Strict Certified Vet Enforcement Guardrail")
        
        # Create animal emergency
        report_animal = {
            "type": "animal",
            "title": "Injured Livestock Stranded at Madhavaram Dairy Farms",
            "description": "8 dairy cows submerged up to their necks with barbed wire trauma injuries. Urgent certified vet required.",
            "disaster_type": "Flood",
            "location_name": "Madhavaram Dairy Farm Sector",
            "latitude": 13.1500,
            "longitude": 80.2310,
            "animal_species": "Bovine Dairy Cattle",
            "animal_count": 8,
            "resources_needed": ["Veterinary Care", "Animal Antiseptic & Bandages", "Cattle Fodder & Feed"],
            "created_by": "USR_CITIZEN1"
        }
        res_a = await client.post("/api/requests", json=report_animal)
        assert res_a.status_code == 200
        req_a_id = res_a.json()["request_id"]
        
        d_a_res = await client.get(f"/api/requests/{req_a_id}")
        runs_a = d_a_res.json()["agent_runs"]
        vol_a_run = next(r for r in runs_a if r["step_name"] == "Volunteer Coordination")
        vol_a_out = vol_a_run["output_data"]

        assert vol_a_out["strict_vet_compliance"] is True, "Animal case failed strict vet compliance rule!"
        for disp in vol_a_out["proposed_dispatches"]:
            assert disp["role_type"] == "vet", "Non-vet assigned to animal case!"
            assert disp["is_vet"] is True
            assert disp["vet_license_no"] is not None
            print(f"  ✓ Strict Vet Assigned: {disp['volunteer_name']} (Reg: {disp['vet_license_no']}) - Non-vets strictly excluded.")

        # -----------------------------------------------------------
        # TEST 4: Human Approval Gate & Shortage Integrity
        # -----------------------------------------------------------
        print("\n[PHASE 5] Stage 5 (Dispatch): Human-in-the-Loop Approval & Inventory Reservation Gate")
        
        # Before approval: verify inventory is NOT reserved yet
        inv_before = await client.get("/api/inventory")
        inv_items_before = {i["item_name"]: i for i in inv_before.json()}
        water_res_before = inv_items_before["Drinking Water"]["reserved_quantity"]
        
        # Coordinator approves REQ001 (Village A)
        d_village_a = (await client.get("/api/requests/REQ001")).json()
        res_run_a = next(r for r in d_village_a["agent_runs"] if r["step_name"] == "Resource Allocation")
        allocs_a = res_run_a["output_data"]["proposed_allocations"]
        vol_run_a = next(r for r in d_village_a["agent_runs"] if r["step_name"] == "Volunteer Coordination")
        disps_a = vol_run_a["output_data"]["proposed_dispatches"]

        # Confirm shortage alert detected in stock
        shortages_a = res_run_a["output_data"]["shortages"]
        assert len(shortages_a) > 0, "Expected shortage flag on Medical Kits!"
        print(f"  ✓ Shortage Alert verified: {shortages_a[0]['item_name']} - {shortages_a[0]['reason']}")

        approve_payload = {
            "coordinator_id": "USR_COORD",
            "approved_priority": "Critical",
            "approved_allocations": allocs_a,
            "approved_dispatches": disps_a,
            "notes": "Chief Coordinator approved field dispatch. Authorize immediate release."
        }
        app_res = await client.post("/api/requests/REQ001/approve", json=approve_payload)
        assert app_res.status_code == 200
        app_json = app_res.json()
        qr_code = app_json["package_qr"]
        print(f"  ✓ Human Approval Granted: Ticket REQ001 moved to Dispatched. Generated QR: {qr_code}")

        # Check inventory is now accurately reserved
        inv_after = await client.get("/api/inventory")
        inv_items_after = {i["item_name"]: i for i in inv_after.json()}
        water_res_after = inv_items_after["Drinking Water"]["reserved_quantity"]
        assert water_res_after > water_res_before, "Inventory reservation failed to increment on approval!"
        print(f"  ✓ Inventory Reservation Enforced: Drinking Water reserved increased from {water_res_before} to {water_res_after}")

        # Also test Coordinator Override endpoint
        override_res = await client.post(f"/api/requests/{req_c_id}/override", json={
            "coordinator_id": "USR_COORD",
            "override_priority": "Critical",
            "override_status": "Dispatched",
            "reason": "Flash flooding worsened in Cuddalore; immediate manual override required.",
            "custom_instructions": "Deploy marine rescue teams."
        })
        assert override_res.status_code == 200
        print(f"  ✓ Coordinator Override Endpoint Verified: {override_res.json()['reason']}")

        # -----------------------------------------------------------
        # TEST 5: QR Handoff & Recipient Acknowledgement
        # -----------------------------------------------------------
        print("\n[PHASE 6] Stage 6 (Acknowledge): Digital Waybill QR Handoff & Ticket Closure")
        
        ack_res = await client.post("/api/deliveries/acknowledge", json={
            "qr_code": qr_code,
            "recipient_ack": True,
            "ack_signature": "Murugan Velu (Verified Digital Handoff on Device)",
            "ack_notes": "All 200 water cans and rations received in full at Madhavaram."
        })
        assert ack_res.status_code == 200
        print(f"  ✓ Recipient Acknowledged Delivery: Chain of custody completed for {qr_code}")

        final_req_a = (await client.get("/api/requests/REQ001")).json()["request"]
        assert final_req_a["status"] == "Acknowledged", f"Expected Acknowledged but got {final_req_a['status']}"
        print(f"  ✓ Ticket State Transition Verified: REQ001 -> {final_req_a['status']}")

        # -----------------------------------------------------------
        # TEST 6: Immutable End-to-End Audit Trail
        # -----------------------------------------------------------
        print("\n[PHASE 7] Immutable Audit Trail Ledger Audit")
        audit = (await client.get("/api/audit-logs")).json()
        events = audit["request_events"]
        runs_all = audit["agent_runs"]
        
        event_types = set(e["event_type"] for e in events)
        print(f"  ✓ Recorded {len(events)} Event Logs across types: {event_types}")
        assert "Report" in event_types
        assert "HumanApprove" in event_types
        assert "HumanOverride" in event_types
        assert "Acknowledge" in event_types
        print(f"  ✓ Recorded {len(runs_all)} AI Specialist Agent Runs in ledger.")

    print("\n" + "=" * 65)
    print("ALL AUDIT SCENARIOS PASSED WITH ZERO REGRESSIONS!")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(run_audit_suite())
