import os
import json
import uuid
import datetime
from typing import Dict, Any, List, Optional

# LangGraph pipeline state representation
class ChiefCoordinatorPipeline:
    """
    LangGraph-compatible Chief Coordinator pipeline orchestrating specialist agents:
    1. Report & Intake
    2. Validate (Request Analysis Agent + Duplicate Check)
    3. Prioritise (Priority Assessment Agent + requires_human_review: true)
    4. Match - Resources (Resource Allocation Agent + NGO stock & Shortage Flagging)
    5. Match - Volunteers (Volunteer Coordination Agent + strict Vet certification for animal cases)
    6. Delivery Monitor & Dispatch Prep (requires human approval gate)

    Includes deterministic JSON fallbacks when LLM API keys are absent or offline,
    ensuring 100% demo reliability without external latency or failures.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def run_request_analysis(self, raw_input: Dict[str, Any], existing_requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Specialist Agent 1: Request Analysis & Deduplication"""
        title = raw_input.get("title", "")
        desc = raw_input.get("description", "")
        req_type = raw_input.get("type", "human").lower()
        loc_name = raw_input.get("location_name", "Unknown")
        lat = float(raw_input.get("latitude", 13.0827))
        lng = float(raw_input.get("longitude", 80.2707))

        # Check for duplicates based on proximity (< 0.01 deg ~= 1.1km) and title/location keyword overlap
        is_duplicate = False
        duplicate_of_id = None
        for ex in existing_requests:
            ex_lat = float(ex.get("latitude", 0))
            ex_lng = float(ex.get("longitude", 0))
            dist = ((lat - ex_lat)**2 + (lng - ex_lng)**2) ** 0.5
            if dist < 0.01 and (loc_name.lower() in ex.get("location_name", "").lower() or ex.get("location_name", "").lower() in loc_name.lower()):
                is_duplicate = True
                duplicate_of_id = ex.get("id")
                break

        # Resources needed parsing
        resources = raw_input.get("resources_needed", [])
        if isinstance(resources, str):
            try:
                resources = json.loads(resources)
            except Exception:
                resources = [r.strip() for r in resources.split(",") if r.strip()]

        if not resources:
            if req_type == "animal":
                resources = ["Veterinary Care", "Animal Feed", "Shelter"]
            else:
                resources = ["Drinking Water", "Food Packets", "Medical Kits"]

        missing_info = []
        if not raw_input.get("location_name"):
            missing_info.append("Precise landmark/location missing")
        if req_type == "human" and not raw_input.get("affected_families") and not raw_input.get("affected_individuals"):
            missing_info.append("Estimated number of affected persons missing")
        if req_type == "animal" and not raw_input.get("animal_species"):
            missing_info.append("Animal species not specified")

        return {
            "agent_name": "Request Analysis Agent",
            "extracted_fields": {
                "type": req_type,
                "title": title or f"Emergency Relief at {loc_name}",
                "description": desc,
                "disaster_type": raw_input.get("disaster_type", "Flood"),
                "location_name": loc_name,
                "latitude": lat,
                "longitude": lng,
                "affected_families": int(raw_input.get("affected_families") or 0),
                "affected_individuals": int(raw_input.get("affected_individuals") or 0),
                "animal_species": raw_input.get("animal_species"),
                "animal_count": int(raw_input.get("animal_count") or 0),
                "resources_needed": resources
            },
            "duplicate_check": {
                "is_duplicate": is_duplicate,
                "duplicate_of": duplicate_of_id,
                "confidence": 0.95 if is_duplicate else 0.05
            },
            "missing_information": missing_info,
            "validation_status": "Flagged Duplicate" if is_duplicate else "Validated"
        }

    def run_priority_assessment(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Specialist Agent 2: Priority Assessment"""
        fields = analysis_data["extracted_fields"]
        req_type = fields["type"]
        families = fields["affected_families"]
        individuals = fields["affected_individuals"]
        resources = fields["resources_needed"]
        desc = (fields["description"] or "").lower()

        # Deterministic scoring logic
        score = 0
        reasons = []

        if req_type == "animal":
            count = fields.get("animal_count", 0)
            if "trapped" in desc or "injured" in desc or "critical" in desc:
                score += 4
                reasons.append("Immediate physical danger / trapped livestock reported")
            if count > 20:
                score += 3
                reasons.append(f"High livestock/animal count ({count} head)")
            else:
                score += 2
                reasons.append("Animal emergency requiring certified veterinary intervention")
        else:
            if families >= 30 or individuals >= 100:
                score += 4
                reasons.append(f"Large affected population ({families} families / {individuals} individuals)")
            elif families >= 10 or individuals >= 30:
                score += 3
                reasons.append(f"Substantial community cluster affected ({families} families)")
            else:
                score += 2
                reasons.append("Localised family emergency")

            if any(k in [r.lower() for r in resources] for k in ["medical kits", "first aid", "medicine", "rescue"]):
                score += 2
                reasons.append("Critical medical relief or rescue required")

            if any(w in desc for w in ["trapped", "elderly", "children", "submerged", "stranded", "urgent"]):
                score += 2
                reasons.append("Vulnerable groups or submerged location detected")

        if score >= 5:
            priority = "Critical"
        elif score >= 4:
            priority = "High"
        elif score >= 2:
            priority = "Medium"
        else:
            priority = "Low"

        return {
            "agent_name": "Priority Assessment Agent",
            "recommended_priority": priority,
            "urgency_score": score,
            "reason": "; ".join(reasons) or "Assessed based on community scale and reported requirements.",
            "requires_human_review": True, # Human-in-the-loop mandatory rule!
            "human_approval_gate": "Coordinator Approval Required before Allocation"
        }

    def run_resource_allocation(self, analysis_data: Dict[str, Any], inventory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Specialist Agent 3: Resource Allocation & Shortage Flagging"""
        fields = analysis_data["extracted_fields"]
        needed = fields["resources_needed"]
        families = max(fields["affected_families"], 1)

        allocations = []
        shortages = []
        inventory_matches = []

        for item_name in needed:
            # Estimate needed quantity: 2 food packets per family, 1 water packet per family, etc.
            norm = item_name.lower().strip()
            if "water" in norm:
                req_qty = families * 4
            elif "food" in norm:
                req_qty = families * 3
            elif "medical" in norm:
                req_qty = max(families // 5, 2)
            elif "blanket" in norm:
                req_qty = families * 2
            elif "feed" in norm or "fodder" in norm:
                req_qty = max(fields.get("animal_count", 5) * 2, 10)
            else:
                req_qty = families

            # Match against inventory
            matched = None
            for inv in inventory:
                if norm in inv["item_name"].lower() or inv["item_name"].lower() in norm:
                    matched = inv
                    break

            if matched:
                available = matched["quantity"] - matched.get("reserved_quantity", 0)
                if available >= req_qty:
                    allocations.append({
                        "item_id": matched["id"],
                        "item_name": matched["item_name"],
                        "ngo_id": matched["ngo_id"],
                        "requested_quantity": req_qty,
                        "allocated_quantity": req_qty,
                        "unit": matched.get("unit", "kits"),
                        "status": "Available"
                    })
                    inventory_matches.append(f"{matched['item_name']}: {req_qty} units allocated from {matched['location_name']}")
                else:
                    # Partial allocation & Shortage flagged
                    alloc_qty = max(available, 0)
                    allocations.append({
                        "item_id": matched["id"],
                        "item_name": matched["item_name"],
                        "ngo_id": matched["ngo_id"],
                        "requested_quantity": req_qty,
                        "allocated_quantity": alloc_qty,
                        "unit": matched.get("unit", "kits"),
                        "status": "Partial" if alloc_qty > 0 else "Out of Stock"
                    })
                    shortage_amount = req_qty - alloc_qty
                    shortages.append({
                        "item_name": matched["item_name"],
                        "shortage_quantity": shortage_amount,
                        "reason": f"Only {available} units available in stock at {matched['location_name']} (Needed: {req_qty})"
                    })
            else:
                shortages.append({
                    "item_name": item_name,
                    "shortage_quantity": req_qty,
                    "reason": f"No NGO in network has '{item_name}' in catalog"
                })

        return {
            "agent_name": "Resource Allocation Agent",
            "proposed_allocations": allocations,
            "shortages": shortages,
            "has_shortage": len(shortages) > 0,
            "recommendation": f"Proposed {len(allocations)} item allocations. Alerted {len(shortages)} supply shortage(s).",
            "requires_human_approval": True
        }

    def run_volunteer_coordination(self, analysis_data: Dict[str, Any], volunteers_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Specialist Agent 4: Volunteer Coordination & Strict Animal Vet Verification"""
        fields = analysis_data["extracted_fields"]
        req_type = fields["type"]
        req_lat = fields["latitude"]
        req_lng = fields["longitude"]

        matched_volunteers = []
        dispatches_proposed = []

        if req_type == "animal":
            # STRICT RULE: strictly assign only certified vets to animal requests!
            eligible = [v for v in volunteers_list if v.get("is_vet") and v.get("is_available")]
            role_type = "vet"
            req_skill = "Veterinary Surgery / Animal First Aid"
        else:
            eligible = [v for v in volunteers_list if v.get("is_available")]
            role_type = "volunteer"
            req_skill = "Disaster Relief / Medical First Aid / Logistics"

        # Proximity sort
        for vol in eligible:
            v_lat = float(vol.get("latitude", 0))
            v_lng = float(vol.get("longitude", 0))
            distance_km = round((((req_lat - v_lat)*111)**2 + ((req_lng - v_lng)*111)**2)**0.5, 2)
            vol_copy = dict(vol)
            vol_copy["distance_km"] = distance_km
            matched_volunteers.append(vol_copy)

        matched_volunteers.sort(key=lambda x: x["distance_km"])

        selected = matched_volunteers[:2] if matched_volunteers else []
        for s in selected:
            dispatches_proposed.append({
                "volunteer_id": s["id"],
                "volunteer_name": s["name"],
                "role_type": role_type,
                "is_vet": bool(s.get("is_vet")),
                "vet_license_no": s.get("vet_license_no"),
                "distance_km": s["distance_km"],
                "phone": s.get("phone", "N/A"),
                "status": "Proposed"
            })

        notes = ""
        if req_type == "animal":
            if not selected:
                notes = "CRITICAL WARNING: No certified veterinarian currently available within network! Human escalation required."
            else:
                notes = f"Verified Animal Emergency: Assigned certified veterinarian {selected[0]['name']} (Lic: {selected[0].get('vet_license_no', 'Active')})."
        else:
            if selected:
                notes = f"Matched {len(selected)} closest available responder(s) with matching relief skills."
            else:
                notes = "No volunteers currently active in region."

        return {
            "agent_name": "Volunteer Coordination Agent",
            "target_role_type": role_type,
            "strict_vet_compliance": True if req_type == "animal" else False,
            "proposed_dispatches": dispatches_proposed,
            "closest_distance_km": selected[0]["distance_km"] if selected else None,
            "recommendation": notes,
            "requires_human_approval": True
        }

    def run_delivery_monitor(self, request_id: str, delivery_record: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Specialist Agent 5: Delivery Monitoring Agent"""
        if not delivery_record:
            return {
                "agent_name": "Delivery Monitoring Agent",
                "request_id": request_id,
                "delivery_status": "Prepared",
                "recipient_acknowledged": False,
                "issues": [],
                "recommendation": "Package QR generated. Awaiting dispatch handover to field responder."
            }

        status = delivery_record.get("delivery_status", "Prepared")
        ack = bool(delivery_record.get("recipient_ack", False))
        issues = []
        if status == "In Transit" and not ack:
            issues.append("Package currently in transit; recipient acknowledgment pending")
        elif status == "Delivered" and not ack:
            issues.append("Package reached location; recipient signature or QR scan required for final verification")

        return {
            "agent_name": "Delivery Monitoring Agent",
            "request_id": request_id,
            "delivery_status": status,
            "recipient_acknowledged": ack,
            "issues": issues,
            "recommendation": "Delivery verified with citizen signature" if ack else "Awaiting recipient acknowledgment."
        }

    def execute_full_pipeline(
        self,
        raw_request: Dict[str, Any],
        existing_requests: List[Dict[str, Any]],
        inventory_items: List[Dict[str, Any]],
        volunteers_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Executes the Chief Coordinator multi-agent orchestrator chain.
        Produces full JSON outputs for all 5 specialist agents with human approval gate.
        """
        analysis = self.run_request_analysis(raw_request, existing_requests)
        priority = self.run_priority_assessment(analysis)
        resources = self.run_resource_allocation(analysis, inventory_items)
        volunteers = self.run_volunteer_coordination(analysis, volunteers_list)
        delivery = self.run_delivery_monitor(raw_request.get("id", "NEW"))

        pipeline_summary = {
            "pipeline_id": str(uuid.uuid4()),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "chief_coordinator_verdict": {
                "request_id": raw_request.get("id"),
                "status": "Awaiting Human Approval",
                "requires_human_review": True,
                "summary": f"Emergency evaluated as {priority['recommended_priority']}. "
                           f"{'Shortage detected in relief stock! ' if resources['has_shortage'] else 'Supplies matched. '}"
                           f"{volunteers['recommendation']}"
            },
            "step_outputs": {
                "1_request_analysis": analysis,
                "2_priority_assessment": priority,
                "3_resource_allocation": resources,
                "4_volunteer_coordination": volunteers,
                "5_delivery_monitor": delivery
            }
        }
        return pipeline_summary
