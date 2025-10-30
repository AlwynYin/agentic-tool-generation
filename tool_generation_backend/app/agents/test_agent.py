"""
Test Agent for generating test suites.

This agent uses Codex CLI to generate comprehensive test files
independently of the implementation to reduce coupling.
"""

import logging
from pathlib import Path
from typing import List

from app.config import get_settings
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
            logger.info(f"Generating tests for: {plan.requirement_name}")

            # Build test generation prompt
            prompt = self._build_test_prompt(tool_definition, plan, iteration_history)

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

    def _build_test_prompt(
        self,
        tool_definition: ToolDefinition,
        plan: ImplementationPlan,
        iteration_history: List[IterationSummary]
    ) -> str:
        """
        Build test generation prompt.

        Args:
            tool_definition: Tool specification
            plan: Implementation plan
            iteration_history: Previous iteration summaries

        Returns:
            Prompt for Codex
        """
        # Format contracts as test requirements
        contracts_text = "Contracts to Test:\n"
        for contract in tool_definition.contracts:
            contracts_text += f"- {contract}\n"

        # Format iteration history (feedback from previous test runs)
        history_text = ""
        if iteration_history:
            history_text = "\n\n=== PREVIOUS ITERATION FEEDBACK ===\n"
            for summary in iteration_history:
                history_text += f"\nIteration {summary.iteration}:\n"
                history_text += f"What Failed: {summary.what_failed}\n"
                history_text += f"Changes Made: {summary.what_changed}\n"
                history_text += f"Next Focus: {summary.next_focus}\n"
            history_text += "\nIMPORTANT: Write tests that will catch the issues from previous iterations!\n"
            history_text += "=== END FEEDBACK ===\n\n"

        prompt = f"""Generate a comprehensive test suite for the following tool.

{history_text}

=== TOOL SPECIFICATION ===

Function Name: {tool_definition.name}
Signature: {tool_definition.signature}

Docstring:
{tool_definition.docstring}

{contracts_text}

Example Usage:
{tool_definition.example_call}

Implementation Plan Summary:
- API References: {', '.join(plan.api_refs[:5])}
- Steps: {len(plan.steps)} implementation steps
- Validation Rules: {len(plan.validation_rules)} rules

=== TEST FILE LOCATION ===

File: tools/{plan.job_id}/{plan.task_id}/tests/test_{plan.requirement_name}.py
Fixtures Directory: tools/{plan.job_id}/{plan.task_id}/tests/data/

=== TEST REQUIREMENTS ===

Generate a comprehensive test suite with the following test types:

1. **Unit Tests** (REQUIRED)
   - Test input validation (type checks, format checks)
   - Test error handling (invalid inputs should raise appropriate exceptions)
   - Test edge cases (empty strings, None, boundary values)
   - Test output type and format
   - Keep tests fast (< 1 second each)

2. **Property Tests** (OPTIONAL, only if applicable)
   - Test invariants (e.g., symmetry, commutativity)
   - Test bounds (e.g., output always positive)
   - Use simple property checks, not hypothesis library

3. **Golden Tests** (RECOMMENDED)
   - Test against known good outputs
   - Use small, realistic examples
   - Create fixtures in tests/data/ directory
   - Compare actual vs expected with appropriate tolerance

4. **Integration Tests** (REQUIRED)
   - End-to-end test with realistic inputs
   - Test complete workflow from input to output
   - Use small molecules/structures for fast execution
   - Test with different parameter combinations

=== TEST EXAMPLES ===

**Unit Test Example:**
```python
def test_{plan.requirement_name}_valid_input():
    \"\"\"Test with valid input.\"\"\"
    result = {plan.requirement_name}("valid_input")
    assert isinstance(result, expected_type)
    assert result > 0  # or appropriate check

def test_{plan.requirement_name}_invalid_input():
    \"\"\"Test that invalid input raises ValueError.\"\"\"
    with pytest.raises(ValueError):
        {plan.requirement_name}(None)

    with pytest.raises(ValueError):
        {plan.requirement_name}("")
```

**Golden Test Example:**
```python
def test_{plan.requirement_name}_golden():
    \"\"\"Test against golden outputs.\"\"\"
    # Load golden data
    golden_data = {{
        "input1": expected_output1,
        "input2": expected_output2,
    }}

    for input_val, expected in golden_data.items():
        result = {plan.requirement_name}(input_val)
        assert abs(result - expected) < 0.001  # appropriate tolerance
```

**Integration Test Example:**
```python
def test_{plan.requirement_name}_integration():
    \"\"\"End-to-end integration test.\"\"\"
    # Use realistic example from chemistry domain
    result = {plan.requirement_name}("realistic_input")
    # Verify result is in expected range or format
    assert expected_min < result < expected_max
```

=== IMPLEMENTATION GUIDELINES ===

1. **Imports:**
   ```python
   import pytest
   import json
   from pathlib import Path
   # Import the tool function
   import sys
   sys.path.insert(0, str(Path(__file__).parent.parent))
   from {plan.requirement_name} import {plan.requirement_name}
   ```

2. **Fixtures (if needed):**
   - Create fixtures in tests/data/ directory
   - Use JSON for simple data
   - Use appropriate formats (XYZ, PDB, CIF) for structures
   - Keep fixtures small (< 100 atoms for molecules)

3. **Assertions:**
   - Use appropriate assertions (assert, pytest.raises, pytest.approx)
   - Include descriptive failure messages
   - Check both type and value

4. **Test Organization:**
   - Group related tests in classes (optional)
   - Use descriptive test names (test_<function>_<scenario>)
   - Add docstrings to explain what's being tested

5. **Performance:**
   - All tests should complete in < 60 seconds total
   - Individual tests should be < 1 second
   - Use small datasets
   - Avoid expensive computations (use force fields, not DFT)

6. **CPU-Only:**
   - Assume CPU-only execution
   - No GPU required
   - No CUDA dependencies

=== IMPORTANT NOTES ===

**Test Independently:**
- Write tests based on the SPECIFICATION (tool_definition), not the implementation
- This reduces coupling and catches implementation bugs
- Tests should pass for ANY correct implementation

**Don't Look at Implementation:**
- You should NOT read the implementation code
- Base tests on: signature, docstring, contracts, example usage
- This ensures tests validate the specification, not the current code

**Chemistry-Specific:**
- Use realistic chemistry examples (ethanol, benzene, water, aspirin)
- Use correct SMILES strings
- Test with valid molecular structures
- Check units (g/mol, eV, Angstroms)

=== OUTPUT FORMAT ===

Generate files at:
1. tools/{plan.job_id}/{plan.task_id}/tests/test_{plan.requirement_name}.py
2. tools/{plan.job_id}/{plan.task_id}/tests/data/<fixture_files> (if needed)

The test file should:
- Import pytest and necessary libraries
- Import the tool function
- Contain 5-15 test functions
- Cover all validation rules from contracts
- Include at least one integration test
- Run successfully with pytest

Generate the test suite now.
"""

        return prompt

    async def _execute_codex_test_generation(
        self,
        plan: ImplementationPlan,
        prompt: str
    ) -> dict:
        """
        Execute Codex CLI to generate test file.

        Args:
            plan: Implementation plan
            prompt: Test generation prompt

        Returns:
            dict: Execution result
        """
        from app.utils.codex_utils import _run_codex_command

        try:
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
            logger.error(f"Error executing Codex for test generation: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def cleanup(self):
        """Clean up test agent resources if needed."""
        logger.info("Test agent cleanup completed")
