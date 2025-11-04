"""
Shared constants for the tool generation pipeline.

This module contains standard definitions, prompts, and guidelines
used across all agents in the V2 pipeline.
"""

# Standard Tool Definition used across all agents
STANDARD_TOOL_DEFINITION = """## Tool Definition Standard

A Tool is a Python function that does one single computation task, with a well-typed and documented input and output schema.

**Requirements:**

1. **Single Purpose**: The tool should not be over-complicated with multiple capabilities. If there are multiple separate jobs, there should be multiple separate tools.

2. **Stateless**: The tool must be completely stateless. This means:
   - No global state usage
   - No modification of outer scope variables
   - Output ONLY via Python's `return` statement
   - No modification of input parameters

3. **Error Handling**: The tool should not raise errors during execution. Instead, it should reflect errors in the return value through the standard return format.

4. **Return Format**: The tool must always return a dictionary with keys including but not limited to:
   - `"success"`: bool indicating if the operation succeeded
   - `"error"`: str or None containing error message if success is False
   - `"result"`: The actual result data (type depends on tool, None if error)

**Example:**
```python
from typing import Dict, Any
from rdkit import Chem
from rdkit.Chem import Descriptors

def calculate_molecular_weight(smiles: str) -> Dict[str, Any]:
    \"\"\"
    Calculate molecular weight from SMILES string.

    Args:
        smiles: SMILES string representation of molecule

    Returns:
        Dictionary with keys:
        - success: bool indicating if calculation succeeded
        - error: str error message if failed, None if succeeded
        - result: float molecular weight in g/mol if succeeded, None if failed
    \"\"\"
    try:
        # Input validation
        if not smiles:
            return {
                "success": False,
                "error": "SMILES string cannot be empty",
                "result": None
            }

        # Parse SMILES
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {
                "success": False,
                "error": f"Invalid SMILES string: {smiles}",
                "result": None
            }

        # Calculate molecular weight
        weight = Descriptors.MolWt(mol)

        # Validate result
        if weight <= 0:
            return {
                "success": False,
                "error": f"Invalid molecular weight calculated: {weight}",
                "result": None
            }

        return {
            "success": True,
            "error": None,
            "result": weight
        }

    except Exception as e:
        # Catch any unexpected errors
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "result": None
        }
```

**Key Points:**
- Never use `raise` statements - return error via dict
- Always validate inputs before processing
- Always validate outputs before returning
- Handle all exceptions and convert to error dict
- Keep functions pure and deterministic
"""
