"""
Implementer Agent for generating Python tool code.

This agent uses LLM backend (Codex or Claude Code) to generate tool
implementations from detailed plans and API references.
"""

import logging
from pathlib import Path
from typing import List, Optional

from app.config import get_settings
from app.models.pipeline_v2 import (
    ImplementationPlan,
    ExplorationReport,
    ImplementationResult,
    IterationSummary
)
from app.utils.llm_backend import execute_llm_implement

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

    def __init__(self):
        """Initialize the implementer agent."""
        self.settings = get_settings()

    async def implement(
        self,
        plan: ImplementationPlan,
        exploration_report: ExplorationReport,
        iteration_history: List[IterationSummary]
    ) -> ImplementationResult:
        """
        Implement tool from plan using LLM backend.

        Args:
            plan: Implementation plan from Planner Agent
            exploration_report: API findings from Search Agent
            iteration_history: Summaries from previous iterations (empty for first iteration)

        Returns:
            ImplementationResult: Generated tool file path and code
        """
        try:
            logger.info(f"Implementing tool: {plan.requirement_name}")

            # Build enhanced implementation prompt
            prompt = self._build_enhanced_prompt(plan, exploration_report, iteration_history)

            # Execute LLM backend to generate tool file
            # Note: execute_llm_implement expects a simplified plan format
            # We'll use the existing execute_llm_implement but with enhanced prompt
            result = await self._execute_llm_with_prompt(plan, prompt)

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

    def _build_enhanced_prompt(
        self,
        plan: ImplementationPlan,
        exploration_report: ExplorationReport,
        iteration_history: List[IterationSummary]
    ) -> str:
        """
        Build enhanced implementation prompt with plan details.

        Args:
            plan: Implementation plan
            exploration_report: API findings
            iteration_history: Previous iteration summaries

        Returns:
            Enhanced prompt for LLM backend
        """
        # Format plan steps
        steps_text = "Implementation Steps:\n"
        for step in plan.steps:
            steps_text += f"{step.step_number}. [{step.action}] {step.description}\n"
            if step.apis_used:
                steps_text += f"   APIs: {', '.join(step.apis_used)}\n"
            steps_text += f"   Error Handling: {step.error_handling}\n"

        # Format validation rules
        validation_text = "Validation Rules:\n"
        for rule in plan.validation_rules:
            validation_text += f"- {rule}\n"

        # Format API references with examples
        api_refs_text = "API References:\n"
        for api in exploration_report.apis[:5]:  # Top 5 APIs
            api_refs_text += f"\n{api.function_name}:\n"
            api_refs_text += f"  Description: {api.description}\n"
            if api.examples:
                api_refs_text += f"  Example: {api.examples[0].code[:200]}...\n"

        # Format iteration history (feedback from previous attempts)
        history_text = ""
        if iteration_history:
            history_text = "\n\n=== PREVIOUS ITERATION FEEDBACK ===\n"
            for summary in iteration_history:
                history_text += f"\nIteration {summary.iteration}:\n"
                history_text += f"What Failed: {summary.what_failed}\n"
                history_text += f"Changes Made: {summary.what_changed}\n"
                history_text += f"Next Focus: {summary.next_focus}\n"
            history_text += "\nIMPORTANT: Address the issues from previous iterations!\n"
            history_text += "=== END FEEDBACK ===\n\n"

        # Build comprehensive prompt
        prompt = f"""Generate a Python tool implementation based on the following detailed plan.

{history_text}

=== TOOL SPECIFICATION ===

Tool Name: {plan.requirement_name}
Description: {plan.requirement_description}

File Location: tools/{plan.job_id}/{plan.task_id}/{plan.requirement_name}.py

=== IMPLEMENTATION PLAN ===

{steps_text}

Pseudo-Code:
{plan.pseudo_code}

{validation_text}

Expected Artifacts:
{', '.join(plan.expected_artifacts)}

=== API REFERENCES ===

{api_refs_text}

=== IMPLEMENTATION REQUIREMENTS ===

1. **Type Annotations:**
   - Use strict type hints for all parameters and return values
   - Import from typing: List, Dict, Optional, Union, etc.

2. **Docstring:**
   - Follow Google-style docstring format
   - Include Args, Returns, Raises, Examples sections
   - Specify units where applicable

3. **Validation:**
   - Implement ALL validation rules from the plan
   - Use assertions or explicit checks
   - Raise appropriate exceptions (ValueError, RuntimeError, TypeError)

4. **Error Handling:**
   - Follow error handling specified in each step
   - Provide clear error messages
   - Catch and re-raise with context

5. **Stateless Function:**
   - No global variables
   - No side effects
   - Output ONLY via return statement
   - Do not modify input parameters

6. **Code Quality:**
   - Follow PEP 8 style guidelines
   - Use descriptive variable names
   - Add comments for complex logic
   - Keep functions focused and simple

7. **Dependencies:**
   - Import only necessary libraries
   - Use standard libraries: rdkit, ase, pymatgen, pyscf
   - Handle import errors gracefully

=== OUTPUT FORMAT ===

Generate a single Python file at: tools/{plan.job_id}/{plan.task_id}/{plan.requirement_name}.py

The file should contain:
1. Module docstring
2. Imports (grouped: standard lib, third-party, typing)
3. Main function implementation
4. No main block or example execution code

Example structure:
```python
\"\"\"
Module for [tool purpose].

This module provides [description].
\"\"\"

# Standard library imports
import json
from typing import List, Dict, Optional

# Third-party imports
import rdkit
from rdkit import Chem
from rdkit.Chem import Descriptors

def {plan.requirement_name}(...) -> ...:
    \"\"\"
    [Complete docstring]
    \"\"\"
    # Implementation following the plan steps
    pass
```

Generate the tool now, following ALL requirements and the implementation plan.
"""

        return prompt

    async def _execute_llm_with_prompt(
        self,
        plan: ImplementationPlan,
        prompt: str
    ) -> dict:
        """
        Execute LLM backend CLI with custom prompt.

        Args:
            plan: Implementation plan (for task_id, job_id, requirement info)
            prompt: Custom prompt to use

        Returns:
            dict: Execution result
        """
        backend = self.settings.llm_backend.lower()

        try:
            if backend == "codex":
                # Import here to avoid circular dependency
                from app.utils.codex_utils import _run_codex_command

                # Build Codex command
                cmd = [
                    "codex", "exec",
                    "--model", "gpt-5",
                    "--dangerously-bypass-approvals-and-sandbox",
                    "--skip-git-repo-check",
                    "--cd", str(self.settings.tools_service_path),
                    prompt
                ]

                # Execute command
                result = await _run_codex_command(cmd, timeout=300)

            elif backend == "claude":
                # Import here to avoid circular dependency
                from app.utils.claude_utils import _run_claude_command

                # Build Claude Code command
                cmd = [
                    "claude",
                    "--dangerously-skip-permissions",
                    "-p", prompt
                ]

                # Execute command
                result = await _run_claude_command(cmd, cwd=str(self.settings.tools_service_path), timeout=300)
            else:
                return {
                    "success": False,
                    "tool_name": plan.requirement_name,
                    "error": f"Unknown LLM backend: {backend}"
                }

            # Check if file was created
            tools_dir = Path(self.settings.tools_path) / plan.job_id / plan.task_id
            output_file = tools_dir / f"{plan.requirement_name}.py"

            if result["success"] and output_file.exists():
                logger.info(f"Tool file generated: {output_file}")
                return {
                    "success": True,
                    "tool_name": plan.requirement_name,
                    "output_file": str(output_file)
                }
            else:
                logger.error(f"Tool file not created: {output_file}")
                return {
                    "success": False,
                    "tool_name": plan.requirement_name,
                    "error": f"File not created: {output_file}",
                    "stderr": result.get("stderr", "")
                }

        except Exception as e:
            logger.error(f"Error executing {backend}: {e}")
            return {
                "success": False,
                "tool_name": plan.requirement_name,
                "error": str(e)
            }

    async def cleanup(self):
        """Clean up implementer agent resources if needed."""
        logger.info("Implementer agent cleanup completed")
