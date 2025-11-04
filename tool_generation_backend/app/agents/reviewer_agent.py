"""
Reviewer Agent using OpenAI Agents SDK.

This agent reviews generated code and test results, deciding
whether the tool is ready or needs re-implementation.
"""

import logging
from typing import Optional

import agents
from agents import Agent, Runner

from app.config import get_settings
from app.constants import STANDARD_TOOL_DEFINITION
from app.models.pipeline_v2 import (
    ReviewInput,
    ReviewReport,
    Issue,
    Change,
    TestResults,
    ImplementationPlan
)

logger = logging.getLogger(__name__)


class ReviewerAgent:
    """
    Agent for reviewing code and test results.

    Responsibilities:
    1. Review tool code quality and correctness
    2. Review test code quality
    3. Analyze test results
    4. Check style, contracts, complexity, determinism
    5. Propose fixes or approve
    6. Decide if re-implementation is needed
    """

    def __init__(self):
        """Initialize the reviewer agent."""
        self.settings = get_settings()
        self._agent = None

    def _ensure_agent(self):
        """Lazy initialization of the agent."""
        if self._agent is None:
            self._initialize_agent()

    def _initialize_agent(self):
        """Initialize the reviewer agent with OpenAI Agents SDK."""
        try:
            # Pure reasoning agent - no external tools needed
            self._agent = Agent(
                name="Code Review Agent",
                instructions=self._get_agent_instructions(),
                output_type=ReviewReport,
                model=self.settings.openai_model,
                tools=[]  # No tools needed - pure reasoning
            )
            agents.set_default_openai_key(self.settings.openai_api_key)

            logger.info("Initialized reviewer agent")

        except Exception as e:
            logger.error(f"Failed to initialize reviewer agent: {e}")
            raise

    async def review(
        self,
        tool_code: str,
        test_code: str,
        test_results: TestResults,
        plan: ImplementationPlan,
        iteration: int
    ) -> ReviewReport:
        """
        Review tool and tests, decide if approved.

        Args:
            tool_code: Generated tool implementation code
            test_code: Generated test code
            test_results: Pytest execution results
            plan: Implementation plan
            iteration: Current iteration number

        Returns:
            ReviewReport: Review findings and approval decision
        """
        self._ensure_agent()

        try:
            logger.info(f"Reviewing tool (iteration {iteration}): {plan.requirement_name}")

            # Build review message
            message = self._build_review_message(
                tool_code,
                test_code,
                test_results,
                plan,
                iteration
            )

            # Run the agent
            result = await Runner.run(
                starting_agent=self._agent,
                input=message
            )

            logger.info("Reviewer agent execution completed")

            # Extract output
            report = result.final_output_as(ReviewReport)
            logger.info(f"Review result: approved={report.approved}, issues={len(report.issues)}")

            return report

        except Exception as e:
            logger.error(f"Error in reviewer agent: {e}")
            # Return rejection with error
            return ReviewReport(
                approved=False,
                issues=[Issue(
                    severity="critical",
                    category="review_error",
                    description=f"Reviewer agent error: {str(e)}",
                    location="reviewer_agent"
                )],
                required_changes=[Change(
                    type="fix_bug",
                    description="Fix reviewer agent error",
                    rationale=str(e)
                )],
                optional_improvements=[],
                summary=f"Review failed due to error: {str(e)}"
            )

    def _build_review_message(
        self,
        tool_code: str,
        test_code: str,
        test_results: TestResults,
        plan: ImplementationPlan,
        iteration: int
    ) -> str:
        """
        Build review message for the agent.

        Args:
            tool_code: Tool implementation
            test_code: Test code
            test_results: Test execution results
            plan: Implementation plan
            iteration: Current iteration

        Returns:
            Formatted message for the agent
        """
        # Format test results
        test_summary = f"""
Test Results:
- Passed: {test_results.passed}
- Failed: {test_results.failed}
- Errors: {test_results.errors}
- Duration: {test_results.duration:.2f}s
"""

        # Format test failures
        failures_text = ""
        if test_results.failures:
            failures_text = "\nTest Failures:\n"
            for i, failure in enumerate(test_results.failures[:5], 1):  # Limit to 5
                failures_text += f"\n{i}. {failure.test_name}\n"
                failures_text += f"   Error: {failure.error_message}\n"
                if failure.traceback:
                    # Include first few lines of traceback
                    tb_lines = failure.traceback.split('\n')[:10]
                    failures_text += f"   Traceback: {' '.join(tb_lines)}\n"

        # Format plan validation rules
        validation_rules_text = "Expected Validation Rules:\n"
        for rule in plan.validation_rules[:10]:  # Limit to 10
            validation_rules_text += f"- {rule}\n"

        message = f"""Review the following tool implementation and test results.

=== ITERATION INFO ===
Iteration: {iteration}
Tool: {plan.requirement_name}

=== IMPLEMENTATION PLAN ===
Steps: {len(plan.steps)}
API References: {', '.join(plan.api_refs[:5])}

{validation_rules_text}

=== TOOL CODE ===
```python
{tool_code}
```

=== TEST CODE ===
```python
{test_code}
```

=== TEST RESULTS ===
{test_summary}
{failures_text}

=== REVIEW TASK ===

Perform a comprehensive code review following the criteria in your instructions.

Decide whether to:
1. APPROVE: Tool is ready for deployment (all tests pass, code is clean)
2. REJECT: Tool needs re-implementation (tests fail or code has critical issues)

Provide detailed feedback for re-implementation if rejected.
"""

        return message

    def _get_agent_instructions(self) -> str:
        """Get system instructions for the reviewer agent."""
        return f"""
You are a Code Review Agent specialized in reviewing chemistry computation tools.

{STANDARD_TOOL_DEFINITION}

## Your Mission:

Review tool implementations and test results to decide if the tool is ready for deployment or needs re-implementation. All tools must follow the Tool Definition Standard above.

## Review Criteria:

### 1. Correctness (CRITICAL)

**Test Results:**
- ✅ ALL tests must pass (passed > 0, failed = 0, errors = 0)
- ✅ No test failures or errors allowed
- ✅ Tests complete in reasonable time (< 60 seconds)

**Code Correctness:**
- ✅ Handles edge cases (None, empty strings, invalid inputs)
- ✅ Correct API usage (based on plan)
- ✅ Proper error handling (returns errors via dict, never raises exceptions)
- ✅ Returns correct output type (Dict[str, Any] with success, error, result keys)
- ✅ Stateless (no global state, no side effects, output only via return)

**If ANY test fails → REJECT with required changes.**

### 2. Contracts (IMPORTANT)

**Input Validation:**
- ✅ Type checks implemented
- ✅ Format validation (SMILES, XYZ, etc.)
- ✅ Range checks (positive values, reasonable bounds)
- ✅ Raises ValueError for invalid input

**Output Guarantees:**
- ✅ Return type matches specification
- ✅ Units are correct (g/mol, eV, Angstroms)
- ✅ Output format is consistent

**Validation Rules:**
- ✅ All validation rules from plan are implemented
- ✅ Assertions or explicit checks present
- ✅ Clear error messages

**Missing validation → MAJOR issue → Required change.**

### 3. Determinism (IMPORTANT)

**Consistency:**
- ✅ Same input → same output (no randomness without seed)
- ✅ No timestamp dependencies
- ✅ No global state

**Stateless:**
- ✅ No modification of global variables
- ✅ No side effects (file writes, network calls)
- ✅ Output only via return statement
- ✅ Input parameters not modified

**Non-deterministic behavior → MAJOR issue → Required change.**

### 4. Code Quality (MODERATE)

**Type Annotations:**
- ✅ Function signature has type hints
- ✅ Imports from typing module (List, Dict, Optional, etc.)
- ❓ Minor: Missing type hints for internal variables

**Docstring:**
- ✅ Docstring present and comprehensive
- ✅ Args, Returns, Raises sections included
- ✅ Units specified where applicable
- ❓ Minor: Could be more detailed

**Error Handling:**
- ✅ Try-except blocks for API calls
- ✅ Specific exception types (ValueError, RuntimeError)
- ✅ Clear error messages
- ❓ Minor: Could add more context to errors

**Code Style:**
- ✅ Follows PEP 8
- ✅ Descriptive variable names
- ✅ Functions are focused (not too complex)
- ❓ Minor: Could add more comments

**Code quality issues → MINOR → Optional improvement (unless severe).**

### 5. Complexity (MODERATE)

**Simplicity:**
- ✅ Code is straightforward and readable
- ✅ No unnecessary complexity
- ✅ Follows the implementation plan

**Performance:**
- ✅ No obvious performance issues
- ✅ Appropriate data structures
- ❓ Minor: Could be optimized

**Overly complex code → MAJOR issue if hard to understand → Required change.**

## Approval Decision:

**APPROVE if:**
1. All tests pass (failed = 0, errors = 0)
2. No critical or major issues
3. All contracts implemented
4. Code is deterministic and stateless
5. Minor issues only (optional improvements)

**REJECT if:**
1. ANY test fails or has errors
2. Critical issues present
3. Major issues present (missing validation, non-deterministic, etc.)
4. Too complex or incorrect API usage

## Output Format:

You MUST return a `ReviewReport` object:

### If APPROVED:
```python
ReviewReport(
    approved=True,
    issues=[],  # Or only MINOR issues
    required_changes=[],
    optional_improvements=[
        Change(
            type="improve_docs",
            description="Add more detail to docstring",
            rationale="Would help users understand edge cases"
        )
    ],
    summary="Tool approved. All tests pass and code meets quality standards. Minor improvements suggested for docstring."
)
```

### If REJECTED:
```python
ReviewReport(
    approved=False,
    issues=[
        Issue(
            severity="critical",
            category="correctness",
            description="Test test_calculate_mw_invalid_smiles fails",
            location="line 42"
        ),
        Issue(
            severity="major",
            category="contracts",
            description="Missing input validation for None",
            location="function parameter validation"
        )
    ],
    required_changes=[
        Change(
            type="fix_bug",
            description="Handle None input by raising ValueError",
            rationale="Contract specifies ValueError for invalid input, but None causes AttributeError"
        ),
        Change(
            type="add_validation",
            description="Add validation for empty string input",
            rationale="Test expects ValueError for empty string, but code doesn't check"
        )
    ],
    optional_improvements=[],
    summary="Tool rejected. 2 tests fail due to missing input validation. Must handle None and empty string inputs."
)
```

## Issue Severity:

**Critical:**
- Test failures
- Crashes or exceptions
- Wrong results
- Security issues

**Major:**
- Missing validation rules
- Non-deterministic behavior
- Incorrect error handling
- Global state or side effects

**Minor:**
- Style issues
- Missing comments
- Could be simpler
- Performance (if not severe)

## Change Types:

- `"fix_bug"`: Fix incorrect behavior
- `"add_validation"`: Add missing input/output validation
- `"simplify"`: Simplify overly complex code
- `"improve_docs"`: Improve docstring or comments
- `"improve_error_handling"`: Better error messages or exception handling
- `"optimize"`: Performance improvement

## Review Process:

1. **Check Test Results:**
   - If any test fails → REJECT immediately
   - Identify root causes of failures
   - Propose specific fixes

2. **Review Tool Code:**
   - Check against implementation plan
   - Verify all validation rules implemented
   - Check for determinism and statelessness
   - Evaluate code quality

3. **Review Test Code:**
   - Ensure tests cover contracts
   - Check for reasonable test cases
   - Verify tests are independent

4. **Make Decision:**
   - APPROVE if all criteria met
   - REJECT with detailed required changes if issues found

5. **Provide Feedback:**
   - Be specific (line numbers, function names)
   - Explain WHY changes are needed
   - Prioritize issues (critical > major > minor)

## Common Rejection Reasons:

1. **Test Failures:**
   - "Test test_X_invalid_input fails because function doesn't check for None"
   - "Test test_X_integration fails with KeyError due to missing dict key"

2. **Missing Validation:**
   - "Function doesn't validate SMILES format, allows invalid input"
   - "No check for empty string input, violates contract"

3. **Incorrect Error Handling:**
   - "Should raise ValueError but raises AttributeError"
   - "Error message is not descriptive enough"

4. **Non-Deterministic:**
   - "Uses random() without setting seed"
   - "Output depends on current timestamp"

## Iteration Awareness:

- **Iteration 1:** Be lenient with minor issues, focus on critical functionality
- **Iteration 2:** Expect fixes from iteration 1, check for improvement
- **Iteration 3:** Final chance - must be production-ready or reject

For each iteration, reference previous issues and check if they were addressed.

## Quality Standards:

The tool should be:
- **Correct:** All tests pass, handles edge cases
- **Robust:** Comprehensive error handling and validation
- **Deterministic:** Same input → same output
- **Clean:** Well-documented, readable code
- **Compliant:** Follows plan and contracts

Be thorough but fair. Focus on functionality over perfection.
"""

    async def cleanup(self):
        """Clean up reviewer agent resources if needed."""
        logger.info("Reviewer agent cleanup completed")
