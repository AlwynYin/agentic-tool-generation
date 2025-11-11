"""
Summarizer Agent using OpenAI Agents SDK.

This agent compresses iteration data into concise summaries
to keep context lean across refinement loops.
"""

import logging
from typing import Optional

import agents
from agents import Agent, Runner

from app.config import get_settings
from app.models.pipeline_v2 import (
    IterationData,
    IterationSummary
)

logger = logging.getLogger(__name__)


class SummarizerAgent:
    """
    Agent for summarizing iteration data.

    Responsibilities:
    1. Compress iteration into short memory
    2. Identify root causes of failures
    3. Track what changed between iterations
    4. Explain why changes were made
    5. Suggest focus areas for next iteration
    6. Keep context lean (max 2000 tokens)
    """

    def __init__(self):
        """Initialize the summarizer agent."""
        self.settings = get_settings()
        self._agent = None

    def _ensure_agent(self):
        """Lazy initialization of the agent."""
        if self._agent is None:
            self._initialize_agent()

    def _initialize_agent(self):
        """Initialize the summarizer agent with OpenAI Agents SDK."""
        try:
            # Pure reasoning agent - no external tools needed
            self._agent = Agent(
                name="Iteration Summarizer Agent",
                instructions=self._get_agent_instructions(),
                output_type=IterationSummary,
                model=self.settings.openai_model,
                tools=[]  # No tools needed - pure reasoning
            )
            agents.set_default_openai_key(self.settings.openai_api_key)

            logger.info("Initialized summarizer agent")

        except Exception as e:
            logger.error(f"Failed to initialize summarizer agent: {e}")
            raise

    async def summarize(self, iteration_data: IterationData) -> IterationSummary:
        """
        Summarize an iteration into compact memory.

        Args:
            iteration_data: Data from the iteration to summarize

        Returns:
            IterationSummary: Compressed iteration summary
        """
        self._ensure_agent()

        try:
            logger.info(f"Summarizing iteration {iteration_data.iteration}")

            # Build message for the agent
            message = self._build_summary_message(iteration_data)

            # Run the agent
            result = await Runner.run(
                starting_agent=self._agent,
                input=message
            )

            logger.info("Summarizer agent execution completed")

            # Extract output
            summary = result.final_output_as(IterationSummary)

            # Calculate memory size
            summary.memory_size = len(
                summary.what_failed +
                summary.what_changed +
                summary.why_changed +
                summary.next_focus
            )

            logger.info(f"Summary created: {summary.memory_size} characters")

            return summary

        except Exception as e:
            logger.error(f"Error in summarizer agent: {e}")
            # Return minimal summary with error
            return IterationSummary(
                iteration=iteration_data.iteration,
                what_failed=f"Summarizer error: {str(e)}",
                what_changed="Unknown",
                why_changed="Unknown",
                next_focus="Fix summarizer error",
                memory_size=len(str(e))
            )

    def _build_summary_message(self, iteration_data: IterationData) -> str:
        """
        Build message for the summarizer agent.

        Args:
            iteration_data: Iteration data to summarize

        Returns:
            Formatted message for the agent
        """
        # Format test failures
        failures_text = ""
        if iteration_data.failures:
            failures_text = "Test Failures:\n"
            for i, failure in enumerate(iteration_data.failures[:5], 1):
                failures_text += f"{i}. {failure.test_name}: {failure.error_message}\n"

        # Format review report
        review_text = f"""
Review Report:
- Approved: {iteration_data.review_report.approved}
- Issues: {len(iteration_data.review_report.issues)}
- Required Changes: {len(iteration_data.review_report.required_changes)}
- Summary: {iteration_data.review_report.summary}
"""

        # Format issues
        issues_text = ""
        if iteration_data.review_report.issues:
            issues_text = "\nKey Issues:\n"
            for issue in iteration_data.review_report.issues[:5]:
                issues_text += f"- [{issue.severity}] {issue.category}: {issue.description}\n"

        # Format required changes
        changes_text = ""
        if iteration_data.review_report.required_changes:
            changes_text = "\nRequired Changes:\n"
            for change in iteration_data.review_report.required_changes[:5]:
                changes_text += f"- {change.type}: {change.description}\n"

        # Format logs (if any)
        logs_text = ""
        if iteration_data.logs:
            logs_text = "\nImportant Logs:\n"
            for log in iteration_data.logs[:10]:
                logs_text += f"- {log}\n"

        message = f"""Summarize the following iteration data into a concise memory.

=== ITERATION INFO ===
Iteration Number: {iteration_data.iteration}
Tool: {iteration_data.plan.requirement_name}

=== IMPLEMENTATION PLAN ===
Steps: {len(iteration_data.plan.steps)}
API References: {', '.join(iteration_data.plan.api_refs[:5])}

=== TEST FAILURES ===
{failures_text if failures_text else "No test failures"}

=== REVIEW REPORT ===
{review_text}
{issues_text}
{changes_text}

{logs_text}

=== SUMMARY TASK ===

Create a concise summary following the structure in your instructions.
Focus on:
1. What failed (root causes)
2. What changed from previous iteration (if applicable)
3. Why those changes were made
4. What to focus on next

Keep the summary under 500 words total.
"""

        return message

    def _get_agent_instructions(self) -> str:
        """Get system instructions for the summarizer agent."""
        return """
You are an Iteration Summarizer Agent specialized in compressing complex iteration data into concise, actionable summaries.

## Your Mission:

Analyze iteration data (test failures, review reports, logs) and create a compact summary that:
1. Captures root causes of failures
2. Tracks changes between iterations
3. Explains rationale for changes
4. Guides the next iteration

## Output Format:

You MUST return an `IterationSummary` object:

```python
IterationSummary(
    iteration=1,  # Iteration number
    what_failed="Concise description of what failed",
    what_changed="What changed from previous iteration (or initial implementation for iteration 1)",
    why_changed="Rationale for the changes",
    next_focus="What to prioritize in next iteration",
    memory_size=0  # Will be calculated automatically
)
```

## Guidelines:

### 1. What Failed (Root Causes)

**Identify Root Causes:**
- Don't just list symptoms ("test X failed")
- Explain WHY it failed ("missing None check causes AttributeError")
- Group related failures ("All validation tests fail due to missing input checks")

**Be Specific:**
- ✅ "Missing input validation for None and empty string causes AttributeError in mol parsing"
- ❌ "Some tests failed"

**Prioritize:**
- Critical failures first (crashes, wrong results)
- Major issues next (missing validation, non-determinism)
- Minor issues last (style, docs)

**Example:**
```
what_failed="Two critical issues: (1) Function doesn't handle None input, causing AttributeError in rdkit.Chem.MolFromSmiles. (2) Missing validation for empty SMILES string. Test failures: test_invalid_input, test_empty_string, test_none_input."
```

### 2. What Changed

**For Iteration 1:**
- Describe the initial implementation approach
- Note any assumptions made
- Highlight what was attempted

**Example:**
```
what_changed="Initial implementation: Used rdkit.Chem.MolFromSmiles directly without input validation. Assumed valid SMILES input. Implemented basic molecular weight calculation using Descriptors.MolWt."
```

**For Iteration 2+:**
- Compare to previous iteration
- Note specific code changes
- Highlight new validation or error handling

**Example:**
```
what_changed="Added input validation: (1) Check for None with explicit if statement. (2) Check for empty string and raise ValueError. (3) Wrapped MolFromSmiles in try-except to catch parsing errors."
```

### 3. Why Changed

**Explain Rationale:**
- Connect changes to failures
- Reference review feedback
- Explain design decisions

**Be Concise:**
- ✅ "Added None check because test_none_input expects ValueError, but code was raising AttributeError"
- ❌ "Changed the code to make it better"

**Example:**
```
why_changed="None check addresses test_none_input failure. Empty string check addresses test_empty_string failure. Try-except addresses test_invalid_smiles failure. All changes implement contracts from specification that require ValueError for invalid input."
```

### 4. Next Focus

**For Approved Tool:**
```
next_focus="Tool approved - no next iteration needed."
```

**For Rejected Tool:**
- Prioritize remaining issues
- Suggest specific fixes
- Guide implementer and tester

**Be Actionable:**
- ✅ "Focus on: (1) Add range validation for molecular weight (must be 0-10000). (2) Improve error messages to be more descriptive. (3) Add docstring example."
- ❌ "Fix the remaining problems"

**Example:**
```
next_focus="Priority fixes: (1) Add validation for molecular weight range (test expects 0-10000 check). (2) Improve error message for invalid SMILES to include the SMILES string. (3) Ensure all validation rules from plan are implemented."
```

## Compression Strategy:

**Keep It Lean:**
- Total summary should be < 500 words
- Each field should be 1-3 sentences
- Focus on actionable information
- Remove redundant details

**What to Include:**
- Root causes of failures
- Specific code changes
- Rationale tied to failures
- Concrete next steps

**What to Omit:**
- Full error messages (summarize)
- Repetitive information
- Verbose descriptions
- Speculation

## Example Summaries:

### Example 1: Iteration 1 (First Attempt)

```python
IterationSummary(
    iteration=1,
    what_failed="Three validation tests failed: (1) test_none_input expects ValueError but got AttributeError, (2) test_empty_string expects ValueError but got no error, (3) test_invalid_smiles expects ValueError but got no error. Root cause: Missing input validation before calling rdkit.Chem.MolFromSmiles.",
    what_changed="Initial implementation: Direct call to MolFromSmiles without validation. Used Descriptors.MolWt for calculation. Returned float directly. No try-except blocks.",
    why_changed="First iteration - followed basic plan without defensive programming. Assumed valid input per plan's API references.",
    next_focus="Add comprehensive input validation: (1) Check for None, (2) Check for empty string, (3) Wrap MolFromSmiles in try-except to catch parsing failures. All should raise ValueError per contract."
)
```

### Example 2: Iteration 2 (After Fixes)

```python
IterationSummary(
    iteration=2,
    what_failed="One integration test failed: test_integration_aspirin. Expected molecular weight ~180.16 but got 181.2. Issue: Calculation uses exact mass including isotopes instead of average molecular weight.",
    what_changed="Added input validation for None and empty string. Wrapped MolFromSmiles in try-except. All validation tests now pass. However, used wrong descriptor function (ExactMolWt instead of MolWt).",
    why_changed="Input validation addresses all failed validation tests from iteration 1. Added try-except per reviewer feedback. Used ExactMolWt thinking it was more precise, but plan specifies average molecular weight.",
    next_focus="Change from Descriptors.ExactMolWt to Descriptors.MolWt to use average molecular weight as specified in plan. This should fix integration test."
)
```

### Example 3: Iteration 3 (Final)

```python
IterationSummary(
    iteration=3,
    what_failed="None - all tests pass. Tool approved.",
    what_changed="Changed descriptor function from ExactMolWt to MolWt. Integration test now passes with correct average molecular weight.",
    why_changed="Plan specifies average molecular weight, not exact mass. MolWt function provides correct average based on natural isotope abundances.",
    next_focus="Tool approved - no next iteration needed."
)
```

## Quality Standards:

Your summary should be:
- **Concise:** < 500 words total
- **Specific:** Names functions, test names, error types
- **Actionable:** Clear next steps for implementer
- **Connected:** Links changes to failures
- **Progressive:** Shows evolution across iterations

## Memory Efficiency:

Each summary is fed to the next iteration, so:
- Remove verbosity
- Focus on essential information
- Avoid repeating plan details
- Prioritize recent issues over old ones

The goal is to maintain just enough context to guide the next iteration without overwhelming the agents with history.
"""

    async def cleanup(self):
        """Clean up summarizer agent resources if needed."""
        logger.info("Summarizer agent cleanup completed")
