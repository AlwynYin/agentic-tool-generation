import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  IconButton,
  Tooltip,
  Tabs,
  Tab,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import DownloadIcon from '@mui/icons-material/Download';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ToolFile, TaskFilesResponse } from '../types';

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
      id={`file-tabpanel-${index}`}
      aria-labelledby={`file-tab-${index}`}
      style={{ height: '100%' }}
      {...other}
    >
      {value === index && <Box sx={{ height: '100%' }}>{children}</Box>}
    </div>
  );
}

interface FileTab {
  label: string;
  content: string;
  language: 'python' | 'text';
  fileName?: string;
}

interface TabbedCodeViewerProps {
  tool?: ToolFile | null;
  taskFiles?: TaskFilesResponse | null;
  open: boolean;
  onClose: () => void;
}

export function TabbedCodeViewer({ tool, taskFiles, open, onClose }: TabbedCodeViewerProps) {
  const [activeTab, setActiveTab] = useState(0);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  // Build tabs from available files
  const tabs: FileTab[] = [];

  // Debug logging
  console.log('TabbedCodeViewer - tool:', tool ? {
    code: !!tool.code,
    testCode: !!tool.testCode,
    implementationPlan: !!tool.implementationPlan,
    functionSpec: !!tool.functionSpec,
    contractsPlan: !!tool.contractsPlan,
    validationRules: !!tool.validationRules,
    testRequirements: !!tool.testRequirements,
    searchResults: !!tool.searchResults,
  } : null);
  console.log('TabbedCodeViewer - taskFiles:', taskFiles ? {
    toolCode: !!taskFiles.toolCode,
    testCode: !!taskFiles.testCode,
    implementationPlan: !!taskFiles.implementationPlan,
    functionSpec: !!taskFiles.functionSpec,
    contractsPlan: !!taskFiles.contractsPlan,
    validationRules: !!taskFiles.validationRules,
    testRequirements: !!taskFiles.testRequirements,
    searchResults: !!taskFiles.searchResults,
  } : null);

  // Tool code tab
  const toolCode = tool?.code || taskFiles?.toolCode;
  const toolFileName = tool?.fileName || taskFiles?.toolFileName;
  if (toolCode) {
    tabs.push({
      label: 'Tool Code',
      content: toolCode,
      language: 'python',
      fileName: toolFileName,
    });
  }

  // Test code tab
  const testCode = tool?.testCode || taskFiles?.testCode;
  const testFileName = taskFiles?.testFileName;
  if (testCode) {
    tabs.push({
      label: 'Test Code',
      content: testCode,
      language: 'python',
      fileName: testFileName,
    });
  }

  // Implementation plan tab
  const implementationPlan = tool?.implementationPlan || taskFiles?.implementationPlan;
  if (implementationPlan) {
    tabs.push({
      label: 'Implementation Plan',
      content: implementationPlan,
      language: 'text',
    });
  }

  // Function spec tab
  const functionSpec = tool?.functionSpec || taskFiles?.functionSpec;
  if (functionSpec) {
    tabs.push({
      label: 'Function Spec',
      content: functionSpec,
      language: 'text',
    });
  }

  // Contracts tab
  const contractsPlan = tool?.contractsPlan || taskFiles?.contractsPlan;
  if (contractsPlan) {
    tabs.push({
      label: 'Contracts',
      content: contractsPlan,
      language: 'text',
    });
  }

  // Validation rules tab
  const validationRules = tool?.validationRules || taskFiles?.validationRules;
  if (validationRules) {
    tabs.push({
      label: 'Validation Rules',
      content: validationRules,
      language: 'text',
    });
  }

  // Test requirements tab
  const testRequirements = tool?.testRequirements || taskFiles?.testRequirements;
  if (testRequirements) {
    tabs.push({
      label: 'Test Requirements',
      content: testRequirements,
      language: 'text',
    });
  }

  // Search results tab
  const searchResults = tool?.searchResults || taskFiles?.searchResults;
  if (searchResults) {
    tabs.push({
      label: 'Search Results',
      content: searchResults,
      language: 'text', // Always show as raw text (markdown or JSON)
    });
  }

  const handleDownload = (tab: FileTab) => {
    const blob = new Blob([tab.content], {
      type: tab.language === 'python' ? 'text/x-python' : 'text/plain'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = tab.fileName || `${tab.label.toLowerCase().replace(/\s+/g, '_')}.${tab.language === 'python' ? 'py' : 'txt'}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (tabs.length === 0) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="h6">No Files Available</Typography>
            <IconButton onClick={onClose}>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Typography>No files are available for this tool.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  }

  const currentTab = tabs[activeTab];

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { height: '90vh' }
      }}
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box>
            <Typography variant="h6">
              {tool?.fileName || taskFiles?.toolFileName || 'Tool Files'}
            </Typography>
            {tool?.description && (
              <Typography variant="body2" color="text.secondary">
                {tool.description}
              </Typography>
            )}
          </Box>
          <Box>
            {currentTab && (
              <Tooltip title={`Download ${currentTab.label}`}>
                <IconButton onClick={() => handleDownload(currentTab)} color="primary">
                  <DownloadIcon />
                </IconButton>
              </Tooltip>
            )}
            <IconButton onClick={onClose}>
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
        >
          {tabs.map((tab, index) => (
            <Tab key={index} label={tab.label} id={`file-tab-${index}`} />
          ))}
        </Tabs>
      </Box>

      <DialogContent dividers sx={{ p: 0, display: 'flex', flexDirection: 'column', height: 'calc(90vh - 200px)' }}>
        {tabs.map((tab, index) => (
          <TabPanel key={index} value={activeTab} index={index}>
            {tab.language === 'python' ? (
              <SyntaxHighlighter
                language="python"
                style={vscDarkPlus}
                showLineNumbers
                customStyle={{
                  margin: 0,
                  borderRadius: 0,
                  fontSize: '14px',
                  height: '100%',
                  overflow: 'auto',
                }}
              >
                {tab.content}
              </SyntaxHighlighter>
            ) : (
              <Box
                component="pre"
                sx={{
                  m: 0,
                  p: 3,
                  height: '100%',
                  overflow: 'auto',
                  backgroundColor: '#1e1e1e',
                  color: '#d4d4d4',
                  fontFamily: 'monospace',
                  fontSize: '14px',
                  whiteSpace: 'pre-wrap',
                  wordWrap: 'break-word',
                }}
              >
                {tab.content}
              </Box>
            )}
          </TabPanel>
        ))}
      </DialogContent>

      <DialogActions>
        <Box sx={{ p: 1, width: '100%' }}>
          {tool && (
            <>
              <Typography variant="caption" color="text.secondary">
                File Path: {tool.filePath}
              </Typography>
              <Typography variant="caption" color="text.secondary" display="block">
                Created: {new Date(tool.createdAt).toLocaleString()}
              </Typography>
            </>
          )}
          {taskFiles && taskFiles.error && (
            <Typography variant="caption" color="error" display="block">
              Note: {taskFiles.error}
            </Typography>
          )}
        </Box>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
