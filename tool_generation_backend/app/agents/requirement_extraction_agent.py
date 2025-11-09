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
from app.services.repository_service import RepositoryService

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
        # Load available libraries dynamically from repository service
        repository_service = RepositoryService()
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
You are a Requirement Extraction Agent for a chemistry computation tool generation system.

## Your Mission:

Analyze the user's task description and break it down into individual tool requirements.
Each tool should be a focused, single-purpose chemistry computation function.

## Output Format:

You MUST return a `RequirementList` object containing a list of `UserToolRequirement` objects.

Each `UserToolRequirement` has:
- `description`: What the tool does (1-2 sentences)
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
- Tools should use standard libraries: {", ".join(self.available_libraries)}
- Focus on molecular properties, quantum chemistry, materials science
- Consider units (g/mol, eV, Angstroms, etc.)

**Stateless Tools:**
- A tool is a python function that's stateless, it can take either python objects or files as input, a file input passes 
- A tool should be completely stateless. It shouldn't have any global state. However it can use randomness, provided that the seed is in input

## Examples:

### Input:
"I need tools to calculate molecular properties from SMILES strings"

### Output:
```json
{
  "requirements": [
    {
      "description": "Calculate molecular weight from SMILES string",
      "input": "SMILES string (e.g., 'CCO' for ethanol)",
      "output": "Molecular weight in g/mol as float"
    },
    {
      "description": "Count atoms in molecule from SMILES string",
      "input": "SMILES string (e.g., 'CCO' for ethanol)",
      "output": "Dictionary with atom types as keys and counts as values"
    },
    {
      "description": "Calculate logP from SMILES string",
      "input": "SMILES string (e.g., 'CCO' for ethanol)",
      "output": "LogP value as float"
    }
  ]
}
```

### Input:
"Build a tool to optimize molecular geometry"

### Output:
```json
{
  "requirements": [
    {
      "description": "Optimize molecular geometry using force field method",
      "input": "XYZ coordinates as string or SMILES string",
      "output": "Optimized XYZ coordinates as string and final energy in eV"
    }
  ]
}
```

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
