"""
Chemistry tool generation pipeline using OpenAI Agents SDK.

This module implements a coordinator-based pipeline that routes operations
to specialized agents using handoff patterns and maintains conversation
history through MongoDB sessions.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

import agents
from agents import Agent, Runner

from app.models import ToolSpec
from app.models.operation import OperationContext, ImplementRequirements, UpdateRequirements
from app.models.session import ToolRequirement, ToolGenerationResult
from app.memory.mongo_session import MongoSession
from app.config import get_settings
from app.agents.tools import implement_tool

logger = logging.getLogger(__name__)


class ToolGenerationPipeline:
    """
    Simple pipeline for chemistry tool generation using OpenAI Agents SDK.

    Single agent that parses user requirements into precise specifications
    and calls Codex to implement tools.
    """

    def __init__(self):
        """Initialize the pipeline with a single tool generation agent."""
        self.settings = get_settings()
        self._agent = None

    def _ensure_agent(self):
        """Lazy initialization of the agent."""
        if self._agent is None:
            self._initialize_agent()

    def _initialize_agent(self):
        """Initialize the tool generation agent."""
        try:
            # Register our decorated tool function with the agent
            self._agent = Agent(
                name="Chemistry Tool Generator",
                instructions=self._get_agent_instructions(),
                output_type=List[ToolGenerationResult],
                model=self.settings.openai_model,
                tools=[implement_tool]  # Use the @function_tool decorated function
            )
            agents.set_default_openai_key(self.settings.openai_api_key)

            logger.info("Initialized chemistry tool generation agent with implement_chemistry_tool")

        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise

    async def process_operation(self, context: OperationContext) -> List[ToolGenerationResult]:
        """
        Process tool generation operation using the OpenAI Agent.

        Args:
            context: Operation context with user requirements

        Returns:
            List of generated tool requirements
        """
        self._ensure_agent()

        # For now, only support implement operations
        if context.operation_type != "implement":
            raise ValueError(f"Only 'implement' operations are currently supported")

        try:
            # Create MongoDB session for conversation history
            session = MongoSession(context.session_id)

            logger.info(f"Processing implement operation for session {context.session_id}")

            # Build message for the agent
            message = self._build_user_requirements_message(context)

            # Use agent to analyze requirements and call implement_chemistry_tool
            result = await Runner.run(
                starting_agent=self._agent,
                input=message,
                session=session
            )

            logger.info(f"Agent execution completed for session {context.session_id}")
            logger.debug(f"Result: {result}")

            # Extract tool requirements from agent's tool calls
            return result.final_output_as(List[ToolGenerationResult])

        except Exception as e:
            logger.error(f"Error processing operation: {e}")
            raise

    def _build_user_requirements_message(self, context: OperationContext) -> str:
        """
        Build message for the agent with user requirements.

        Args:
            context: Operation context with user requirements

        Returns:
            Formatted message for the agent
        """
        if not isinstance(context.requirements, ImplementRequirements):
            raise ValueError("Invalid requirements type")

        tools = context.requirements.tools
        message = f"Generate {len(tools)} chemistry computation tools based on these requirements:\n\n"

        for i, tool in enumerate(tools, 1):
            message += f"{i}. Description: {tool.description}\n"
            message += f"   Input: {tool.input}\n"
            message += f"   Output: {tool.output}\n\n"

        message += "Please analyze each requirement, create precise specifications with exact parameter names and types, then call implement_chemistry_tool for each one."

        return message

    def _get_agent_instructions(self) -> str:
        """Get system instructions for the single tool generation agent."""
        return """
You are a Chemistry Tool Generation Expert. Your job is to analyze user requirements and create precise tool specifications.

## Your Process:
1. **Analyze**: Understand what the user wants to accomplish
2. **Specify**: Define exact parameter names, types, and chemistry library functions
3. **Implement**: Call the implement_chemistry_tool function with precise specifications

## Requirements for tool specifications:
- `tool_name`: Clear, descriptive name (snake_case)
- `description`: Detailed explanation of functionality
- `input_spec`: JSON schema with exact parameter names and types
- `output_spec`: JSON schema for return values
- `chemistry_libraries`: List of specific chemistry libraries needed

## Chemistry Libraries Available:
- **RDKit**: Molecular manipulation, descriptors, fingerprints
- **ASE**: Atomic structure, calculations, optimization
- **PyMatGen**: Materials science, crystal structures
- **PySCF**: Quantum chemistry calculations

## Common Transformations:
- "molecule" → `smiles: str` (SMILES string format)
- "molecular weight" → `molecular_weight: float` (in g/mol)
- "properties" → specific property names (mw, logp, tpsa, etc.)
- "calculate" → specific algorithm or library function

## Output Specifications:
You should return a list of all tools you have generated, each as a ToolGenerationResult object.

Transform user descriptions into production-ready tool specifications and implement them.
"""

    async def cleanup_session(self, session_id: str):
        """Clean up resources for a session."""
        try:
            session = MongoSession(session_id)
            await session.close()
            logger.info(f"Cleaned up pipeline session {session_id}")
        except Exception as e:
            logger.error(f"Error cleaning up pipeline session {session_id}: {e}")

    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get session information and conversation history."""
        try:
            session = MongoSession(session_id)
            return await session.get_session_info()
        except Exception as e:
            logger.error(f"Error getting pipeline session info for {session_id}: {e}")
            return {"session_id": session_id, "error": str(e)}