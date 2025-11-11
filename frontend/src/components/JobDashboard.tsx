import { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  LinearProgress,
  Grid,
  Paper,
  Alert,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import SyncIcon from '@mui/icons-material/Sync';
import { JobResponse, JobStatus } from '../types';
import { ApiClient } from '../api';

interface JobDashboardProps {
  jobId: string;
  onJobUpdate?: (job: JobResponse) => void;
}

const statusConfig: Record<JobStatus, { label: string; color: any; icon: JSX.Element }> = {
  pending: {
    label: 'Pending',
    color: 'default',
    icon: <HourglassEmptyIcon />,
  },
  processing: {
    label: 'Processing',
    color: 'primary',
    icon: <SyncIcon />,
  },
  completed: {
    label: 'Completed',
    color: 'success',
    icon: <CheckCircleIcon />,
  },
  failed: {
    label: 'Failed',
    color: 'error',
    icon: <ErrorIcon />,
  },
};

export function JobDashboard({ jobId, onJobUpdate }: JobDashboardProps) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    let pollInterval: NodeJS.Timeout;

    const fetchJob = async () => {
      try {
        const jobData = await ApiClient.getJob(jobId);
        if (mounted) {
          setJob(jobData);
          setError(null);
          onJobUpdate?.(jobData);

          // Stop polling if job is completed or failed
          if (jobData.status === 'completed' || jobData.status === 'failed') {
            clearInterval(pollInterval);
          }
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to fetch job');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    // Initial fetch
    fetchJob();

    // Poll every 5 seconds
    pollInterval = setInterval(fetchJob, 5000);

    return () => {
      mounted = false;
      clearInterval(pollInterval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]); // Only depend on jobId, not onJobUpdate

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography>Loading job...</Typography>
          <LinearProgress sx={{ mt: 2 }} />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert severity="error">
        {error}
      </Alert>
    );
  }

  if (!job) {
    return null;
  }

  const config = statusConfig[job.status];
  const progressPercent = job.progress.total > 0
    ? ((job.progress.completed + job.progress.failed) / job.progress.total) * 100
    : 0;

  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
          <Typography variant="h5">
            Job {jobId}
          </Typography>
          <Chip
            label={config.label}
            color={config.color}
            icon={config.icon}
          />
        </Box>

        <Typography variant="body2" color="text.secondary" gutterBottom>
          Created: {new Date(job.createdAt).toLocaleString()}
        </Typography>

        <Box mt={3} mb={2}>
          <Typography variant="body2" gutterBottom>
            Progress: {job.progress.completed + job.progress.failed} / {job.progress.total} tools
          </Typography>
          <LinearProgress
            variant="determinate"
            value={progressPercent}
            sx={{ height: 8, borderRadius: 4 }}
          />
        </Box>

        <Grid container spacing={2} mt={1}>
          <Grid item xs={3}>
            <Paper elevation={2} sx={{ p: 2, textAlign: 'center' }}>
              <Typography variant="h4" color="primary">
                {job.progress.total}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Total
              </Typography>
            </Paper>
          </Grid>
          <Grid item xs={3}>
            <Paper elevation={2} sx={{ p: 2, textAlign: 'center', bgcolor: 'success.light' }}>
              <Typography variant="h4" color="success.contrastText">
                {job.progress.completed}
              </Typography>
              <Typography variant="caption" color="success.contrastText">
                Completed
              </Typography>
            </Paper>
          </Grid>
          <Grid item xs={3}>
            <Paper elevation={2} sx={{ p: 2, textAlign: 'center', bgcolor: 'error.light' }}>
              <Typography variant="h4" color="error.contrastText">
                {job.progress.failed}
              </Typography>
              <Typography variant="caption" color="error.contrastText">
                Failed
              </Typography>
            </Paper>
          </Grid>
          <Grid item xs={3}>
            <Paper elevation={2} sx={{ p: 2, textAlign: 'center', bgcolor: 'info.light' }}>
              <Typography variant="h4" color="info.contrastText">
                {job.progress.inProgress}
              </Typography>
              <Typography variant="caption" color="info.contrastText">
                In Progress
              </Typography>
            </Paper>
          </Grid>
        </Grid>

        {job.progress.currentTool && (
          <Box mt={2}>
            <Typography variant="body2" color="text.secondary">
              Current: {job.progress.currentTool}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
