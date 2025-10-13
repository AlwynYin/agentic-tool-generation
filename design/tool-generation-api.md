# Tool Generation Service API Specification

## Overview
This document defines the API specification for the Tool Generation Service.

Users generate code by passing tool requirements in natural language. A `job` is created, which generates tools asynchronously using an OpenAI agent-based workflow. Users can monitor job progress by polling the job status endpoint.

The service uses a session-based architecture where:
- Each job creates a corresponding session that tracks the multi-agent workflow
- Tools are stored in a MongoDB `tools` collection with complete code, metadata, and schemas
- Tool IDs are stored as ObjectIds in MongoDB and returned as strings via the API
- The workflow progresses through stages: pending → planning → searching → implementing → executing → completed/failed

## Service Configuration

- **Base URL**: Configurable via `HOST` and `PORT` environment variables (default: `http://localhost:8000`)
- **Database**: MongoDB connection via `MONGODB_URL` and `MONGODB_DB_NAME` (default: `mongodb://localhost:27017` and `agent_browser`)
- **API Version**: v1 (`/api/v1/`)

## Service Endpoints


### Check Health

#### `GET /api/v1/health`
Health check endpoint.

**Response:**
```typescript
interface HealthResponse {
    status: 'healthy' | 'unhealthy'
    timestamp: string
    version: string
    database: 'connected' | 'disconnected'
}
```

### Job Management

#### `POST /api/v1/jobs`
Create a new tool generation job.

**Request Body:**
```typescript
interface ToolGenerationRequest {
    toolRequirements: UserToolRequirement[]
    metadata?: RequestMetadata
}
```

**Response:**
```typescript
interface JobResponse {
    jobId: string
    status: JobStatus
    createdAt: string
    updatedAt: string
    progress: JobProgress
}
```

#### `GET /api/v1/jobs/{jobId}`
Get job status and metadata.

**Response:** `JobResponse`

### Session Management (Internal)

The following session endpoints are available for advanced use cases but are typically managed internally by the job workflow:

#### `GET /api/v1/sessions/{session_id}`
Get session details by session ID.

#### `GET /api/v1/sessions/{session_id}/tools`
Get all tools generated for a specific session.

#### `GET /api/v1/sessions/{session_id}/status`
Get detailed session status including workflow progress.

#### `GET /api/v1/sessions/user/{user_id}`
Get all sessions for a specific user.

#### `GET /api/v1/sessions/status/{status_value}`
Get all sessions with a specific status (e.g., "completed", "failed").


## Data Models

### Input Objects

#### `ToolRequirement`
```typescript
interface UserToolRequirement {
    description: string           // Natural language description of the tool
    input: string                 // Natural language description of the input
    output: string                // Natural language description of the output
}
```

#### `RequestMetadata`
```typescript
interface RequestMetadata {
    sessionId?: string            // Optional session tracking
    clientId?: string             // Client identifier
}
```

### Output Objects

#### `JobResponse`
```typescript
interface JobResponse {
    jobId: string
    status: JobStatus
    createdAt: string             // ISO timestamp
    updatedAt: string             // ISO timestamp  
    progress: JobProgress
    toolFiles?: ToolFile[]        // Generated tool files (only when completed)
    failures?: ToolGenerationFailure[]  // Failed tool generations (only when completed)
    summary?: GenerationSummary   // Job summary (only when completed)
}

type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

interface JobProgress {
    total: number                 // Total tools to generate
    completed: number             // Successfully generated
    failed: number                // Failed generations
    inProgress: number            // Currently being generated
    currentTool?: string          // Name of tool currently being generated
}

interface ToolFile {
    toolId: string                // Unique tool identifier (MongoDB ObjectId stored as string)
    fileName: string              // e.g., "calculate_molecular_weight.py"
    filePath: string              // Virtual file path (for compatibility)
    description: string           // Tool description from requirement
    code: string                  // Generated Python code content
    endpoint?: string             // Reserved for future use (currently null)
    registered: boolean           // Tool status (draft/registered/deprecated/failed)
    createdAt: string             // ISO timestamp
}
```


#### `ToolGenerationFailure`
```typescript
interface ToolGenerationFailure {
    toolRequirement: ToolRequirement
    error: string
}
```

#### `GenerationSummary`
```typescript
interface GenerationSummary {
    totalRequested: number
    successful: number
    failed: number
}
```

### Error Objects

#### `ErrorResponse`
```typescript
interface ErrorResponse {
    error: string
    code: ErrorCode
    details?: any
    timestamp: string
    jobId?: string
    requestId?: string            // For support/debugging
}

type ErrorCode = 
    | 'INVALID_REQUEST'           // Malformed request
    | 'INVALID_TOOL_REQUIREMENT'  // Tool requirement validation failed
    | 'INSUFFICIENT_API_SPECS'    // Not enough API documentation
    | 'GENERATION_TIMEOUT'        // Tool generation timed out
    | 'AI_SERVICE_ERROR'          // OpenAI/AI service error
    | 'AI_SERVICE_RATE_LIMITED'   // Rate limited by AI service
    | 'JOB_NOT_FOUND'            // Job ID doesn't exist
    | 'JOB_CANCELLED'            // Job was cancelled
    | 'JOB_ALREADY_COMPLETED'    // Job already finished
    | 'RATE_LIMIT_EXCEEDED'      // Too many requests
    | 'SERVICE_UNAVAILABLE'      // Service temporarily unavailable
    | 'INTERNAL_ERROR'           // Unexpected server error
```

