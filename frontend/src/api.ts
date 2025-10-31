// API client for backend communication

import { ToolGenerationRequest, JobResponse } from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export class ApiClient {
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
   * Create WebSocket connection for real-time updates
   */
  static createWebSocket(sessionId: string): WebSocket {
    return new WebSocket(`${WS_BASE_URL}/ws/${sessionId}`);
  }
}
