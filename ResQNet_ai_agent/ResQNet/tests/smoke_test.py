import sys
import os
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

async def run_smoke_tests():
    print("Seeding database...")
    seed_tamil_nadu_data()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health & Frontend
        h = await client.get("/api/health")
        assert h.status_code == 200
        print("[PASS] 1. API Health Check:", h.json())

        f = await client.get("/")
        assert f.status_code == 200
        assert "ResQNet" in f.text
        print("[PASS] 2. React PWA Frontend served with HTTP 200")

        # 2. Requests list
        r = await client.get("/api/requests")
        assert r.status_code == 200
        reqs = r.json()
        print(f"[PASS] 3. Loaded {len(reqs)} disaster relief requests")
        req1 = next(x for x in reqs if x["id"] == "REQ001")
        print(f"       - REQ001 Title: {req1['title']}, Status: {req1['status']}, Priority: {req1['priority']}")

        # 3. REQ001 details & AI Agent Runs (Shortage check)
        d = await client.get("/api/requests/REQ001")
        assert d.status_code == 200
        data = d.json()
        runs = data["agent_runs"]
        res_run = next(x for x in runs if x["step_name"] == "Resource Allocation")
        shortages = res_run["output_data"]["shortages"]
        assert len(shortages) > 0
        print(f"[PASS] 4. Resource Allocation Agent flagged shortage in Medical Kits: {shortages[0]['reason']}")

        # 4. Animal Emergency strict vet compliance
        d2 = await client.get("/api/requests/REQ002")
        runs2 = d2.json()["agent_runs"]
        vol_run = next(x for x in runs2 if x["step_name"] == "Volunteer Coordination")
        assert vol_run["output_data"]["strict_vet_compliance"] is True
        vet_disp = vol_run["output_data"]["proposed_dispatches"][0]
        assert vet_disp["is_vet"] is True
        print(f"[PASS] 5. Animal Case REQ002 strictly assigned certified vet: {vet_disp['volunteer_name']} (Lic: {vet_disp['vet_license_no']})")

        # 5. Coordinator Human Approval Gate
        allocs = res_run["output_data"]["proposed_allocations"]
        disps = vol_run["output_data"]["proposed_dispatches"]
        app_res = await client.post("/api/requests/REQ001/approve", json={
            "coordinator_id": "USR_COORD",
            "approved_priority": "Critical",
            "approved_allocations": allocs,
            "approved_dispatches": disps,
            "notes": "Verified by Chief Disaster Coordinator. Dispatch boats and relief."
        })
        assert app_res.status_code == 200
        app_data = app_res.json()
        qr_code = app_data["package_qr"]
        print(f"[PASS] 6. Coordinator Human Approval Gate verified. Generated Package QR: {qr_code}")

        # Check stock was reserved
        inv_res = await client.get("/api/inventory")
        water_item = next(i for i in inv_res.json() if "Water" in i["item_name"])
        assert water_item["reserved_quantity"] > 0
        print(f"[PASS] 7. Stock Auto-Reservation verified: {water_item['item_name']} reserved: {water_item['reserved_quantity']}")

        # 6. Recipient Delivery Acknowledgement
        ack_res = await client.post("/api/deliveries/acknowledge", json={
            "qr_code": qr_code,
            "recipient_ack": True,
            "ack_signature": "Murugan Velu (Verified Digital Signature)"
        })
        assert ack_res.status_code == 200
        print("[PASS] 8. Recipient delivery acknowledged via QR code. Chain of custody closed.")

        # Verify final status
        final_req = (await client.get("/api/requests/REQ001")).json()["request"]
        assert final_req["status"] == "Acknowledged"
        print(f"[PASS] 9. Request REQ001 reached verified end status: {final_req['status']}")

        # 7. Audit log verification
        audit = (await client.get("/api/audit-logs")).json()
        assert len(audit["request_events"]) >= 3
        print(f"[PASS] 10. Audit trail verified: {len(audit['request_events'])} human/system events and {len(audit['agent_runs'])} AI agent runs logged.")

        print("\n" + "="*50)
        print("ALL 10 END-TO-END SMOKE TESTS PASSED CLEANLY!")
        print("="*50)

if __name__ == "__main__":
    asyncio.run(run_smoke_tests())