## Usage Examples

### Tool Generation

```bash
# Create job
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "toolRequirements": [
      {
        "description": "I need a tool that calculates the molecular weight of a chemical compound. Please use RDKit if available.",
        "input": "SMILES string of the molecule",
        "output": "molecular weight"
      }
    ],
    "metadata": {
      "sessionId": "session_123",
      "clientId": "web-app"
    }
  }'

# Response
{
  "jobId": "job_abc123",
  "status": "pending",
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T10:30:00Z",
  "progress": {
    "total": 1,
    "completed": 0,
    "failed": 0,
    "inProgress": 0,
    "currentTool": null
  }
}
```

### Check Job Status

```bash
curl http://localhost:8000/api/v1/jobs/job_abc123

# Response
{
  "jobId": "job_abc123", 
  "status": "running",
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T10:30:45Z",
  "progress": {
    "total": 1,
    "completed": 0,
    "failed": 0,
    "inProgress": 1,
    "currentTool": "calculate_molecular_weight"
  }
}
```

### Retrieve Generated Tools

```bash
curl http://localhost:8000/api/v1/jobs/job_abc123

# Response (when completed)
{
  "jobId": "job_abc123",
  "status": "completed",
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T10:31:30Z",
  "progress": {
    "total": 1,
    "completed": 1,
    "failed": 0,
    "inProgress": 0,
    "currentTool": null
  },
  "toolFiles": [
    {
      "toolId": "tool_xyz789",
      "fileName": "calculate_molecular_weight.py",
      "filePath": "tools/calculate_molecular_weight.py",
      "description": "Calculate molecular weight from SMILES string using RDKit",
      "code": "from typing import Dict\n\ndef calculate_molecular_weight(smiles: str) -> Dict[str, float]:\n    \"\"\"Calculate molecular weight of a chemical compound from SMILES string.\"\"\"\n    from rdkit import Chem\n    from rdkit.Chem import Descriptors\n    \n    try:\n        mol = Chem.MolFromSmiles(smiles)\n        if mol is None:\n            raise ValueError(f\"Invalid SMILES string: {smiles}\")\n        \n        molecular_weight = Descriptors.MolWt(mol)\n        return {'molecular_weight': molecular_weight}\n    except Exception as e:\n        raise ValueError(f\"Error calculating molecular weight: {str(e)}\")",
      "endpoint": null,
      "registered": true,
      "createdAt": "2024-01-15T10:31:30Z"
    }
  ],
  "failures": [],
  "summary": {
    "totalRequested": 1,
    "successful": 1,
    "failed": 0
  }
}
```

### Python Client Example
see `tool_generation_backend/tests/test_v1_pipeline.py`

## Tool Storage Architecture

### MongoDB Collections

Tools are stored in a MongoDB database with the following collections:

1. **`sessions` collection**: Tracks tool generation workflows
   - `job_id`: Associated job identifier
   - `user_id`: User who created the job
   - `status`: Current workflow status (pending/planning/searching/implementing/executing/completed/failed)
   - `tool_ids`: Array of ObjectIds referencing tools in the `tools` collection
   - `tool_requirements`: Original user requirements
   - `created_at`, `updated_at`: Timestamps

2. **`tools` collection**: Stores generated tools with full metadata
   - `_id`: MongoDB ObjectId (returned as string in API)
   - `name`: Tool name (unique identifier)
   - `file_name`: Python file name (e.g., "calculate_molecular_weight.py")
   - `file_path`: Virtual file path (for compatibility)
   - `description`: Tool description
   - `code`: Complete Python code implementation
   - `input_schema`: Input parameter specifications
   - `output_schema`: Output type specification
   - `dependencies`: Required Python packages
   - `test_cases`: Tool test cases
   - `status`: Tool status (draft/registered/deprecated/failed)
   - `session_id`: Session that generated this tool
   - `created_at`, `updated_at`: Timestamps

3. **`agent_sessions` collection**: OpenAI Agents SDK conversation history
   - Stores agent conversation state and memory

### Database Configuration

The database name is configurable via the `MONGODB_DB_NAME` environment variable (default: `agent_browser`).

### Tool ID Storage

Tool IDs are stored as MongoDB ObjectIds in the database for efficiency (12 bytes vs ~24 bytes for strings), but are converted to strings at the API boundary for compatibility.

### Python Code Structure

Generated tools follow this structure:

```python
"""
Generated Tool: Calculate Molecular Weight
Description: Calculate molecular weight from SMILES string using RDKit
Dependencies: rdkit
"""

from typing import Dict

def calculate_molecular_weight(smiles: str) -> Dict[str, float]:
    """
    Calculate molecular weight of a chemical compound from SMILES string.

    Args:
        smiles: SMILES string representation of the molecule

    Returns:
        Dictionary containing molecular weight
    """
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Invalid SMILES string: {smiles}")

        molecular_weight = Descriptors.MolWt(mol)
        return {'molecular_weight': molecular_weight}
    except Exception as e:
        raise ValueError(f"Error calculating molecular weight: {str(e)}")
```

