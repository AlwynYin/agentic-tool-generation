import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  CssBaseline,
  ThemeProvider,
  createTheme,
  Container,
} from '@mui/material';
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import ScienceIcon from '@mui/icons-material/Science';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { DashboardPage } from './pages/DashboardPage';
import { JobDetailsPage } from './pages/JobDetailsPage';
import { TaskDetailsPage } from './pages/TaskDetailsPage';

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

function AppContent() {
  const navigate = useNavigate();

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="static">
        <Toolbar>
          <ScienceIcon sx={{ mr: 2 }} />
          <Typography
            variant="h6"
            component="div"
            sx={{ cursor: 'pointer' }}
            onClick={() => navigate('/')}
          >
            Tool Generation Service
          </Typography>
        </Toolbar>
      </AppBar>

      <Box component="main" sx={{ flex: 1, py: 3 }}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/jobs/:jobId" element={<JobDetailsPage />} />
          <Route path="/jobs/:jobId/tasks/:taskId" element={<TaskDetailsPage />} />
        </Routes>
      </Box>

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
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <WebSocketProvider>
          <AppContent />
        </WebSocketProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
