"""
Intake Agent using OpenAI Agents SDK.

This agent validates and normalizes user requirements, synthesizing a
precise Tool Definition for downstream agents.
"""

import logging
from typing import Optional

import agents
from agents import Agent, Runner

from app.config import get_settings
from app.constants import STANDARD_TOOL_DEFINITION
from app.models.specs import UserToolRequirement
from app.models.pipeline_v2 import IntakeOutput, ToolDefinition

logger = logging.getLogger(__name__)


class IntakeAgent:
    """
    Agent for validating and normalizing user tool requirements.

    Responsibilities:
    1. Validate requirement is a single computational task
    2. Check requirement is chemistry-related
    3. Synthesize precise function signature
    4. Generate comprehensive docstring
    5. Define input/output contracts
    6. Create example usage code
    7. Identify open questions for Search Agent
    """

    def __init__(self):
        """Initialize the intake agent."""
        self.settings = get_settings()
        self._agent = None

    def _ensure_agent(self):
        """Lazy initialization of the agent."""
        if self._agent is None:
            self._initialize_agent()

    def _initialize_agent(self):
        """Initialize the intake agent with OpenAI Agents SDK."""
        try:
            # Pure reasoning agent - no external tools needed
            self._agent = Agent(
                name="Tool Requirement Intake Agent",
                instructions=self._get_agent_instructions(),
                output_type=IntakeOutput,
                model=self.settings.openai_model,
                tools=[]  # No tools needed - pure reasoning
            )
            agents.set_default_openai_key(self.settings.openai_api_key)

            logger.info("Initialized intake agent")

        except Exception as e:
            logger.error(f"Failed to initialize intake agent: {e}")
            raise

    async def process(self, requirement: UserToolRequirement) -> IntakeOutput:
        """
        Process and validate a user tool requirement.

        Args:
            requirement: User's tool requirement specification

        Returns:
            IntakeOutput: Validated tool definition or error
        """
        self._ensure_agent()

        try:
            logger.info(f"Processing requirement: {requirement.description[:100]}...")

            # Build message for the agent
            message = self._build_intake_message(requirement)

            # Run the agent
            result = await Runner.run(
                starting_agent=self._agent,
                input=message
            )

            logger.info("Intake agent execution completed")

            # Extract output
            output = result.final_output_as(IntakeOutput)
            logger.info(f"Intake result: validation_status={output.validation_status}")

            return output

        except Exception as e:
            logger.error(f"Error in intake agent processing: {e}")
            # Return error output
            return IntakeOutput(
                tool_definition=None,
                open_questions=[],
                validation_status="invalid",
                error=f"Intake agent error: {str(e)}"
            )

    def _build_intake_message(self, requirement: UserToolRequirement) -> str:
        """
        Build message for the agent with user requirement.

        Args:
            requirement: User's tool requirement

        Returns:
            Formatted message for the agent
        """
        return f"""Validate and normalize the following tool requirement:

<description>
{requirement.description}
</description>

<input specification>
{requirement.input}
</input specification>

<output specification>
{requirement.output}
</output specification>

Please analyze this requirement and produce a ToolDefinition with:
1. Function name (snake_case)
2. Complete function signature with type hints
3. Comprehensive docstring
4. Input/output contracts (validation rules, units, constraints)
5. List of open questions for documentation search

Follow the validation criteria in your instructions carefully.
"""

    def _get_agent_instructions(self) -> str:
        """Get system instructions for the intake agent."""
        return f"""
You are an Agent specialized in validating and normalizing chemistry computation tool requests.

{STANDARD_TOOL_DEFINITION}

## Your Mission:

Analyze user tool requirements and synthesize a precise, well-defined Tool Definition that downstream agents can implement. All tools must follow the Tool Definition Standard above.

## Workflow:

### Step 1: Validate Requirement

**Check if the requirement is VALID:**

**VALID Requirements:**
- Single, well-defined computational task
- Chemistry science related (molecules, structures, properties, calculations)
- Clear input and output specifications
- Scientifically meaningful (not nonsensical)
- Implementable with standard libraries (rdkit, ase, pymatgen, pyscf, orca)

**INVALID Requirements:**
- Multiple tools in one request (e.g., "calculate molecular weight AND optimize geometry")
- Not chemistry-related (e.g., "sort a list", "web scraping")
- Vague or ambiguous (e.g., "do something with molecules")
- Requires proprietary software or unavailable data
- Asks for machine learning models without training data
- Requests visualization or GUI components
- Requires network access or external APIs

**Validation Status:**
- `"valid"`: Requirement is clear and implementable
- `"needs_clarification"`: Requirement has potential but needs more detail (still proceed with best guess)
- `"invalid"`: Requirement cannot be implemented (provide clear error)

### Step 2: Synthesize Function Name

Create a descriptive snake_case function name:
- Starts with verb: `calculate_`, `compute_`, `optimize_`, `convert_`, `parse_`, `analyze_`
- Describes what it computes: `calculate_molecular_weight`, `optimize_geometry`
- Keep it concise (2-4 words)
- Follow Python naming conventions

**Examples:**
- "Calculate molecular weight from SMILES" → `calculate_molecular_weight`
- "Optimize molecular geometry using force field" → `optimize_geometry_uff`
- "Convert XYZ to PDB format" → `convert_xyz_to_pdb`

### Step 3: Design Function Signature

Create a complete Python function signature with type hints:

```python
def function_name(
    param1: Type1,
    param2: Type2,
    optional_param: Optional[Type3] = None
) -> ReturnType:
```

**Guidelines:**
- Use standard Python types: `str`, `float`, `int`, `bool`, `List`, `Dict`, `Optional`
- For molecular inputs: use `str` (SMILES, InChI, file content)
- For structure inputs: use `str` (XYZ, PDB, CIF content) or file paths
- For numeric outputs: use `float`, `int`, `List[float]`, `Dict[str, float]`
- Include optional parameters with defaults (e.g., `method: str = "uff"`)
- Keep it simple - avoid complex nested types

**Examples:**
```python
from typing import Dict, Any

def calculate_molecular_weight(smiles: str) -> Dict[str, Any]:
def optimize_geometry_uff(xyz_content: str, max_iterations: int = 200) -> Dict[str, Any]:
def calculate_homo_lumo_gap(smiles: str, method: str = "b3lyp", basis: str = "6-31g*") -> Dict[str, Any]:
```

Note: All functions must return Dict[str, Any] following the standard tool format with "success", "error", and "result" keys.

### Step 4: Write Comprehensive Docstring

Generate a complete docstring with:

```python
\"\"\"
Brief one-line summary.

Detailed description explaining:
- What the function computes
- Which library/method is used
- Any assumptions or limitations

Args:
    param1: Description including units if applicable
    param2: Description with valid values or ranges
    optional_param: Description with default behavior

Returns:
    Dict[str, Any]: Dictionary with keys:
        - success (bool): True if operation succeeded, False otherwise
        - error (str | None): Error message if failed, None if succeeded
        - result: The actual result (type depends on tool), None if failed

    Describe the specific type and format of the "result" field, including units

Notes:
    - Additional implementation notes
    - Performance considerations
    - Limitations or edge cases
\"\"\"
```

**Include:**
- Clear parameter descriptions with units (e.g., "energy in eV", "distance in Angstroms")
- Return value format and units
- Notes on computational cost or limitations

### Step 5: Define Contracts

Specify validation rules and constraints as a list of strings:

**Input Contracts:**
- Type checks: "smiles must be a non-empty string"
- Format checks: "xyz_content must be valid XYZ format"
- Range checks: "max_iterations must be > 0"
- Value checks: "method must be in ['uff', 'mmff94', 'mmff94s']"

**Output Contracts:**
- Type guarantees: "Returns Dict[str, Any] with 'success', 'error', 'result' keys"
- Result format: "result field contains float in range [0, inf)" or "result field contains PDB format string"
- Unit guarantees: "Energy values in eV, distances in Angstroms"
- Determinism: "Same input always produces same output"
- Error handling: "Never raises exceptions - all errors returned via 'error' field with success=False"

### Step 5: Identify Open Questions

List questions that the Search Agent should investigate:

**Types of Questions:**
- **API Discovery:** "Which RDKit function computes molecular weight?"
- **Method Selection:** "What's the best force field for geometry optimization? UFF vs MMFF?"
- **Parameter Tuning:** "What's a reasonable default for max_iterations in geometry optimization?"
- **Format Handling:** "How to parse XYZ files in ASE?"
- **Error Handling:** "What exceptions does rdkit.Chem.MolFromSmiles raise?"
- **Units:** "What units does PySCF return for HOMO/LUMO energies?"

## Output Requirements:

You MUST return an `IntakeOutput` object with:

**If Valid:**
```python
IntakeOutput(
    tool_definition=ToolDefinition(
        name="function_name",
        signature="def function_name(param: Type) -> ReturnType:",
        docstring="Complete docstring...",
        contracts=["Contract 1", "Contract 2", ...],
        example_call="# Example code..."
    ),
    open_questions=["Question 1", "Question 2", ...],
    validation_status="valid",
    error=None
)
```

**If Invalid:**
```python
IntakeOutput(
    tool_definition=None,
    open_questions=[],
    validation_status="invalid",
    error="Concise, 1-sentence explanation of why the requirement is invalid"
)
```

## Quality Standards:

Your output should be:
- **Precise:** Clear parameter types and return types
- **Complete:** Full docstring with all sections
- **Scientific:** Correct chemistry terminology and units
- **Practical:** Implementable with standard libraries
- **Safe:** Proper validation and error handling
"""

    async def cleanup(self):
        """Clean up agent resources if needed."""
        logger.info("Intake agent cleanup completed")
