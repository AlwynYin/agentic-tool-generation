"""
Planner Agent using OpenAI Agents SDK.

This agent creates detailed, step-by-step implementation plans
from tool definitions and exploration reports.
"""

import logging
from typing import Optional, List

import agents
from agents import Agent, Runner

from app.config import get_settings
from app.constants import STANDARD_TOOL_DEFINITION
from app.models.pipeline_v2 import (
    ToolDefinition,
    ExplorationReport,
    ImplementationPlan,
    PlanStep
)

logger = logging.getLogger(__name__)


class PlannerAgent:
    """
    Agent for creating detailed implementation plans.

    Responsibilities:
    1. Map input_spec → API calls → output_spec
    2. Define step-by-step execution plan
    3. Specify data transformations
    4. Include unit handling
    5. Define error handling strategy
    6. Specify validation rules
    7. Generate pseudo-code outline
    """

    def __init__(self, available_packages: List[str]):
        """Initialize the planner agent.

        Args:
            available_packages: List of available package names for implementation planning
        """
        self.settings = get_settings()
        self.available_packages = available_packages
        self._agent = None
        logger.info(f"Initialized planner agent with {len(self.available_packages)} available packages")

    def _ensure_agent(self):
        """Lazy initialization of the agent."""
        if self._agent is None:
            self._initialize_agent()

    def _initialize_agent(self):
        """Initialize the planner agent with OpenAI Agents SDK."""
        try:
            # Pure reasoning agent - no external tools needed
            self._agent = Agent(
                name="Implementation Planner Agent",
                instructions=self._get_agent_instructions(),
                output_type=ImplementationPlan,
                model=self.settings.openai_model,
                tools=[]  # No tools needed - pure reasoning
            )
            agents.set_default_openai_key(self.settings.openai_api_key)

            logger.info("Initialized planner agent")

        except Exception as e:
            logger.error(f"Failed to initialize planner agent: {e}")
            raise

    async def create_plan(
        self,
        tool_definition: ToolDefinition,
        exploration_report: ExplorationReport,
        task_id: str = "unknown",
        job_id: str = "unknown"
    ) -> ImplementationPlan:
        """
        Create a detailed implementation plan.

        Args:
            tool_definition: Tool specification from Intake Agent
            exploration_report: API findings from Search Agent
            task_id: Task identifier
            job_id: Job identifier

        Returns:
            ImplementationPlan: Detailed step-by-step plan
        """
        self._ensure_agent()

        try:
            logger.info(f"Creating implementation plan for: {tool_definition.name}")

            # Build message for the agent
            message = self._build_planning_message(tool_definition, exploration_report)

            # Run the agent
            result = await Runner.run(
                starting_agent=self._agent,
                input=message
            )

            logger.info("Planner agent execution completed")

            # Extract output
            plan = result.final_output_as(ImplementationPlan)

            # Add task_id and job_id (agent can't know these)
            plan.task_id = task_id
            plan.job_id = job_id
            plan.requirement_name = tool_definition.name
            # plan.requirement_description = tool_definition.docstring
            if not plan.requirement_signature:
                plan.requirement_signature = tool_definition.signature
            if not plan.requirement_docstring:
                plan.requirement_docstring = tool_definition.docstring
            if not plan.requirement_contracts:
                plan.requirement_contracts = tool_definition.contracts

            logger.info(f"Plan created with {len(plan.steps)} steps")

            return plan

        except Exception as e:
            logger.error(f"Error in planner agent: {e}")
            # Return minimal plan with error indication
            return ImplementationPlan(
                task_id=task_id,
                job_id=job_id,
                requirement_name=tool_definition.name,
                requirement_signature="",
                requirement_docstring=f"Error creating plan: {str(e)}",
                requirement_contracts=[],
                steps=[],
                validation_rules=[],
                expected_artifacts=[]
            )

    def _build_planning_message(
        self,
        tool_definition: ToolDefinition,
        exploration_report: ExplorationReport
    ) -> str:
        """
        Build message for the planner agent.

        Args:
            tool_definition: Tool specification
            exploration_report: API findings (markdown file reference)

        Returns:
            Formatted message for the agent
        """
        # Read markdown search results
        search_results_text = ""
        if exploration_report.api_refs_file and exploration_report.api_refs_file.endswith('.md'):
            try:
                with open(exploration_report.api_refs_file, 'r') as f:
                    markdown_content = f.read()
                    search_results_text = f"""
---

## API Exploration Results

The following information was gathered from documentation research:

{markdown_content}

---
"""
            except Exception as e:
                logger.error(f"Failed to read markdown search results: {e}")
                search_results_text = "\n---\n\nNo API exploration results available.\n\n---\n"
        else:
            search_results_text = "\n---\n\nNo API exploration results available.\n\n---\n"

        # Format contracts
        contracts_text = "\n".join([f"- {c}" for c in tool_definition.contracts])

        return f"""Create a detailed implementation plan for the following tool:

**Function Name:** {tool_definition.name}

**Signature:** {tool_definition.signature}

**Docstring:**
{tool_definition.docstring}

**Contracts:**
{contracts_text}

{search_results_text}

Create a comprehensive implementation plan following the structure in your instructions.
"""

    def _get_agent_instructions(self) -> str:
        """Get system instructions for the planner agent."""
        return f"""
You are an Implementation Planning Agent specialized in creating detailed, executable plans for chemistry computation tools.

{STANDARD_TOOL_DEFINITION}

## Your Mission:

Analyze the tool definition and available APIs to create a precise, step-by-step implementation plan that guides the code generation. All implementation plans must ensure the tool follows the Tool Definition Standard above.

## Output Structure:

You MUST return an `ImplementationPlan` object with:

```python
ImplementationPlan(
    task_id="",  # Will be filled by system
    job_id="",  # Will be filled by system
    requirement_name="",  # Will be filled by system
    requirement_signature="",  # Revised signature of tool
    requirement_docstring="",  # Revised docstring of tool
    requirement_contracts=[],  # Revised contracts of tool
    api_refs=[], # a list of apis to be used
    steps=[PlanStep(...), PlanStep(...), ...],
    validation_rules=["Rule 1", "Rule 2", ...],
    expected_artifacts=["file1.py", "data structure description", ...]
)
```

## Step 1: Revise the tool definition
If you believe any of the signature, docstring, and contracts needs to be revised, generate your revised requirement_signature, requirement_docstring, and requirement_contracts respectively.
If you believe any of them does not need revision, leave them blank, e.g. requirement_signature="", requirement_docstring="", requirement_contracts=[]

## Step 2: Create Step-by-Step Plan

Break down implementation into discrete steps. Each step is a `PlanStep`:

```python
PlanStep(
    step_number=1,
    action="parse_input",  # or "call_api", "validate", "transform", "format_output"
    description="Detailed description of what this step does",
    apis_used=["api.function.name"],
    error_handling="How to handle errors in this step"
)
```

**Action Types:**
- `"parse_input"`: Parse and validate input parameters
- `"call_api"`: Call external library function
- `"transform"`: Transform data between steps
- `"validate"`: Validate intermediate or final results
- `"format_output"`: Format results for return
- `"error_handling"`: Handle specific error cases

**Typical Flow:**
1. Parse input (validate SMILES, XYZ, etc.)
2. Call API to convert input to library object (e.g., Mol object)
3. Call API to perform computation
4. Transform result if needed
5. Validate output
6. Format output for return

**Example:**
```python
steps=[
    PlanStep(
        step_number=1,
        action="parse_input",
        description="Validate SMILES string is non-empty and contains only valid characters",
        apis_used=[],
        error_handling="Return {{success: False, error: 'SMILES cannot be empty', result: None}} if SMILES is empty or None"
    ),
    PlanStep(
        step_number=2,
        action="call_api",
        description="Convert SMILES to RDKit Mol object",
        apis_used=["rdkit.Chem.MolFromSmiles"],
        error_handling="Return {{success: False, error: 'Invalid SMILES string', result: None}} if parsing fails (returns None)"
    ),
    PlanStep(
        step_number=3,
        action="call_api",
        description="Calculate molecular weight using RDKit descriptor",
        apis_used=["rdkit.Chem.Descriptors.MolWt"],
        error_handling="Return {{success: False, error: 'Calculation failed', result: None}} if descriptor calculation fails"
    ),
    PlanStep(
        step_number=4,
        action="validate",
        description="Ensure molecular weight is positive float",
        apis_used=[],
        error_handling="Return {{success: False, error: 'Invalid weight', result: None}} if weight is non-positive"
    ),
    PlanStep(
        step_number=5,
        action="format_output",
        description="Return success result with molecular weight in g/mol",
        apis_used=[],
        error_handling="Return {{success: True, error: None, result: weight}} with weight as float"
    )
]
```

## Step 3: Define Validation Rules

List specific validation checks to implement:

**Input Validation:**
- Type checks
- Format checks
- Range checks
- Value checks

**Output Validation:**
- Type guarantees
- Range guarantees
- Format guarantees
- Determinism checks

**Example:**
```python
validation_rules=[
    "Input: smiles must be non-empty string",
    "Input: smiles must parse successfully with rdkit.Chem.MolFromSmiles",
    "Output: must return Dict[str, Any] with 'success', 'error', 'result' keys",
    "Output: result field must contain positive float molecular weight in g/mol",
    "Output: molecular weight must be in range (0, 10000) g/mol for typical organic molecules",
    "Behavior: function must be deterministic (same input → same output)",
    "Behavior: function must be stateless (no global state, no side effects)",
    "Error: return success=False with error message for invalid SMILES",
    "Error: return success=False with error message for calculation failures",
    "Error: never raise exceptions - all errors via return dict"
]
```

## Step 4: Specify Expected Artifacts

List what will be created:

**Typical Artifacts:**
- Main tool file: `{{function_name}}.py`
- Data structures returned (dict keys, list structure)
- Any intermediate files if applicable

**Example:**
```python
expected_artifacts=[
    "calculate_molecular_weight.py - main tool file",
    "Returns: Dict[str, Any] with success (bool), error (str|None), result (float molecular weight in g/mol)",
    "No intermediate files created"
]
```

## Planning Guidelines:

**Keep It Simple:**
- 4-8 steps typical for most tools
- Each step should be atomic and testable
- Avoid over-complication

**Be Specific:**
- Name exact API functions
- Specify units (eV, Angstroms, g/mol, etc.)
- Define exact error messages to return in error field
- Specify structure of result field

**Think About Edge Cases:**
- What if input is None?
- What if API returns None?
- What if computation fails?
- What if result is unexpected?
- All error cases must return dict, never raise exceptions

**Consider Performance:**
- Note if computations are expensive
- Suggest reasonable timeouts
- Flag operations that might be slow

## Quality Standards:

Your plan should be:
- **Executable:** Clear enough for code generation
- **Complete:** Covers all requirements from tool definition
- **Robust:** Includes comprehensive error handling
- **Scientific:** Uses correct units and terminology
- **Efficient:** Avoids unnecessary complexity

Focus on creating a plan that directly translates to clean, working code.
"""

    async def cleanup(self):
        """Clean up planner agent resources if needed."""
        logger.info("Planner agent cleanup completed")
