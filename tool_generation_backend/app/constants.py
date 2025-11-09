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
   - `"metadata"`: metadata about the call

**Key Points:**
- Never use `raise` statements - return error via dict
- Always validate inputs before processing
- Always validate outputs before returning
- Handle all exceptions and convert to error dict
- Keep functions pure and deterministic
"""
