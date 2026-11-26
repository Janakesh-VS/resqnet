import os
import sys
import unittest
import json
from fastapi.testclient import TestClient

# Ensure root & venv packages in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
VENV_PKGS = os.path.join(BASE_DIR, ".venv", "Lib", "site-packages")
if os.path.exists(VENV_PKGS) and VENV_PKGS not in sys.path:
    sys.path.append(VENV_PKGS)

from resqnet.seed import seed_tamil_nadu_data
from resqnet.api import app

class TestResQNetEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_tamil_nadu_data()
        cls.client = TestClient(app)

    def test_01_health_and_frontend(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

        # Frontend index
        res_front = self.client.get("/")
        self.assertEqual(res_front.status_code, 200)
        self.assertIn("ResQNet", res_front.text)

    def test_02_seeded_requests_and_village_a(self):
        res = self.client.get("/api/requests")
        self.assertEqual(res.status_code, 200)
        requests = res.json()
        self.assertGreaterEqual(len(requests), 2)
        
        # Verify REQ001 (Village A)
        req1 = next(r for r in requests if r["id"] == "REQ001")
        self.assertEqual(req1["type"], "human")
        self.assertEqual(req1["priority"], "Critical")
        self.assertIn("Drinking Water", req1["resources_needed"])
        self.assertIn("Medical Kits", req1["resources_needed"])

    def test_03_inventory_shortage_detection(self):
        res = self.client.get("/api/requests/REQ001")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        agent_runs = data["agent_runs"]
        
        # Resource agent run must flag shortage for Medical Kits (only 3 in stock, 10 needed)
        res_run = next(r for r in agent_runs if r["step_name"] == "Resource Allocation")
        out = res_run["output_data"]
        self.assertTrue(out["has_shortage"])
        shortages = [s["item_name"] for s in out["shortages"]]
        self.assertIn("Medical Kits", shortages)

    def test_04_animal_emergency_strict_vet_rule(self):
        # REQ002 is livestock rescue at Adyar River
        res = self.client.get("/api/requests/REQ002")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        vol_run = next(r for r in data["agent_runs"] if r["step_name"] == "Volunteer Coordination")
        out = vol_run["output_data"]
        
        # Must enforce strict vet compliance!
        self.assertTrue(out["strict_vet_compliance"])
        for disp in out["proposed_dispatches"]:
            self.assertEqual(disp["role_type"], "vet")
            self.assertTrue(disp["is_vet"])
            self.assertIsNotNone(disp["vet_license_no"])

    def test_05_human_in_the_loop_approval_and_qr_generation(self):
        # Coordinator approves REQ001
        detail_res = self.client.get("/api/requests/REQ001")
        data = detail_res.json()
        allocs = next(r for r in data["agent_runs"] if r["step_name"] == "Resource Allocation")["output_data"]["proposed_allocations"]
        disps = next(r for r in data["agent_runs"] if r["step_name"] == "Volunteer Coordination")["output_data"]["proposed_dispatches"]

        approval_payload = {
            "coordinator_id": "USR_COORD",
            "approved_priority": "Critical",
            "approved_allocations": allocs,
            "approved_dispatches": disps,
            "notes": "Verified by Chief Disaster Coordinator. Dispatch boats and relief."
        }
        app_res = self.client.post("/api/requests/REQ001/approve", json=approval_payload)
        self.assertEqual(app_res.status_code, 200)
        app_data = app_res.json()
        self.assertEqual(app_data["status"], "approved_and_dispatched")
        self.assertTrue(app_data["package_qr"].startswith("RESQ-REQ001-"))

        # Check request status updated to Dispatched
        updated_req = self.client.get("/api/requests/REQ001").json()["request"]
        self.assertEqual(updated_req["status"], "Dispatched")
        self.assertEqual(updated_req["requires_human_review"], 0)

        # Recipient delivery acknowledgement
        ack_res = self.client.post("/api/deliveries/acknowledge", json={
            "qr_code": app_data["package_qr"],
            "recipient_ack": True,
            "ack_signature": "Murugan Velu (Verified Digital Signature)"
        })
        self.assertEqual(ack_res.status_code, 200)
        self.assertEqual(ack_res.json()["status"], "acknowledged")

        # Final request status should be Acknowledged
        final_req = self.client.get("/api/requests/REQ001").json()["request"]
        self.assertEqual(final_req["status"], "Acknowledged")

    def test_06_audit_trail_immutable_logging(self):
        res = self.client.get("/api/audit-logs")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(len(data["request_events"]), 0)
        self.assertGreater(len(data["agent_runs"]), 0)

if __name__ == "__main__":
    unittest.main()
