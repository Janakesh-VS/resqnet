import os
import sys
import json
import sqlite3
import datetime

VENV_PKGS = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv", "Lib", "site-packages")
if os.path.exists(VENV_PKGS) and VENV_PKGS not in sys.path:
    sys.path.append(VENV_PKGS)

from resqnet.db import DB_PATH, init_db_sync
from resqnet.pipeline import ChiefCoordinatorPipeline

def seed_tamil_nadu_data():
    init_db_sync()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Clear existing demo data
    cursor.execute("DELETE FROM agent_runs")
    cursor.execute("DELETE FROM packages")
    cursor.execute("DELETE FROM dispatches")
    cursor.execute("DELETE FROM allocations")
    cursor.execute("DELETE FROM request_events")
    cursor.execute("DELETE FROM requests")
    cursor.execute("DELETE FROM volunteers")
    cursor.execute("DELETE FROM inventory_items")
    cursor.execute("DELETE FROM users")

    # 1. Seed Users (Demo roles: citizen, volunteer, ngo, coordinator, vet)
    users_data = [
        ("USR_COORD", "Dr. Rajesh Sundaram", "coordinator@resqnet.org", "coordinator", "+91 98401 11223", "Tamil Nadu Disaster Management Authority"),
        ("USR_CITIZEN1", "Murugan Velu", "citizen@resqnet.org", "citizen", "+91 94440 22334", "Village A Resident Welfare"),
        ("USR_NGO1", "Red Cross Relief TN", "ngo@resqnet.org", "ngo", "+91 44 2855 4411", "Indian Red Cross Society Chennai"),
        ("USR_VOL1", "Karthik Raja", "volunteer@resqnet.org", "volunteer", "+91 98840 55667", "Tamil Nadu Relief Volunteers"),
        ("USR_VET1", "Dr. Shalini Swaminathan (BVSc)", "vet@resqnet.org", "vet", "+91 97910 88990", "Blue Cross of India & TANUVAS Vet Corps"),
    ]
    cursor.executemany("INSERT INTO users (id, name, email, role, phone, organization) VALUES (?, ?, ?, ?, ?, ?)", users_data)

    # 2. Seed Volunteers & Certified Vets (Chennai & Cuddalore coastal flood zones)
    volunteers_data = [
        ("VOL001", "USR_VOL1", "Karthik Raja", "+91 98840 55667", 0, None, json.dumps(["Disaster Relief", "First Aid", "Boat Operations"]), 1, 13.0827, 80.2707, "Chennai Egmore"),
        ("VOL002", "USR_VET1", "Dr. Shalini Swaminathan", "+91 97910 88990", 1, "TN-VET-2024-9982", json.dumps(["Veterinary Surgery", "Livestock Evacuation", "Bovine Trauma"]), 1, 13.0382, 80.2223, "Guindy / Saidapet"),
        ("VOL003", "USR_VOL1", "Arun Kumar", "+91 98412 34567", 0, None, json.dumps(["Logistics", "Food Distribution"]), 1, 13.0604, 80.2496, "T. Nagar Relief Camp"),
        ("VOL004", "USR_VET1", "Dr. Anand Baskaran", "+91 99401 23456", 1, "TN-VET-2023-4112", json.dumps(["Large Animal Care", "Vaccination"]), 1, 12.9249, 80.1000, "Tambaram Vet Station")
    ]
    cursor.executemany(
        "INSERT INTO volunteers (id, user_id, name, phone, is_vet, vet_license_no, skills, is_available, latitude, longitude, current_location) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        volunteers_data
    )

    # 3. Seed NGO Inventory (With intentional shortage for Village A!)
    # Village A needs: 50 families * 4 = 200 Drinking Water, 50 * 3 = 150 Food, 10 Medical Kits, 100 Blankets.
    # We deliberately give: Drinking Water = 500 (Available), Food = 300 (Available), Blankets = 200 (Available),
    # but Medical Kits = ONLY 3 kits in stock! (Shortage flag!)
    inventory_data = [
        ("INV001", "USR_NGO1", "Drinking Water", "Water", 500, 0, "cans (20L)", "Red Cross Warehouse Royapettah", 13.0569, 80.2600),
        ("INV002", "USR_NGO1", "Food Packets", "Food", 300, 0, "packets", "Red Cross Warehouse Royapettah", 13.0569, 80.2600),
        ("INV003", "USR_NGO1", "Medical Kits", "Medical", 3, 0, "trauma kits", "Red Cross Warehouse Royapettah", 13.0569, 80.2600), # SHORTAGE!
        ("INV004", "USR_NGO1", "Blankets", "Shelter", 200, 0, "units", "Chennai Central Relief Hub", 13.0827, 80.2707),
        ("INV005", "USR_NGO1", "Cattle Fodder & Feed", "Veterinary", 80, 0, "bags (25kg)", "Tambaram Animal Shelter", 12.9249, 80.1000),
        ("INV006", "USR_NGO1", "Animal Antiseptic & Bandages", "Veterinary", 50, 0, "kits", "Guindy Veterinary College", 13.0382, 80.2223)
    ]
    cursor.executemany(
        "INSERT INTO inventory_items (id, ngo_id, item_name, category, quantity, reserved_quantity, unit, location_name, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        inventory_data
    )

    # 4. Seed Requests:
    # REQ001: Village A, 50 families needing Water, Food, Medical Kits, Blankets
    # REQ002: Animal rescue case: 14 stranded cattle and 3 injured dogs near Adyar River bank
    # REQ003: Cuddalore coastal hamlet requesting urgent rescue boats
    req1_resources = json.dumps(["Drinking Water", "Food Packets", "Medical Kits", "Blankets"])
    cursor.execute("""
        INSERT INTO requests (
            id, type, title, description, disaster_type, status, priority,
            location_name, latitude, longitude, affected_families, affected_individuals,
            resources_needed, duplicate_flag, requires_human_review, created_by
        ) VALUES (
            'REQ001', 'human', 'Emergency Inundation Relief - Village A',
            'Severe flood water breached river banks. 50 families cut off on rooftops without potable water or power. Elderly and children present.',
            'Flood', 'Reported', 'Critical', 'Village A, Near Madhavaram Lake, Chennai',
            13.1489, 80.2306, 50, 195, ?, 0, 1, 'USR_CITIZEN1'
        )
    """, (req1_resources,))

    req2_resources = json.dumps(["Veterinary Care", "Cattle Fodder & Feed", "Animal Antiseptic & Bandages"])
    cursor.execute("""
        INSERT INTO requests (
            id, type, title, description, disaster_type, status, priority,
            location_name, latitude, longitude, animal_species, animal_count,
            resources_needed, duplicate_flag, requires_human_review, created_by
        ) VALUES (
            'REQ002', 'animal', 'Livestock Rescue & Trauma Care - Adyar River Bank',
            'Dairy cattle herd stranded on submerged embankment. 2 cows injured by floating debris, 14 cows stranded with rising water levels. Urgent certified vet required.',
            'Flood', 'Reported', 'High', 'Adyar River Embankment near Saidapet Bridge',
            13.0204, 80.2217, 'Cattle (Bovine) & Canines', 17, ?, 0, 1, 'USR_CITIZEN1'
        )
    """, (req2_resources,))

    # Log initial events
    cursor.execute("""
        INSERT INTO request_events (request_id, event_type, actor_id, actor_role, details)
        VALUES ('REQ001', 'Report', 'USR_CITIZEN1', 'citizen', '{"source": "Citizen Web Portal", "note": "Reported 50 families in urgent distress"}')
    """)
    cursor.execute("""
        INSERT INTO request_events (request_id, event_type, actor_id, actor_role, details)
        VALUES ('REQ002', 'Report', 'USR_CITIZEN1', 'citizen', '{"source": "Citizen Web Portal", "note": "Livestock emergency reported"}')
    """)

    conn.commit()
    conn.close()

    # Now execute the Chief Coordinator pipeline for both seeded requests to generate AI recommendations in agent_runs!
    pipeline = ChiefCoordinatorPipeline()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch all inventories & volunteers
    cursor.execute("SELECT * FROM inventory_items")
    inv_list = [dict(r) for r in cursor.fetchall()]
    cursor.execute("SELECT * FROM volunteers")
    vol_list = [dict(r) for r in cursor.fetchall()]
    cursor.execute("SELECT * FROM requests")
    req_list = [dict(r) for r in cursor.fetchall()]

    for r in req_list:
        raw_req = dict(r)
        pipeline_output = pipeline.execute_full_pipeline(raw_req, [x for x in req_list if x["id"] != raw_req["id"]], inv_list, vol_list)
        
        # Log to agent_runs
        steps = pipeline_output["step_outputs"]
        step_names = [
            ("Request Analysis", "Request Analysis Agent", steps["1_request_analysis"]),
            ("Priority Assessment", "Priority Assessment Agent", steps["2_priority_assessment"]),
            ("Resource Allocation", "Resource Allocation Agent", steps["3_resource_allocation"]),
            ("Volunteer Coordination", "Volunteer Coordination Agent", steps["4_volunteer_coordination"]),
            ("Delivery Monitor", "Delivery Monitoring Agent", steps["5_delivery_monitor"])
        ]
        for sname, aname, data in step_names:
            cursor.execute("""
                INSERT INTO agent_runs (id, request_id, step_name, agent_name, input_data, output_data, human_approved)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
            """, (f"RUN_{raw_req['id']}_{sname.replace(' ', '_')}", raw_req["id"], sname, aname, json.dumps(raw_req), json.dumps(data)))

    conn.commit()
    conn.close()
    print("Seed data for Tamil Nadu flood demo initialized successfully!")

if __name__ == "__main__":
    seed_tamil_nadu_data()
