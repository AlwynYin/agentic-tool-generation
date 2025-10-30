"""
Planner Agent using OpenAI Agents SDK.

This agent creates detailed, step-by-step implementation plans
from tool definitions and exploration reports.
"""

import logging
from typing import Optional

import agents
from agents import Agent, Runner

from app.config import get_settings
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

    def __init__(self):
        """Initialize the planner agent."""
        self.settings = get_settings()
        self._agent = None

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
            plan.requirement_description = tool_definition.docstring

            logger.info(f"Plan created with {len(plan.steps)} steps")

            return plan

        except Exception as e:
            logger.error(f"Error in planner agent: {e}")
            # Return minimal plan with error indication
            return ImplementationPlan(
                task_id=task_id,
                job_id=job_id,
                requirement_name=tool_definition.name,
                requirement_description=f"Error creating plan: {str(e)}",
                api_refs=[],
                steps=[],
                pseudo_code=f"# Error: {str(e)}",
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
            exploration_report: API findings

        Returns:
            Formatted message for the agent
        """
        # Format API functions
        apis_text = ""
        if exploration_report.apis:
            apis_text = "Available APIs:\n"
            for api in exploration_report.apis[:5]:  # Limit to top 5 most relevant
                apis_text += f"- {api.function_name}: {api.description}\n"
                if api.input_schema:
                    params = ", ".join([f"{p.name}: {p.type}" for p in api.input_schema])
                    apis_text += f"  Parameters: {params}\n"
                if api.output_schema:
                    apis_text += f"  Returns: {api.output_schema.type} - {api.output_schema.description}\n"
                apis_text += "\n"
        else:
            apis_text = "No specific APIs found. Use general library knowledge.\n"

        # Format code examples
        examples_text = ""
        if exploration_report.examples:
            examples_text = "Code Examples:\n"
            for i, example in enumerate(exploration_report.examples[:3], 1):  # Top 3 examples
                examples_text += f"Example {i}:\n{example.code}\n\n"

        # Format contracts
        contracts_text = "\n".join([f"- {c}" for c in tool_definition.contracts])

        return f"""Create a detailed implementation plan for the following tool:

**Function Name:** {tool_definition.name}

**Signature:** {tool_definition.signature}

**Docstring:**
{tool_definition.docstring}

**Contracts:**
{contracts_text}

**Example Usage:**
{tool_definition.example_call}

---

{apis_text}

{examples_text}

**Entry Points Found:**
{', '.join(exploration_report.entry_points[:5]) if exploration_report.entry_points else 'None'}

---

Create a comprehensive implementation plan following the structure in your instructions.
"""

    def _get_agent_instructions(self) -> str:
        """Get system instructions for the planner agent."""
        return """
You are an Implementation Planning Agent specialized in creating detailed, executable plans for chemistry computation tools.

## Your Mission:

Analyze the tool definition and available APIs to create a precise, step-by-step implementation plan that guides the code generation.

## Output Structure:

You MUST return an `ImplementationPlan` object with:

```python
ImplementationPlan(
    task_id="",  # Will be filled by system
    job_id="",  # Will be filled by system
    requirement_name="",  # Will be filled by system
    requirement_description="",  # Will be filled by system
    api_refs=["api.function.name1", "api.function.name2", ...],
    steps=[PlanStep(...), PlanStep(...), ...],
    pseudo_code="# Detailed pseudo-code outline",
    validation_rules=["Rule 1", "Rule 2", ...],
    expected_artifacts=["file1.py", "data structure description", ...]
)
```

## Step 1: Identify API References

List the specific API functions that will be used:
- Use fully qualified names (e.g., "rdkit.Chem.Descriptors.MolWt")
- Include 3-8 primary functions
- Order by importance (most critical first)

**Example:**
```python
api_refs=[
    "rdkit.Chem.MolFromSmiles",
    "rdkit.Chem.Descriptors.MolWt",
    "rdkit.Chem.MolToSmiles"
]
```

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
        error_handling="Raise ValueError if SMILES is empty or None"
    ),
    PlanStep(
        step_number=2,
        action="call_api",
        description="Convert SMILES to RDKit Mol object",
        apis_used=["rdkit.Chem.MolFromSmiles"],
        error_handling="Raise ValueError if SMILES parsing fails (returns None)"
    ),
    PlanStep(
        step_number=3,
        action="call_api",
        description="Calculate molecular weight using RDKit descriptor",
        apis_used=["rdkit.Chem.Descriptors.MolWt"],
        error_handling="Raise RuntimeError if descriptor calculation fails"
    ),
    PlanStep(
        step_number=4,
        action="validate",
        description="Ensure molecular weight is positive float",
        apis_used=[],
        error_handling="Raise RuntimeError if weight is non-positive"
    ),
    PlanStep(
        step_number=5,
        action="format_output",
        description="Return molecular weight as float in g/mol",
        apis_used=[],
        error_handling="No additional error handling needed"
    )
]
```

## Step 3: Write Pseudo-Code

Create a detailed pseudo-code outline showing the implementation structure:

**Include:**
- Function signature with type hints
- Step-by-step logic matching your plan steps
- Error handling (try-except blocks)
- Comments explaining key decisions
- Data flow between steps
- Units in comments

**Example:**
```python
pseudo_code = '''
def calculate_molecular_weight(smiles: str) -> float:
    \"\"\"Calculate molecular weight from SMILES.\"\"\"

    # Step 1: Parse input - validate SMILES
    if not smiles or not isinstance(smiles, str):
        raise ValueError("SMILES must be a non-empty string")

    # Step 2: Call API - convert SMILES to Mol
    try:
        mol = rdkit.Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Invalid SMILES: {smiles}")
    except Exception as e:
        raise ValueError(f"Failed to parse SMILES: {e}")

    # Step 3: Call API - calculate molecular weight
    try:
        mol_weight = rdkit.Chem.Descriptors.MolWt(mol)  # Returns g/mol
    except Exception as e:
        raise RuntimeError(f"Failed to calculate molecular weight: {e}")

    # Step 4: Validate - ensure positive weight
    if mol_weight <= 0:
        raise RuntimeError(f"Invalid molecular weight: {mol_weight}")

    # Step 5: Format output - return float
    return float(mol_weight)  # g/mol
'''
```

## Step 4: Define Validation Rules

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
    "Output: molecular weight must be positive float",
    "Output: molecular weight must be in range (0, 10000) g/mol for typical organic molecules",
    "Behavior: function must be deterministic (same input → same output)",
    "Error: raise ValueError for invalid SMILES",
    "Error: raise RuntimeError for calculation failures"
]
```

