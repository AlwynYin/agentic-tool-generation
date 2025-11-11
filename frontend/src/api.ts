// API client for backend communication

import { ToolGenerationRequest, JobResponse, TaskResponse, TaskFilesResponse } from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export class ApiClient {
  /**
   * List all jobs with pagination
   */
  static async listJobs(limit: number = 100, skip: number = 0): Promise<JobResponse[]> {
    const response = await fetch(`${API_BASE_URL}/jobs?limit=${limit}&skip=${skip}`);

    if (!response.ok) {
      throw new Error(`Failed to list jobs: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Create a new job with tool requirements
   */
  static async createJob(request: ToolGenerationRequest): Promise<JobResponse> {
    const response = await fetch(`${API_BASE_URL}/jobs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to create job: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get job status by job ID
   */
  static async getJob(jobId: string): Promise<JobResponse> {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`);

    if (!response.ok) {
      throw new Error(`Failed to get job: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get all tasks for a job
   */
  static async getJobTasks(jobId: string): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/tasks`);

    if (!response.ok) {
      throw new Error(`Failed to get job tasks: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Extract requirements from natural language and create job
   */
  static async extractAndSubmit(taskDescription: string, clientId: string = 'web-ui'): Promise<{
    job_id: string;
    requirements_count: number;
    status: string;
  }> {
    const response = await fetch(`${API_BASE_URL}/extract-and-submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        task_description: taskDescription,
        client_id: clientId,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to extract and submit: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get task details by task ID
   */
  static async getTask(taskId: string): Promise<TaskResponse> {
    const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`);

    if (!response.ok) {
      throw new Error(`Failed to get task: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get task files (tool code and test code)
   */
  static async getTaskFiles(taskId: string): Promise<TaskFilesResponse> {
    const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/files`);

    if (!response.ok) {
      throw new Error(`Failed to get task files: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Create WebSocket connection for real-time updates
   */
  static createWebSocket(sessionId: string): WebSocket {
    return new WebSocket(`${WS_BASE_URL}/ws/${sessionId}`);
  }
}
