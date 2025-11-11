"""
Requirement Extraction Agent for testing purposes.

This simple agent takes a string description and converts it
into a list of UserToolRequirement objects.
"""

import logging
from typing import List

import agents
from agents import Agent, Runner
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models.specs import UserToolRequirement

logger = logging.getLogger(__name__)


class RequirementList(BaseModel):
    """List of tool requirements extracted from description."""
    requirements: List[UserToolRequirement] = Field(
        default_factory=list,
        description="List of extracted tool requirements"
    )


class RequirementExtractionAgent:
    """
    Simple agent for extracting tool requirements from text descriptions.

    This is a testing-only agent that analyzes a task description
    and breaks it down into individual UserToolRequirement objects.
    """

    def __init__(self):
        """Initialize the requirement extraction agent."""
        self.settings = get_settings()
        self._agent = None
        # Load available libraries dynamically from repository service (singleton)
        # Import here to avoid circular import
        from app.dependencies import get_repository_service
        repository_service = get_repository_service()
        self.available_libraries = repository_service.get_available_packages()
        logger.info(f"Loaded {len(self.available_libraries)} available libraries for requirement extraction")

    def _ensure_agent(self):
        """Lazy initialization of the agent."""
        if self._agent is None:
            self._initialize_agent()

    def _initialize_agent(self):
        """Initialize the agent with OpenAI Agents SDK."""
        try:
            self._agent = Agent(
                name="Requirement Extraction Agent",
                instructions=self._get_agent_instructions(),
                output_type=RequirementList,
                model=self.settings.openai_model,
                tools=[]  # Pure reasoning - no tools needed
            )
            agents.set_default_openai_key(self.settings.openai_api_key)

            logger.info("Initialized requirement extraction agent")

        except Exception as e:
            logger.error(f"Failed to initialize requirement extraction agent: {e}")
            raise

    async def extract_requirements(self, task_description: str) -> List[UserToolRequirement]:
        """
        Extract tool requirements from a task description.

        Args:
            task_description: Natural language description of what needs to be built

        Returns:
            List[UserToolRequirement]: Extracted tool requirements
        """
        self._ensure_agent()

        try:
            logger.info(f"Extracting requirements from: {task_description[:100]}...")

            # Run the agent
            result = await Runner.run(
                starting_agent=self._agent,
                input=task_description
            )

            logger.info("Requirement extraction completed")

            # Extract output
            requirement_list = result.final_output_as(RequirementList)

            logger.info(f"Extracted {len(requirement_list.requirements)} requirements")

            return requirement_list.requirements

        except Exception as e:
            logger.error(f"Error in requirement extraction agent: {e}")
            # Return empty list on error
            return []

    def _get_agent_instructions(self) -> str:
        """Get system instructions for the requirement extraction agent."""
        return """
You are an computational chemistry expert Agent for a chemistry computation tool generation system.

## Your Mission:

- You are given a task description from the user
- you need to think about how you would solve the task step by step
- You need to think what tools would be needed to assist you in solving the task
- Each tool should be a focused, single-purpose python function that performs certain chemistry computation task
- Make sure by reasoning and calling all the tools, you will be able to solve the task efficiently with minimal error

## Output Format:

You MUST return a `RequirementList` object containing a list of `UserToolRequirement` objects.

Each `UserToolRequirement` has:
- `description`: What the tool does, in less than 4 sentences
- `input`: What data the tool takes as input
- `output`: What data the tool produces as output

## Guidelines:

**Break Down Complex Tasks:**
- If the description mentions multiple operations, create separate requirements
- Each tool should do ONE thing well
- Tools can be composed together by users

**Be Specific:**
- Clearly define inputs (SMILES, XYZ coordinates, molecule object, etc.)
- Clearly define outputs (molecular weight in g/mol, energy in eV, list of atoms, etc.)
- Use chemistry-specific terminology

**Chemistry Focus:**
- Tools should be achievable with python and help of common numerical and computational chemistry libraries.
- You should explain what the tool produces in terms of chemistry, without going too much detail in programming. e.g. you should NOT specify which specific function in the specific library to use
- Consider units (g/mol, eV, Angstroms, etc.)

**Stateless Tools:**
- A tool is a python function that's stateless, it can take either python objects or files as input, a file input passes 
- A tool should be completely stateless. It shouldn't have any global state. However it can use randomness, provided that the seed is in input

## Edge Cases:

**Vague Description:**
- Make reasonable assumptions about what the user wants
- Default to common chemistry operations
- If truly unclear, create 1-2 general tools

**Single Tool Request:**
- If description clearly asks for ONE tool, create just one requirement
- Don't over-decompose simple requests

**Non-Chemistry Request:**
- If description is not chemistry-related, return empty list
- Log that this is a chemistry-only system

Focus on extracting clear, actionable tool requirements that can be implemented.
"""

    async def cleanup(self):
        """Clean up agent resources if needed."""
        logger.info("Requirement extraction agent cleanup completed")
