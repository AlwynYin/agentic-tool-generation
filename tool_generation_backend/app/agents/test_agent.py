"""
Test Agent for generating test suites.

This agent uses Codex CLI to generate comprehensive test files
independently of the implementation to reduce coupling.
"""

import logging
from pathlib import Path
from typing import Dict, List

from app.config import get_settings
from app.constants import STANDARD_TOOL_DEFINITION
from app.models.pipeline_v2 import (
    ToolDefinition,
    ImplementationPlan,
    TestResult,
    IterationSummary
)

logger = logging.getLogger(__name__)


class TestAgent:
    """
    Agent for generating test suites.

    Uses Codex CLI to:
    1. Generate test file independently of implementation
    2. Create unit tests
    3. Create property tests (optional)
    4. Create golden tests (optional)
    5. Create integration tests
    6. Generate fixtures
    """

    def __init__(self):
        """Initialize the test agent."""
        self.settings = get_settings()

    async def generate_tests(
        self,
        tool_definition: ToolDefinition,
        plan: ImplementationPlan,
        iteration_history: List[IterationSummary]
    ) -> TestResult:
        """
        Generate test suite for tool.

        Args:
            tool_definition: Tool specification from Intake Agent
            plan: Implementation plan from Planner Agent
            iteration_history: Summaries from previous iterations

        Returns:
            TestResult: Generated test file and fixtures
        """
        try:
            logger.info(f"Generating/updating tests for: {plan.requirement_name}")

            # Write test context files
            context_files = self._write_test_context_files(tool_definition, plan, iteration_history)

            # Build brief test generation prompt
            prompt = self._build_test_prompt(tool_definition, plan, iteration_history, context_files)

            # Execute Codex to generate test file
            result = await self._execute_codex_test_generation(plan, prompt)

            if result["success"]:
                # Read generated test code
                test_file_path = result["test_file_path"]
                with open(test_file_path, 'r') as f:
                    test_code = f.read()

                logger.info(f"Tests generated successfully: {test_file_path}")

                return TestResult(
                    success=True,
                    test_file_path=test_file_path,
                    test_code=test_code,
                    fixtures_created=result.get("fixtures_created", []),
                    test_types=result.get("test_types", ["unit", "integration"]),
                    error=None
                )
            else:
                logger.error(f"Test generation failed: {result.get('error', 'Unknown error')}")
                return TestResult(
                    success=False,
                    test_file_path="",
                    test_code="",
                    fixtures_created=[],
                    test_types=[],
                    error=result.get("error", "Unknown error")
                )

        except Exception as e:
            logger.error(f"Error in test agent: {e}")
            return TestResult(
                success=False,
                test_file_path="",
                test_code="",
                fixtures_created=[],
                test_types=[],
                error=f"Test agent error: {str(e)}"
            )

    def _write_test_context_files(
        self,
        tool_definition: ToolDefinition,
        plan: ImplementationPlan,
        iteration_history: List[IterationSummary]
    ) -> Dict[str, str]:
        """
        Write test context files to disk for the LLM to reference.

        Args:
            tool_definition: Tool specification
            plan: Implementation plan
            iteration_history: Previous iteration summaries

        Returns:
            Dict[str, str]: Mapping of file purpose to file path
        """
        # Create directories
        tools_dir = Path(self.settings.tools_path) / plan.job_id / plan.task_id
        plan_dir = tools_dir / "plan"
        context_dir = tools_dir / "context"

        plan_dir.mkdir(parents=True, exist_ok=True)
        context_dir.mkdir(parents=True, exist_ok=True)

        file_paths = {}

        try:
            # 1. Write test requirements
            test_req_file = plan_dir / "test_requirements.txt"
            with open(test_req_file, 'w') as f:
                f.write(f"# Test Requirements for {plan.requirement_name}\n\n")
                f.write("## Test Types Required\n\n")
                f.write("1. Unit tests - Test individual functions and edge cases\n")
                f.write("2. Property tests - Test mathematical/chemical properties\n")
                f.write("3. Golden tests - Test against known reference values\n")
                f.write("4. Integration tests - Test end-to-end workflows\n\n")
                f.write("## Coverage Requirements\n\n")
                f.write("- Test all input validation rules\n")
                f.write("- Test all error conditions (verify success=False and error message)\n")
                f.write("- Test stateless behavior\n")
                f.write("- Test dict return format\n")

            file_paths["test_requirements"] = str(test_req_file)
            logger.info(f"Wrote test requirements to: {test_req_file}")

            # 2. Write contracts
            contracts_file = plan_dir / "contracts.txt"
            with open(contracts_file, 'w') as f:
                f.write(f"# Contracts for {plan.requirement_name}\n\n")
                f.write("## From Tool Definition\n\n")
                for i, contract in enumerate(tool_definition.contracts, 1):
                    f.write(f"{i}. {contract}\n")
                f.write("\n## From Implementation Plan\n\n")
                for i, rule in enumerate(plan.validation_rules, 1):
                    f.write(f"{i}. {rule}\n")

            file_paths["contracts"] = str(contracts_file)
            logger.info(f"Wrote contracts to: {contracts_file}")

            # 3. Write iteration history (if exists)
            if iteration_history:
                history_file = context_dir / "test_iteration_history.txt"
                with open(history_file, 'w') as f:
                    f.write(f"# Test Iteration History for {plan.requirement_name}\n\n")
                    f.write("Tests have been generated before. Review previous iterations to fix failing tests.\n\n")

                    for summary in iteration_history:
                        f.write(f"## Iteration {summary.iteration}\n\n")
                        f.write(f"**What Failed:** {summary.what_failed}\n\n")
                        f.write(f"**Next Focus:** {summary.next_focus}\n\n")
                        f.write("---\n\n")

                file_paths["history"] = str(history_file)
                logger.info(f"Wrote test iteration history to: {history_file}")

            return file_paths

        except Exception as e:
            logger.error(f"Failed to write test context files: {e}")
            return {}

    def _build_test_prompt(
        self,
        tool_definition: ToolDefinition,
        plan: ImplementationPlan,
        iteration_history: List[IterationSummary],
        context_files: Dict[str, str]
    ) -> str:
        """
        Build brief test generation prompt with file references.

        Args:
            tool_definition: Tool specification
            plan: Implementation plan
            iteration_history: Previous iteration summaries
            context_files: Dict mapping file purpose to file path

        Returns:
            Brief prompt for LLM backend with file references
        """
        # Build relative paths
        tools_dir_rel = f"tools/{plan.job_id}/{plan.task_id}"
        tool_file = f"{tools_dir_rel}/{plan.requirement_name}.py"
        test_file = f"{tools_dir_rel}/tests/test_{plan.requirement_name}.py"

        # Build context file references
        context_refs = []
        if "test_requirements" in context_files:
            context_refs.append(f"- Test requirements: {context_files['test_requirements']}")
        if "contracts" in context_files:
            context_refs.append(f"- Contracts to validate: {context_files['contracts']}")
        if "history" in context_files:
            context_refs.append(f"- Previous test iteration feedback: {context_files['history']}")

        context_refs_text = "\n".join(context_refs)

        # Build brief prompt
        prompt = f"""You are generating or updating comprehensive tests for a Python chemistry computation tool.

{STANDARD_TOOL_DEFINITION}

## Task

**Tool Name:** {plan.requirement_name}
**Tool File:** {tool_file}
**Test File:** {test_file}
**Fixtures Directory:** {tools_dir_rel}/tests/data/

## Tool Specification

**Function Signature:** {tool_definition.signature}

**Docstring:**
```
{tool_definition.docstring}
```

**Example Usage:**
```python
{tool_definition.example_call}
```

## Context Files

Read the following files for test requirements and contracts:

{context_refs_text}

## Instructions

1. **Read all context files** to understand what needs to be tested
2. **Test the tool specification**, not the implementation (don't read the tool file)
3. **Test the dict return format**:
   - Verify "success", "error", "result" keys exist
   - Test success=True cases with valid inputs
   - Test success=False cases with invalid inputs
   - Verify error messages are descriptive
4. **Test stateless behavior**: Call function multiple times, verify no side effects
5. **Follow test types**: Unit, property, golden, integration tests
6. **Update existing tests** if iteration history exists (fix failing tests based on feedback)

## Test Requirements

- Use pytest framework
- Import: `import pytest`, `from {plan.requirement_name} import {plan.requirement_name}`
- 5-15 test functions covering all validation rules
- Fast tests (< 1 second each, < 60 seconds total)
- CPU-only (no GPU required)
- Create fixtures in tests/data/ if needed

## Output

Generate/update the test file at: {test_file}

If the file already exists, UPDATE it based on feedback in the iteration history. Otherwise, create it from scratch.
"""

        return prompt

    async def _execute_codex_test_generation(
        self,
        plan: ImplementationPlan,
        prompt: str
    ) -> dict:
        """
        Execute LLM backend CLI to generate test file.

        Args:
            plan: Implementation plan
            prompt: Test generation prompt

        Returns:
            dict: Execution result
        """
        backend = self.settings.llm_backend.lower()

        try:
            # Execute backend-specific query
            if backend == "codex":
                from app.utils.codex_utils import run_codex_query
                result = await run_codex_query(
                    query=prompt,
                    working_dir=str(self.settings.tools_service_path),
                    timeout=300
                )
            elif backend == "claude":
                from app.utils.claude_utils import run_claude_query
                result = await run_claude_query(
                    query=prompt,
                    working_dir=str(self.settings.tools_service_path),
                    timeout=300
                )
            else:
                return {
                    "success": False,
                    "error": f"Unknown LLM backend: {backend}"
                }

            # Check if test file was created
            test_dir = Path(self.settings.tools_path) / plan.job_id / plan.task_id / "tests"
            test_file = test_dir / f"test_{plan.requirement_name}.py"

            # Check for fixtures
            fixtures_dir = test_dir / "data"
            fixtures_created = []
            if fixtures_dir.exists():
                fixtures_created = [str(f) for f in fixtures_dir.glob("*") if f.is_file()]

            if result["success"] and test_file.exists():
                logger.info(f"Test file generated: {test_file}")
                return {
                    "success": True,
                    "test_file_path": str(test_file),
                    "fixtures_created": fixtures_created,
                    "test_types": ["unit", "integration"]  # Could parse test file to detect types
                }
            else:
                logger.error(f"Test file not created: {test_file}")
                return {
                    "success": False,
                    "error": f"Test file not created: {test_file}",
                    "stderr": result.get("stderr", "")
                }

        except Exception as e:
            logger.error(f"Error executing {backend} for test generation: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def cleanup(self):
        """Clean up test agent resources if needed."""
        logger.info("Test agent cleanup completed")
