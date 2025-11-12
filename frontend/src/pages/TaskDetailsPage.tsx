import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  Box,
  Chip,
  Button,
  Breadcrumbs,
  Link,
  Alert,
  Tabs,
  Tab,
  LinearProgress,
  Divider,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CodeIcon from '@mui/icons-material/Code';
import BugReportIcon from '@mui/icons-material/BugReport';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ApiClient } from '../api';
import { TaskResponse, TaskFilesResponse, TaskStatus } from '../types';
import { useTaskStatusUpdates } from '../contexts/WebSocketContext';

const taskStatusColors: Record<TaskStatus, 'default' | 'info' | 'warning' | 'primary' | 'success' | 'error'> = {
  pending: 'default',
  planning: 'info',
  searching: 'info',
  implementing: 'warning',
  executing: 'warning',
  completed: 'success',
  failed: 'error',
};

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`code-tabpanel-${index}`}
      aria-labelledby={`code-tab-${index}`}
      {...other}
    >
      {value === index && <Box>{children}</Box>}
    </div>
  );
}

export const TaskDetailsPage: React.FC = () => {
  const { jobId, taskId } = useParams<{ jobId: string; taskId: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<TaskResponse | null>(null);
  const [files, setFiles] = useState<TaskFilesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);

  const loadTaskDetails = useCallback(async () => {
    if (!taskId) return;

    try {
      setLoading(true);
      setError(null);

      // Load task details and files in parallel
      const [taskData, filesData] = await Promise.all([
        ApiClient.getTask(taskId),
        ApiClient.getTaskFiles(taskId),
      ]);

      setTask(taskData);
      setFiles(filesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load task details');
      console.error('Failed to load task:', err);
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    loadTaskDetails();
  }, [loadTaskDetails]);

  // WebSocket updates
  useTaskStatusUpdates(jobId || null, (updatedTaskId: string, status: string) => {
    if (updatedTaskId === taskId && task) {
      setTask({ ...task, status: status as TaskStatus });
    }
  });

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Typography>Loading task details...</Typography>
        <LinearProgress sx={{ mt: 2 }} />
      </Container>
    );
  }

  if (error || !task) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">
          {error || 'Task not found'}
        </Alert>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(`/jobs/${jobId}`)}
          sx={{ mt: 2 }}
        >
          Back to Job
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
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
        <Link
          component="button"
          variant="body1"
          onClick={() => navigate(`/jobs/${jobId}`)}
          sx={{ cursor: 'pointer', textDecoration: 'none' }}
        >
          {jobId}
        </Link>
        <Typography color="text.primary">{task.task_id}</Typography>
      </Breadcrumbs>

      {/* Back Button */}
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => navigate(`/jobs/${jobId}`)}
        sx={{ mb: 2 }}
      >
        Back to Job
      </Button>

      {/* Task Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h4" component="h1">
            {task.task_id}
          </Typography>
          <Chip
            label={task.status}
            color={taskStatusColors[task.status]}
            size="medium"
          />
        </Box>

        {/* Tool Requirement Details */}
        <Typography variant="h6" gutterBottom>
          Tool Requirement
        </Typography>
        <Box mb={2}>
          <Typography variant="body1" paragraph>
            <strong>Description:</strong> {task.tool_requirement.description}
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            <strong>Input:</strong> {task.tool_requirement.input}
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            <strong>Output:</strong> {task.tool_requirement.output}
          </Typography>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Timestamps */}
        <Box display="flex" gap={3}>
          <Typography variant="caption" color="text.secondary">
            Created: {new Date(task.created_at).toLocaleString()}
          </Typography>
          {task.updated_at && (
            <Typography variant="caption" color="text.secondary">
              Updated: {new Date(task.updated_at).toLocaleString()}
            </Typography>
          )}
        </Box>
      </Paper>

      {/* Error Alert */}
      {(task.status === 'failed' || files?.error) && (
        <Alert severity="error" sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            <strong>Task Failed</strong>
          </Typography>
          {files?.error && (
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {files.error}
            </Typography>
          )}
          {!files?.error && (
            <Typography variant="body2">
              This task failed. See logs for more details.
            </Typography>
          )}
        </Alert>
      )}

      {/* Code Section */}
      <Paper sx={{ mb: 3 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange} aria-label="code tabs">
            <Tab
              icon={<CodeIcon />}
              iconPosition="start"
              label={"Tool Code"}
              disabled={!files?.toolCode}
            />
            <Tab
              icon={<BugReportIcon />}
              iconPosition="start"
              label={"Test Code"}
              disabled={!files?.testCode}
            />
          </Tabs>
        </Box>

        <TabPanel value={tabValue} index={0}>
          {files?.toolCode ? (
            <>
              {task.status === 'failed' && (
                <Alert severity="warning" sx={{ m: 2 }}>
                  <Typography variant="body2">
                    Task failed - this may be partial or incomplete code
                  </Typography>
                </Alert>
              )}
              <SyntaxHighlighter
                language="python"
                style={vscDarkPlus}
                customStyle={{
                  margin: 0,
                  borderRadius: 0,
                  maxHeight: '70vh',
                  fontSize: '14px',
                }}
                showLineNumbers
              >
                {files.toolCode}
              </SyntaxHighlighter>
            </>
          ) : (
            <Box p={3}>
              <Typography variant="body1" color="text.secondary" align="center">
                {task.status === 'completed' || task.status === 'failed'
                  ? 'Tool code not available'
                  : 'Tool code will be available when task completes'}
              </Typography>
            </Box>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          {files?.testCode ? (
            <>
              {task.status === 'failed' && (
                <Alert severity="warning" sx={{ m: 2 }}>
                  <Typography variant="body2">
                    Task failed - this may be partial or incomplete code
                  </Typography>
                </Alert>
              )}
              <SyntaxHighlighter
                language="python"
                style={vscDarkPlus}
                customStyle={{
                  margin: 0,
                  borderRadius: 0,
                  maxHeight: '70vh',
                  fontSize: '14px',
                }}
                showLineNumbers
              >
                {files.testCode}
              </SyntaxHighlighter>
            </>
          ) : (
            <Box p={3}>
              <Typography variant="body1" color="text.secondary" align="center">
                {task.status === 'completed' || task.status === 'failed'
                  ? 'Test code not available'
                  : 'Test code will be available when task completes'}
              </Typography>
            </Box>
          )}
        </TabPanel>
      </Paper>

      {/* Additional Info */}
      {files && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Task Status: {files.status}
          </Typography>
        </Paper>
      )}
    </Container>
  );
};
