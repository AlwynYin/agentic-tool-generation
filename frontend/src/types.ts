// API Types matching backend models

export interface UserToolRequirement {
  description: string;
  input: string;
  output: string;
}

export interface ToolGenerationRequest {
  toolRequirements: UserToolRequirement[];
  metadata?: {
    sessionId?: string;
    clientId?: string;
  };
}

export interface JobProgress {
  total: number;
  completed: number;
  failed: number;
  inProgress: number;
  currentTool?: string;
}

export interface ToolFile {
  toolId: string;
  fileName: string;
  filePath: string;
  description: string;
  code: string;
  endpoint: string | null;
  registered: boolean;
  createdAt: string;
}

export interface ToolGenerationFailure {
  toolRequirement: UserToolRequirement;
  error: string;
  error_type: string;
}

export interface GenerationSummary {
  totalRequested: number;
  successful: number;
  failed: number;
}

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type TaskStatus = 'pending' | 'planning' | 'searching' | 'implementing' | 'executing' | 'completed' | 'failed';

export interface JobResponse {
  jobId: string;
  status: JobStatus;
  createdAt: string;
  updatedAt: string;
  taskDescription?: string;
  toolRequirements?: UserToolRequirement[];
  progress: JobProgress;
  toolFiles?: ToolFile[];
  failures?: ToolGenerationFailure[];
  summary?: GenerationSummary;
}

export interface TaskResponse {
  task_id: string;
  job_id: string;
  status: TaskStatus;
  tool_requirement: UserToolRequirement;
  created_at: string;
  updated_at?: string;
}

export interface TaskFilesResponse {
  taskId: string;
  status: TaskStatus;
  toolCode?: string;
  testCode?: string;
  toolFileName?: string;
  testFileName?: string;
  error?: string;
}

// WebSocket message types
export interface WSMessage {
  type: string;
  data?: any;
}

export interface WSJobStatusChanged extends WSMessage {
  type: 'job-status-changed';
  data: {
    jobId: string;
    status: JobStatus;
    updatedAt: string;
  };
}

export interface WSJobProgressUpdated extends WSMessage {
  type: 'job-progress-updated';
  data: {
    jobId: string;
    progress: JobProgress;
    updatedAt: string;
  };
}

export interface WSTaskStatusChanged extends WSMessage {
  type: 'task-status-changed';
  data: {
    taskId: string;
    jobId: string;
    status: TaskStatus;
    updatedAt: string;
  };
}