## Step 5: Specify Expected Artifacts

List what will be created:

**Typical Artifacts:**
- Main tool file: `{function_name}.py`
- Data structures returned (dict keys, list structure)
- Any intermediate files if applicable

**Example:**
```python
expected_artifacts=[
    "calculate_molecular_weight.py - main tool file",
    "Returns: float (molecular weight in g/mol)",
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
- Define exact error types to raise

**Think About Edge Cases:**
- What if input is None?
- What if API returns None?
- What if computation fails?
- What if result is unexpected?

**Consider Performance:**
- Note if computations are expensive
- Suggest reasonable timeouts
- Flag operations that might be slow

## Common Patterns:

**Pattern 1: SMILES → Property**
1. Parse input (validate SMILES)
2. Convert SMILES to Mol (rdkit.Chem.MolFromSmiles)
3. Calculate property (rdkit.Chem.Descriptors.XXX)
4. Validate result
5. Return value

**Pattern 2: Structure → Optimized Structure**
1. Parse input (validate XYZ/PDB)
2. Create structure object (ase.Atoms or similar)
3. Set up calculator (ase.calculators.XXX)
4. Run optimization (optimize.BFGS or similar)
5. Extract optimized structure
6. Format output (to XYZ string)
7. Return result

**Pattern 3: Structure → Quantum Properties**
1. Parse input (validate structure format)
2. Create quantum chemistry object (pyscf.gto.M)
3. Run SCF calculation
4. Extract properties (HOMO, LUMO, etc.)
5. Convert units if needed
6. Return dict with properties

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
