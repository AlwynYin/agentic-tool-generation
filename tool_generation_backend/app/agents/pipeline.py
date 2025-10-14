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

from app.models import UserToolRequirement
from app.models.session import ToolRequirement
from app.models.tool_generation import ToolGenerationResult, ToolGenerationFailure, ToolGenerationOutput
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
                output_type=ToolGenerationOutput,
                model=self.settings.openai_model,
                tools=[implement_tool]  # Use the @function_tool decorated function
            )
            agents.set_default_openai_key(self.settings.openai_api_key)

            logger.info("Initialized chemistry tool generation agent with implement_chemistry_tool")

        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise

    async def process_tool_generation(self, session_id: str, requests: List[UserToolRequirement]) -> ToolGenerationOutput:
        """
        Process tool generation operation using the OpenAI Agent.

        Args:
            session_id: The session id of the tool generation request.
            requests: List of User Tool Requirements.

        Returns:
            ToolGenerationOutput with results and failures
        """
        self._ensure_agent()

        try:
            # Create MongoDB session for conversation history
            session = MongoSession(session_id)

            logger.info(f"Processing implement operation for session {session_id}")

            # Build message for the agent
            message = self._build_user_requirements_message(requests)

            # Use agent to analyze requirements and call implement_chemistry_tool
            result = await Runner.run(
                starting_agent=self._agent,
                input=message,
                session=session
            )

            logger.info(f"Agent execution completed for session {session_id}")
            logger.debug(f"Result: {result}")

            # Extract tool generation output
            output = result.final_output_as(ToolGenerationOutput)
            logger.info(f"Generated {output.success_count} tools, {output.failure_count} failures")

            return output

        except Exception as e:
            logger.error(f"Error processing operation: {e}")
            raise

    def _build_user_requirements_message(self, tools: List[UserToolRequirement]) -> str:
        """
        Build message for the agent with user requirements.

        Args:
            context: Operation context with user requirements

        Returns:
            Formatted message for the agent
        """
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
You are a Computational Chemistry Expert. Your job is to analyze user requirements and create precise computational chemistry tools.

## Tool
- A Tool is a python function that does one single computation task, with a well-typed and documented input and output schema. 
- The tool should not be over-complicated and have multiple capabilities. If there's multiple separate jobs, there should be multiple separate tools.
- The tool should be completely stateless. This means that it should not use any global state, and should not modify anything from the outer scope. It should output from, and only from, python's `return` statement. It should not modify the input.

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

## Malformed Requirements:
Some user requirements may be malformed or unsuitable. Common cases include:
- **Too broad**: "make a computation toolset for molecules" (requires multiple tools)
- **Not a computation task**: "make a http server", "create a database"
- **Lacks specificity**: "do chemistry stuff", "analyze molecules" (what analysis?)
- **Outside chemistry domain**: "parse JSON files", "send emails"
- **Impossible/nonsensical**: "calculate the color of happiness"

When you encounter a malformed requirement, DO NOT attempt to implement it.

## Output Specifications:
You MUST return a ToolGenerationOutput object with two fields:
- `results`: List of successfully generated tools (ToolGenerationResult objects)
- `failures`: List of failed requirements (ToolGenerationFailure objects)

For each user requirement, decide:

1. **If the requirement is valid** → Call implement_chemistry_tool, then add a ToolGenerationResult to `results`:
   - Set `success: true`
   - Include all required fields: name, file_name, description, input_schema, output_schema, dependencies

2. **If the requirement is malformed/invalid** → Add a ToolGenerationFailure to `failures`:
   - Set `success: false`
   - Include the original `userToolRequirement` object
   - Provide a clear `error` message explaining why it cannot be implemented
   - Provide a `error_type` message, containing one or two words classifying its problem

Example failures:
- "Requirement too broad: This describes multiple separate tools. Please specify individual computation tasks."
- "Not a chemistry computation: HTTP servers are not chemistry tools. Please request molecular calculations, structure analysis, or property predictions."
- "Lacks specificity: 'analyze molecules' could mean many things. Please specify which molecular properties or analyses you need."

IMPORTANT: Every user requirement must appear in either `results` OR `failures`. The total count must match the number of requirements.

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