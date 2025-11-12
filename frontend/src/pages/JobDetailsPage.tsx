import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  Box,
  Chip,
  LinearProgress,
  Button,
  Grid,
  Card,
  CardContent,
  CardActionArea,
  Breadcrumbs,
  Link,
  Alert,
  Divider,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { ApiClient } from '../api';
import { JobResponse, JobStatus, TaskStatus } from '../types';
import { useJobStatusUpdates, useJobProgressUpdates, useTaskStatusUpdates } from '../contexts/WebSocketContext';

const statusColors: Record<JobStatus, 'default' | 'primary' | 'success' | 'error'> = {
  pending: 'default',
  processing: 'primary',
  completed: 'success',
  failed: 'error',
};

const taskStatusColors: Record<TaskStatus, 'default' | 'info' | 'warning' | 'primary' | 'success' | 'error'> = {
  pending: 'default',
  planning: 'info',
  searching: 'info',
  implementing: 'warning',
  executing: 'warning',
  completed: 'success',
  failed: 'error',
};

interface TaskCardData {
  taskId: string;
  toolName: string;
  status: TaskStatus;
  description: string;
}

export const JobDetailsPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<JobResponse | null>(null);
  const [tasks, setTasks] = useState<TaskCardData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadJobDetails = useCallback(async () => {
    if (!jobId) return;

    try {
      setLoading(true);
      setError(null);

      // Fetch job and tasks in parallel
      const [jobData, tasksData] = await Promise.all([
        ApiClient.getJob(jobId),
        ApiClient.getJobTasks(jobId),
      ]);

      setJob(jobData);

      // Map tasks to card data
      const taskCards: TaskCardData[] = tasksData.map((task: any) => ({
        taskId: task.task_id,
        toolName: task.task_id.split('_')[1],
        status: task.status as TaskStatus,
        description: task.tool_requirement?.description || 'No description',
      }));

      setTasks(taskCards);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load job details');
      console.error('Failed to load job:', err);
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    loadJobDetails();
  }, [loadJobDetails]);

  // WebSocket updates
  useJobStatusUpdates(jobId || null, (status: string, updatedAt: string, receivedJobId?: string) => {
    if (job && receivedJobId === jobId) {
      setJob({ ...job, status: status as JobStatus, updatedAt });
    }
  });

  useJobProgressUpdates(jobId || null, (progress: any, receivedJobId?: string) => {
    if (job && receivedJobId === jobId) {
      setJob({ ...job, progress, updatedAt: new Date().toISOString() });
    }
  });

  useTaskStatusUpdates(jobId || null, (taskId: string, status: string, updatedAt: string) => {
    setTasks(prev => prev.map(task =>
      task.taskId === taskId
        ? { ...task, status: status as TaskStatus }
        : task
    ));
  });

  const handleTaskClick = (taskId: string) => {
    navigate(`/jobs/${jobId}/tasks/${taskId}`);
  };

  const getProgressPercentage = () => {
    if (!job || job.progress.total === 0) return 0;
    return ((job.progress.completed + job.progress.failed) / job.progress.total) * 100;
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Typography>Loading job details...</Typography>
        <LinearProgress sx={{ mt: 2 }} />
      </Container>
    );
  }

  if (error || !job) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">
          {error || 'Job not found'}
        </Alert>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/')}
          sx={{ mt: 2 }}
        >
          Back to Dashboard
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link
          component="button"
          variant="body1"
          onClick={() => navigate('/')}
          sx={{ cursor: 'pointer', textDecoration: 'none' }}
        >
          Dashboard
        </Link>
        <Typography color="text.primary">{job.jobId}</Typography>
      </Breadcrumbs>

      {/* Back Button */}
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => navigate('/')}
        sx={{ mb: 2 }}
      >
        Back to Dashboard
      </Button>

      {/* Job Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h4" component="h1">
            {job.jobId}
          </Typography>
          <Chip
            label={job.status}
            color={statusColors[job.status]}
            size="medium"
          />
        </Box>

        {/* Task Description */}
        {job.taskDescription && (
          <>
            <Typography variant="h6" gutterBottom>
              Task Description
            </Typography>
            <Typography variant="body1" color="text.secondary" paragraph>
              {job.taskDescription}
            </Typography>
            <Divider sx={{ my: 2 }} />
          </>
        )}

        {/* Progress Section */}
        <Typography variant="h6" gutterBottom>
          Progress
        </Typography>
        <Box sx={{ mb: 2 }}>
          <Box display="flex" justifyContent="space-between" mb={1}>
            <Typography variant="body2" color="text.secondary">
              {job.progress.completed + job.progress.failed} of {job.progress.total} tools processed
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {Math.round(getProgressPercentage())}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={getProgressPercentage()}
            sx={{ height: 8, borderRadius: 4 }}
          />
        </Box>

        {/* Stats */}
        <Box display="flex" gap={2} flexWrap="wrap">
          <Box>
            <Typography variant="caption" color="text.secondary" display="block">
              Completed
            </Typography>
            <Typography variant="h6" color="success.main">
              {job.progress.completed}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary" display="block">
              Failed
            </Typography>
            <Typography variant="h6" color="error.main">
              {job.progress.failed}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary" display="block">
              In Progress
            </Typography>
            <Typography variant="h6" color="primary.main">
              {job.progress.inProgress}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary" display="block">
              Total
            </Typography>
            <Typography variant="h6">
              {job.progress.total}
            </Typography>
          </Box>
        </Box>

        {/* Timestamps */}
        <Box mt={2} display="flex" gap={3}>
          <Typography variant="caption" color="text.secondary">
            Created: {new Date(job.createdAt).toLocaleString()}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Updated: {new Date(job.updatedAt).toLocaleString()}
          </Typography>
        </Box>
      </Paper>

      {/* Tasks Section */}
      <Typography variant="h5" gutterBottom>
        Tools ({tasks.length})
      </Typography>

      {tasks.length === 0 ? (
        <Paper sx={{ p: 3 }}>
          <Typography variant="body1" color="text.secondary" align="center">
            No tasks found for this job.
          </Typography>
        </Paper>
      ) : (
        <Grid container spacing={2}>
          {tasks.map((task) => (
            <Grid item xs={12} key={task.taskId}>
              <Card>
                <CardActionArea onClick={() => handleTaskClick(task.taskId)}>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                      <Typography variant="h6" component="div" noWrap>
                        {task.toolName}
                      </Typography>
                      <Chip
                        label={task.status}
                        color={taskStatusColors[task.status]}
                        size="small"
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary" noWrap>
                      {task.description}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                      {task.taskId}
                    </Typography>
                  </CardContent>
                </CardActionArea>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Container>
  );
};
