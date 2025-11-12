import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Chip,
  Box,
  Alert,
} from '@mui/material';
import CodeIcon from '@mui/icons-material/Code';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { ToolFile, ToolGenerationFailure } from '../types';
import { TabbedCodeViewer } from './TabbedCodeViewer';

interface ToolListProps {
  tools: ToolFile[];
  failures: ToolGenerationFailure[];
}

export function ToolList({ tools, failures }: ToolListProps) {
  const [selectedTool, setSelectedTool] = useState<ToolFile | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);

  const handleToolClick = (tool: ToolFile) => {
    setSelectedTool(tool);
    setViewerOpen(true);
  };

  const handleViewerClose = () => {
    setViewerOpen(false);
  };

  if (tools.length === 0 && failures.length === 0) {
    return null;
  }

  return (
    <>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Generated Tools
          </Typography>

          {tools.length > 0 && (
            <Box mb={2}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Successfully generated tools (click to view code):
              </Typography>
              <List>
                {tools.map((tool) => (
                  <ListItem key={tool.toolId} disablePadding>
                    <ListItemButton onClick={() => handleToolClick(tool)}>
                      <CodeIcon sx={{ mr: 2, color: 'success.main' }} />
                      <ListItemText
                        primary={tool.fileName}
                        secondary={tool.description}
                      />
                      <Chip
                        label="Success"
                        color="success"
                        size="small"
                      />
                    </ListItemButton>
                  </ListItem>
                ))}
              </List>
            </Box>
          )}

          {failures.length > 0 && (
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Failed generations:
              </Typography>
              <List>
                {failures.map((failure, index) => (
                  <ListItem key={index}>
                    <ErrorOutlineIcon sx={{ mr: 2, color: 'error.main' }} />
                    <ListItemText
                      primary={failure.toolRequirement.description}
                      secondary={
                        <Box component="span">
                          <Typography variant="caption" color="error" display="block">
                            Error: {failure.error}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Type: {failure.error_type}
                          </Typography>
                        </Box>
                      }
                    />
                    <Chip
                      label="Failed"
                      color="error"
                      size="small"
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}
        </CardContent>
      </Card>

      <TabbedCodeViewer
        tool={selectedTool}
        open={viewerOpen}
        onClose={handleViewerClose}
      />
    </>
  );
}
