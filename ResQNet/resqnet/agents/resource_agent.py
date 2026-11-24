from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from resqnet.schemas.request_schema import ResourceDetails


# Sample inventory for prototype testing
inventory = {
    "Drinking Water": 500,
    "Food Packets": 300,
    "Medical Kits": 100,
    "Blankets": 200,
    "Clothes": 150
}


def check_inventory(resource_name: str) -> dict:
    """
    Checks available inventory using case-insensitive matching.
    """

    normalized_name = resource_name.strip().casefold()

    for name, quantity in inventory.items():
        if name.casefold() == normalized_name:
            return {
                "resource": name,
                "available_quantity": quantity
            }

    return {
        "resource": resource_name,
        "available_quantity": 0,
        "message": "Resource not found in inventory"
    }


resource_agent = Agent(
    name="resource_allocation_agent",

    model="gemini-3.5-flash-lite",

    description=(
        "Checks relief inventory and recommends "
        "suitable resource allocation."
    ),

    instruction="""
    Use the extracted request information from:
{request_details}

Check the inventory against the requested resources.
Do not assume required quantities.
Do not allocate resources.
    You are the Resource Allocation Agent of ResQNet.

    Your responsibility is to match emergency requests
    with available relief resources.

    Use the check_inventory tool to check quantities.

    Rules:

    - Check every requested resource.
    - Never invent inventory quantities.
    - Identify shortages.
    - Recommend suitable resource allocation.
    - Do not confirm actual dispatch.
    - Human coordinator approval is required
      before allocation is finalised.
    """,
    output_key="resource_result",
    tools=[FunctionTool(check_inventory)],

    output_schema=ResourceDetails
)
