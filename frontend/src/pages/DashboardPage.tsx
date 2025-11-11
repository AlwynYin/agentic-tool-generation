import React, { useState, useEffect, useCallback } from 'react';
import {
  Container,
  Grid,
  Card,
  CardContent,
  CardActionArea,
  Typography,
  Chip,
  LinearProgress,
  Box,
  Button,
  Stack,
  Alert,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import AddIcon from '@mui/icons-material/Add';
import { ApiClient } from '../api';
import { JobResponse, JobStatus } from '../types';
import { useJobStatusUpdates, useJobProgressUpdates } from '../contexts/WebSocketContext';
import { ManualJobDialog } from '../components/ManualJobDialog';
import { ExtractAndSubmitDialog } from '../components/ExtractAndSubmitDialog';

const statusColors: Record<JobStatus, 'default' | 'primary' | 'success' | 'error'> = {
  pending: 'default',
  processing: 'primary',
  completed: 'success',
  failed: 'error',
};

export const DashboardPage: React.FC = () => {
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [manualDialogOpen, setManualDialogOpen] = useState(false);
  const [extractDialogOpen, setExtractDialogOpen] = useState(false);
  const navigate = useNavigate();

  const loadJobs = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const jobList = await ApiClient.listJobs(100, 0);
      setJobs(jobList);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs');
      console.error('Failed to load jobs:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    // Refresh every 10 seconds to show live updates
    const interval = setInterval(loadJobs, 10000);
    return () => clearInterval(interval);
  }, [loadJobs]);

  const handleJobClick = (jobId: string) => {
    navigate(`/jobs/${jobId}`);
  };

  const truncateDescription = (desc: string | undefined) => {
    if (!desc) return null;
    return desc.length > 100 ? desc.substring(0, 100) + '...' : desc;
  };

  const getProgressPercentage = (job: JobResponse) => {
    if (job.progress.total === 0) return 0;
    return ((job.progress.completed + job.progress.failed) / job.progress.total) * 100;
  };

  if (loading && jobs.length === 0) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Typography>Loading jobs...</Typography>
        <LinearProgress sx={{ mt: 2 }} />
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Stack spacing={3}>
        {/* Header */}
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h4" component="h1">
            Job Dashboard
          </Typography>
          <Stack direction="row" spacing={2}>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setManualDialogOpen(true)}
            >
              Submit Job (Manual)
            </Button>
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() => setExtractDialogOpen(true)}
            >
              Extract and Submit
            </Button>
          </Stack>
        </Box>

        {/* Error Alert */}
        {error && (
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Jobs Grid */}
        {jobs.length === 0 ? (
          <Card>
            <CardContent>
              <Typography variant="body1" color="text.secondary" align="center">
                No jobs found. Create your first job using one of the buttons above.
              </Typography>
            </CardContent>
          </Card>
        ) : (
          <Grid container spacing={3}>
            {jobs.map((job) => (
              <Grid item xs={12} sm={6} md={4} key={job.jobId}>
                <Card>
                  <CardActionArea onClick={() => handleJobClick(job.jobId)}>
                    <CardContent>
                      {/* Job ID and Status */}
                      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                        <Typography variant="h6" component="div" noWrap>
                          {job.jobId}
                        </Typography>
                        <Chip
                          label={job.status}
                          color={statusColors[job.status]}
                          size="small"
                        />
                      </Box>

                      {/* Task Description */}
                      {job.taskDescription && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2, minHeight: 40 }}>
                          {truncateDescription(job.taskDescription)}
                        </Typography>
                      )}

                      {/* Progress */}
                      <Box sx={{ mb: 1 }}>
                        <Box display="flex" justifyContent="space-between" mb={0.5}>
                          <Typography variant="caption" color="text.secondary">
                            Progress
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {job.progress.completed + job.progress.failed}/{job.progress.total}
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={getProgressPercentage(job)}
                          sx={{ height: 6, borderRadius: 3 }}
                        />
                      </Box>

                      {/* Stats */}
                      <Box display="flex" gap={1} flexWrap="wrap">
                        {job.progress.completed > 0 && (
                          <Chip
                            label={`✓ ${job.progress.completed}`}
                            size="small"
                            color="success"
                            variant="outlined"
                          />
                        )}
                        {job.progress.failed > 0 && (
                          <Chip
                            label={`✗ ${job.progress.failed}`}
                            size="small"
                            color="error"
                            variant="outlined"
                          />
                        )}
                        {job.progress.inProgress > 0 && (
                          <Chip
                            label={`⟳ ${job.progress.inProgress}`}
                            size="small"
                            color="primary"
                            variant="outlined"
                          />
                        )}
                      </Box>

                      {/* Timestamp */}
                      <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                        {new Date(job.createdAt).toLocaleString()}
                      </Typography>
                    </CardContent>
                  </CardActionArea>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </Stack>

      {/* Submission Dialogs */}
      <ManualJobDialog
        open={manualDialogOpen}
        onClose={() => setManualDialogOpen(false)}
        onSuccess={(jobId) => {
          loadJobs();
          navigate(`/jobs/${jobId}`);
        }}
      />
      <ExtractAndSubmitDialog
        open={extractDialogOpen}
        onClose={() => setExtractDialogOpen(false)}
        onSuccess={(jobId) => {
          loadJobs();
          navigate(`/jobs/${jobId}`);
        }}
      />
    </Container>
  );
};
