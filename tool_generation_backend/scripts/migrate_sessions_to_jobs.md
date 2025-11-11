# Database Migration: Sessions → Jobs Architecture

## Overview
This migration transforms the database from a bulk processing model (1 session → N tools) to a parallel processing model (1 job → N sessions → N tools).

## Migration Steps

### 1. Backup Current Database
```bash
# Backup the entire database before migration
mongodump --uri="<MONGODB_URI>" --out=./backup_pre_migration_$(date +%Y%m%d_%H%M%S)
```

### 2. Rename Collections

#### 2.1 Rename `sessions` → `jobs`
```javascript
db.sessions.renameCollection("jobs")
```

#### 2.2 Create New `sessions` Collection
```javascript
db.createCollection("sessions")
```

### 3. Update Job Documents

#### 3.1 Add New Fields to Jobs Collection
```javascript
db.jobs.updateMany(
  {},
  {
    $set: {
      // Rename job_id to preserve short identifier
      // (Already exists as job_id field)

      // Add new fields
      session_ids: [],  // Will track child sessions
      tools_completed: 0,
      tools_failed: 0,
      tools_in_progress: 0,

      // Update status values to match new JobStatus enum
      // PENDING, PROCESSING, COMPLETED, FAILED
    },
    $rename: {
      // Keep tool_requirements as is
      // Keep job_id as is
      // Keep user_id as is
    }
  }
)
```

#### 3.2 Update Status Values
```javascript
// Map old SessionStatus values to new JobStatus values
db.jobs.updateMany(
  { status: { $in: ["pending", "planning", "searching", "implementing", "executing"] } },
  { $set: { status: "processing" } }
)

// Keep "completed" and "failed" as is
```

#### 3.3 Calculate Initial Counters
```javascript
// For each job, set counters based on existing tool_ids and tool_failure_ids
db.jobs.find().forEach(function(job) {
  db.jobs.updateOne(
    { _id: job._id },
    {
      $set: {
        tools_completed: job.tool_ids ? job.tool_ids.length : 0,
        tools_failed: job.tool_failure_ids ? job.tool_failure_ids.length : 0,
        tools_in_progress: 0
      }
    }
  )
})
```

#### 3.4 Remove Old Array Fields (Optional - Keep for Backwards Compatibility)
```javascript
// OPTIONAL: Remove old tool_ids and tool_failure_ids arrays
// Only do this after verifying all tools are tracked via sessions
db.jobs.updateMany(
  {},
  {
    $unset: {
      tool_ids: "",
      tool_failure_ids: ""
    }
  }
)
```

### 4. Create Indexes

#### 4.1 Jobs Collection Indexes
```javascript
// Unique index on job_id (short identifier)
db.jobs.createIndex({ "job_id": 1 }, { unique: true })

// Index for user queries
db.jobs.createIndex({ "user_id": 1 })

// Index for status queries
db.jobs.createIndex({ "status": 1 })

// Compound index for user + status
db.jobs.createIndex({ "user_id": 1, "status": 1 })

// Index for sorting by created_at
db.jobs.createIndex({ "created_at": 1 })
```

#### 4.2 Sessions Collection Indexes
```javascript
// Unique index on session_id (unique identifier)
db.sessions.createIndex({ "session_id": 1 }, { unique: true })

// Index for job_id queries (find all sessions for a job)
db.sessions.createIndex({ "job_id": 1 })

// Index for user queries
db.sessions.createIndex({ "user_id": 1 })

// Index for status queries
db.sessions.createIndex({ "status": 1 })

// Compound index for user + status
db.sessions.createIndex({ "user_id": 1, "status": 1 })

// Index for sorting by created_at
db.sessions.createIndex({ "created_at": 1 })
```

### 5. Migration Script Schema

#### New Job Document Structure
```json
{
  "_id": ObjectId,
  "job_id": "job_abc123",
  "user_id": "user_xyz",
  "operation_type": "generate",
  "tool_requirements": [
    {
      "description": "Calculate molecular weight",
      "input": "SMILES string",
      "output": "Molecular weight in g/mol"
    }
  ],
  "status": "processing",
  "session_ids": ["session_xyz1", "session_xyz2"],
  "tools_completed": 0,
  "tools_failed": 0,
  "tools_in_progress": 2,
  "error_message": null,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

#### New Session Document Structure
```json
{
  "_id": ObjectId,
  "session_id": "session_xyz1",
  "job_id": "job_abc123",
  "user_id": "user_xyz",
  "tool_requirement": {
    "description": "Calculate molecular weight",
    "input": "SMILES string",
    "output": "Molecular weight in g/mol"
  },
  "status": "implementing",
  "tool_id": ObjectId("..."),
  "tool_failure_id": null,
  "error_message": null,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### 6. Verification Queries

#### 6.1 Verify Jobs Collection
```javascript
// Check job counts
db.jobs.countDocuments()

// Check job_id uniqueness
db.jobs.aggregate([
  { $group: { _id: "$job_id", count: { $sum: 1 } } },
  { $match: { count: { $gt: 1 } } }
])

// Verify counters match reality
db.jobs.find().forEach(function(job) {
  print("Job:", job.job_id);
  print("  tools_completed:", job.tools_completed);
  print("  tools_failed:", job.tools_failed);
  print("  Total expected:", job.tool_requirements.length);
})
```

#### 6.2 Verify Sessions Collection
```javascript
// Should be empty after migration (new sessions will be created on first run)
db.sessions.countDocuments()

// Verify indexes
db.sessions.getIndexes()
```

### 7. Rollback Procedure

If migration fails:

```javascript
// 1. Drop new sessions collection
db.sessions.drop()

// 2. Rename jobs back to sessions
db.jobs.renameCollection("sessions")

// 3. Restore from backup
mongorestore --uri="<MONGODB_URI>" --dir=./backup_pre_migration_<timestamp>
```

## Post-Migration Checks

1. ✅ Verify `jobs` collection has all expected documents
2. ✅ Verify all job_ids are unique
3. ✅ Verify counters (tools_completed, tools_failed) match tool_ids/tool_failure_ids counts
4. ✅ Verify `sessions` collection is empty (new sessions created on first request)
5. ✅ Verify all indexes are created
6. ✅ Test creating a new job via API
7. ✅ Test querying job status via API
8. ✅ Monitor logs for any errors during first requests

## Notes

- The migration preserves historical job data in the `jobs` collection
- New sessions will be created when the first requests come in after deployment
- Tools and tool_failures collections remain unchanged
- The `job_id` field in the `jobs` collection remains the same (e.g., `job_abc123`)
- MongoDB _id fields are preserved during renameCollection operation
