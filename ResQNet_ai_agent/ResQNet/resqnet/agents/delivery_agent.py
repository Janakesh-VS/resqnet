from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from resqnet.schemas.request_schema import DeliveryDetails


# Simulated delivery records
deliveries = {
    "REQ001": {
        "status": "In Transit",
        "location": "Village A",
        "acknowledgement": False
    },

    "REQ002": {
        "status": "Delivered",
        "location": "Village B",
        "acknowledgement": True
    }
}


def check_delivery(request_id: str) -> dict:
    """
    Checks the recorded delivery status of a request.
    """

    record = deliveries.get(request_id)

    if record is None:
        return {
            "request_id": request_id,
            "status": "Pending",
            "location": "Unknown",
            "acknowledgement": False
        }

    return {
        "request_id": request_id,
        **record
    }


delivery_agent = Agent(
    name="delivery_monitoring_agent",

    model="gemini-3.5-flash-lite",

    description=(
        "Monitors relief delivery records and identifies delays."
    ),

    instruction="""
    You are the Delivery Monitoring Agent of ResQNet.

    Your responsibility is to monitor delivery progress.

    Use check_delivery to retrieve recorded delivery information.

    Rules:

    - Never invent delivery information.
    - Identify pending and delayed deliveries.
    - Check whether acknowledgement was received.
    - Do not treat GPS or QR scans alone as proof of delivery.
    - Only mark a delivery as acknowledged when the
      recorded acknowledgement confirms it.
    - Report issues to the coordinator.
    - Do not modify delivery records yourself.
    """,

    tools=[FunctionTool(check_delivery)],

    output_schema=DeliveryDetails
)
