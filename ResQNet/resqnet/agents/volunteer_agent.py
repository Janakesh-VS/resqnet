from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from resqnet.schemas.request_schema import VolunteerDetails


# Sample volunteer database
volunteers = [
    {
        "name": "Volunteer A",
        "skills": ["First Aid", "Medical Support"],
        "available": True
    },
    {
        "name": "Volunteer B",
        "skills": ["Food Distribution", "Logistics"],
        "available": True
    },
    {
        "name": "Volunteer C",
        "skills": ["Transportation"],
        "available": False
    },
    {
        "name": "Volunteer D",
        "skills": ["Communication", "Coordination"],
        "available": True
    }
]


def find_volunteers(required_skill: str) -> dict:
    """
    Finds available volunteers with a particular skill.
    """

    matches = [
        volunteer["name"]
        for volunteer in volunteers
        if required_skill in volunteer["skills"]
        and volunteer["available"]
    ]

    return {
        "required_skill": required_skill,
        "matching_volunteers": matches
    }


volunteer_agent = Agent(
    name="volunteer_coordination_agent",

    model="gemini-3.5-flash-lite",

    description=(
        "Identifies suitable volunteers based on skills "
        "and availability."
    ),

    instruction="""
    Use the emergency information from:
{request_details}

Recommend suitable volunteers based on required skills.
Do not confirm assignments or deployment.
    You are the Volunteer Coordination Agent of ResQNet.

    Your responsibility is to recommend volunteers
    for approved relief tasks.

    Use find_volunteers to identify suitable volunteers.

    Consider:

    - Required skills
    - Availability
    - Task requirements
    - Location, when verified location information exists

    Rules:

    - Do not assign unavailable volunteers.
    - Never invent volunteer details.
    - Recommend suitable volunteers.
    - Do not independently deploy volunteers.
    - Human approval is required before assignment.
    """,

    tools=[FunctionTool(find_volunteers)],
    output_key="volunteer_result",
    output_schema=VolunteerDetails
)
