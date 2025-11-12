"""
Implementer Agent for generating Python tool code.

This agent uses LLM backend (Codex or Claude Code) to generate tool
implementations from detailed plans and API references.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.config import get_settings
from app.models.pipeline_v2 import (
    ToolDefinition,
    ImplementationPlan,
    ExplorationReport,
    ImplementationResult,
    IterationSummary
)
from app.utils.llm_backend import execute_llm_query

logger = logging.getLogger(__name__)


class ImplementerAgent:
    """
    Agent for implementing Python tools from plans.

    Uses LLM backend (Codex or Claude Code) to:
    1. Generate Python tool file from plan
    2. Add strict type annotations
    3. Add comprehensive docstring
    4. Implement contracts as validation
    5. Handle errors gracefully
    6. Ensure stateless function
    """

    def __init__(self, available_packages: List[str]):
        """Initialize the implementer agent.

        Args:
            available_packages: List of available package names for implementation
        """
        self.settings = get_settings()
        self.available_packages = available_packages
        logger.info(f"Initialized implementer agent with {len(self.available_packages)} available packages")

    async def implement(
        self,
        tool_definition: ToolDefinition,
        plan: ImplementationPlan,
        exploration_report: ExplorationReport,
        iteration_history: List[IterationSummary]
    ) -> ImplementationResult:
        """
        Implement tool from plan using LLM backend.

        Args:
            tool_definition: Tool specification from Intake Agent
            plan: Implementation plan from Planner Agent
            exploration_report: API findings from Search Agent
            iteration_history: Summaries from previous iterations (empty for first iteration)

        Returns:
            ImplementationResult: Generated tool file path and code
        """
        try:
            logger.info(f"Implementing/updating tool: {plan.requirement_name}")

            # Write context files to disk
            context_files = self._write_context_files(tool_definition, plan, exploration_report, iteration_history)

            # Build brief implementation prompt
            prompt = self._build_prompt(plan, exploration_report, iteration_history, context_files)

            # Execute LLM backend to generate tool file using centralized executor
            result = await execute_llm_query(
                prompt=prompt,
                job_id=plan.job_id,
                task_id=plan.task_id,
                expected_file_name=f"{plan.requirement_name}.py"
            )

            if result["success"]:
                # Read generated code
                tool_file_path = result["output_file"]
                with open(tool_file_path, 'r') as f:
                    tool_code = f.read()

                logger.info(f"Tool implemented successfully: {tool_file_path}")

                return ImplementationResult(
                    success=True,
                    tool_file_path=tool_file_path,
                    tool_code=tool_code,
                    error=None
                )
            else:
                logger.error(f"Implementation failed: {result.get('error', 'Unknown error')}")
                return ImplementationResult(
                    success=False,
                    tool_file_path="",
                    tool_code="",
                    error=result.get("error", "Unknown error")
                )

        except Exception as e:
            logger.error(f"Error in implementer agent: {e}")
            return ImplementationResult(
                success=False,
                tool_file_path="",
                tool_code="",
                error=f"Implementer agent error: {str(e)}"
            )

    def _write_context_files(
        self,
        tool_definition: ToolDefinition,
        plan: ImplementationPlan,
        exploration_report: ExplorationReport,
        iteration_history: List[IterationSummary]
    ) -> Dict[str, str]:
        """
        Write context files to disk for the LLM to reference.

        Args:
            tool_definition: Tool specification
            plan: Implementation plan
            exploration_report: API findings
            iteration_history: Previous iteration summaries

        Returns:
            Dict[str, str]: Mapping of file purpose to file path
        """
        from pathlib import Path

        # Create directories
        tools_dir = Path(self.settings.tools_path) / plan.job_id / plan.task_id
        plan_dir = tools_dir / "plan"
        context_dir = tools_dir / "context"

        plan_dir.mkdir(parents=True, exist_ok=True)
        context_dir.mkdir(parents=True, exist_ok=True)

        file_paths = {}

        try:
            # 1. Write function specification
            function_spec_file = plan_dir / "function_spec.txt"
            with open(function_spec_file, 'w') as f:
                f.write(f"# Function Specification for {plan.requirement_name}\n\n")
                f.write(f"## Function Signature\n\n")
                f.write(f"```python\n{tool_definition.signature}\n```\n\n")

                f.write(f"## Docstring\n\n")
                f.write(f"```\n{tool_definition.docstring}\n```\n\n")

                f.write(f"## Contracts\n\n")
                for i, contract in enumerate(tool_definition.contracts, 1):
                    f.write(f"{i}. {contract}\n")

            file_paths["function_spec"] = str(function_spec_file)
            logger.info(f"Wrote function specification to: {function_spec_file}")

            # 2. Write implementation plan
            plan_file = plan_dir / "implementation_plan.txt"
            with open(plan_file, 'w') as f:
                f.write(f"# Implementation Plan for {plan.requirement_name}\n\n")
                f.write(f"## Description\n{plan.requirement_docstring}\n\n")

                f.write("## Implementation Steps\n\n")
                for step in plan.steps:
                    f.write(f"### Step {step.step_number}: {step.action}\n")
                    f.write(f"{step.description}\n\n")
                    if step.apis_used:
                        f.write(f"**APIs Used:** {', '.join(step.apis_used)}\n\n")
                    f.write(f"**Error Handling:** {step.error_handling}\n\n")

                f.write(f"## Expected Artifacts\n\n")
                for artifact in plan.expected_artifacts:
                    f.write(f"- {artifact}\n")

            file_paths["plan"] = str(plan_file)
            logger.info(f"Wrote implementation plan to: {plan_file}")

            # 3. Write validation rules
            validation_file = plan_dir / "validation_rules.txt"
            with open(validation_file, 'w') as f:
                f.write(f"# Validation Rules for {plan.requirement_name}\n\n")
                for i, rule in enumerate(plan.validation_rules, 1):
                    f.write(f"{i}. {rule}\n")

            file_paths["validation"] = str(validation_file)
            logger.info(f"Wrote validation rules to: {validation_file}")

            # 4. Write iteration history (if exists)
            if iteration_history:
                history_file = context_dir / "iteration_history.txt"
                with open(history_file, 'w') as f:
                    f.write(f"# Iteration History for {plan.requirement_name}\n\n")
                    f.write("This tool has been implemented before. Review previous iterations to avoid repeating mistakes.\n\n")

                    for summary in iteration_history:
                        f.write(f"## Iteration {summary.iteration}\n\n")
                        f.write(f"**What Failed:** {summary.what_failed}\n\n")
                        f.write(f"**Changes Made:** {summary.what_changed}\n\n")
                        f.write(f"**Why Changed:** {summary.why_changed}\n\n")
                        f.write(f"**Next Focus:** {summary.next_focus}\n\n")
                        f.write("---\n\n")

                file_paths["history"] = str(history_file)
                logger.info(f"Wrote iteration history to: {history_file}")

            return file_paths

        except Exception as e:
            logger.error(f"Failed to write context files: {e}")
            return {}

    def _build_prompt(
        self,
        plan: ImplementationPlan,
        exploration_report: ExplorationReport,
        iteration_history: List[IterationSummary],
        context_files: Dict[str, str]
    ) -> str:
        """
        Build brief implementation prompt with file references.

        Args:
            plan: Implementation plan
            exploration_report: API findings
            iteration_history: Previous iteration summaries
            context_files: Dict mapping file purpose to file path

        Returns:
            Brief prompt for LLM backend with file references
        """
        # Build relative paths for the LLM to reference
        tools_dir_rel = f"tools/{plan.job_id}/{plan.task_id}"

        # Build context file references
        context_refs = []
        if "function_spec" in context_files:
            context_refs.append(f"- Function specification: {context_files['function_spec']}")
        if "plan" in context_files:
            context_refs.append(f"- Implementation plan: {context_files['plan']}")
        if "validation" in context_files:
            context_refs.append(f"- Validation rules: {context_files['validation']}")
        if exploration_report.api_refs_file:
            context_refs.append(f"- API references and Question Answers: {exploration_report.api_refs_file}")
        if "history" in context_files:
            context_refs.append(f"- Previous iteration feedback: {context_files['history']}")

        context_refs_text = "\n".join(context_refs)

        # Build brief prompt
        prompt = f"""You are implementing or updating a Python chemistry computation tool based on detailed specifications stored in files.

## Task

**Tool Name:** {plan.requirement_name}
**Description:** {plan.requirement_docstring}
**Target File:** {tools_dir_rel}/{plan.requirement_name}.py

## Context Files

Read and follow the specifications in these files:

{context_refs_text}

## Instructions

1. **Use all context files** to understand the complete requirements
2. **Follow the implementation plan** step by step
3. **Implement all validation rules** from the validation file
4. **Use the API references** to call the correct library functions
5. **Address previous feedback** if iteration history exists (this means you need to UPDATE the existing file, not create from scratch)
6. **Check tools/tool_schema.txt** for format of the file and key requirements of the tool function
7. **Note:** if the tool generates a plot, BE CAREFUL not to show the plot, instead save the figure into a file.

## Output

Generate/update the tool file at: {tools_dir_rel}/{plan.requirement_name}.py

If the file already exists, UPDATE it based on the feedback in the iteration history. Otherwise, create it from scratch.
"""

        return prompt

    async def cleanup(self):
        """Clean up implementer agent resources if needed."""
        logger.info("Implementer agent cleanup completed")
