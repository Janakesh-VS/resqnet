from google.adk.agents import SequentialAgent

from resqnet.agents.request_agent import request_agent
from resqnet.agents.priority_agent import priority_agent
from resqnet.agents.resource_agent import resource_agent
from resqnet.agents.volunteer_agent import volunteer_agent


root_agent = SequentialAgent(
    name="resqnet_coordinator",

    description=(
        "Coordinates emergency analysis, priority assessment, "
        "resource checking and volunteer recommendations."
    ),

    sub_agents=[
        request_agent,
        priority_agent,
        resource_agent,
        volunteer_agent
    ]
)
