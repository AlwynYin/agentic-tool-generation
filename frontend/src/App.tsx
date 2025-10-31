import { useState } from 'react';
import {
  Container,
  AppBar,
  Toolbar,
  Typography,
  Box,
  CssBaseline,
  ThemeProvider,
  createTheme,
  Stack,
} from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';
import { JobSubmissionForm } from './components/JobSubmissionForm';
import { JobDashboard } from './components/JobDashboard';
import { ToolList } from './components/ToolList';
import { JobResponse } from './types';

const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

function App() {
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [currentJob, setCurrentJob] = useState<JobResponse | null>(null);

  const handleJobCreated = (jobId: string) => {
    setCurrentJobId(jobId);
    setCurrentJob(null);
  };

  const handleJobUpdate = (job: JobResponse) => {
    setCurrentJob(job);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <AppBar position="static">
          <Toolbar>
            <ScienceIcon sx={{ mr: 2 }} />
            <Typography variant="h6" component="div">
              Tool Generation Service
            </Typography>
          </Toolbar>
        </AppBar>

        <Container maxWidth="lg" sx={{ mt: 4, mb: 4, flex: 1 }}>
          <Stack spacing={3}>
            {!currentJobId && (
              <JobSubmissionForm onJobCreated={handleJobCreated} />
            )}

            {currentJobId && (
              <>
                <JobDashboard
                  jobId={currentJobId}
                  onJobUpdate={handleJobUpdate}
                />

                {currentJob && (currentJob.toolFiles || currentJob.failures) && (
                  <ToolList
                    tools={currentJob.toolFiles || []}
                    failures={currentJob.failures || []}
                  />
                )}
              </>
            )}
          </Stack>
        </Container>

        <Box
          component="footer"
          sx={{
            py: 3,
            px: 2,
            mt: 'auto',
            backgroundColor: (theme) =>
              theme.palette.mode === 'light'
                ? theme.palette.grey[200]
                : theme.palette.grey[800],
          }}
        >
          <Container maxWidth="lg">
            <Typography variant="body2" color="text.secondary" align="center">
              Tool Generation Backend - Multi-Agent Pipeline V2
            </Typography>
          </Container>
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default App;
