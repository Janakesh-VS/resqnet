from pydantic import BaseModel
from typing import Optional, Literal


class RequestDetails(BaseModel):
    request_id: str
    disaster_type: str
    location: Optional[str] = None
    affected_families: Optional[int] = None
    affected_individuals: Optional[int] = None
    resources_needed: list[str]
    description: str
    missing_information: list[str]
    status: str


class PriorityDetails(BaseModel):
    request_id: str
    recommended_priority: Literal["Critical", "High", "Medium", "Low"]
    reason: str
    requires_human_review: bool


class ResourceDetails(BaseModel):
    request_id: str
    matched_resources: list[str]
    available_quantity: list[str]
    shortages: list[str]
    recommendation: str


class VolunteerDetails(BaseModel):
    request_id: str
    recommended_volunteers: list[str]
    required_skills: list[str]
    assignment_status: str
    recommendation: str


class DeliveryDetails(BaseModel):
    request_id: str
    delivery_status: Literal[
        "Pending", "Dispatched", "In Transit", "Delivered", "Delayed"
    ]
    delivery_location: str
    issues: list[str]
    acknowledgement_received: bool
