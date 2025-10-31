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

export interface JobResponse {
  jobId: string;
  status: JobStatus;
  createdAt: string;
  updatedAt: string;
  progress: JobProgress;
  toolFiles?: ToolFile[];
  failures?: ToolGenerationFailure[];
  summary?: GenerationSummary;
}
