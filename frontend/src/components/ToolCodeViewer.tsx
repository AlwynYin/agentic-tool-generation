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
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import DownloadIcon from '@mui/icons-material/Download';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ToolFile } from '../types';

interface ToolCodeViewerProps {
  tool: ToolFile | null;
  open: boolean;
  onClose: () => void;
}

export function ToolCodeViewer({ tool, open, onClose }: ToolCodeViewerProps) {
  const handleDownload = () => {
    if (!tool) return;

    const blob = new Blob([tool.code], { type: 'text/x-python' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = tool.fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!tool) return null;

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
            <Typography variant="h6">{tool.fileName}</Typography>
            <Typography variant="body2" color="text.secondary">
              {tool.description}
            </Typography>
          </Box>
          <Box>
            <Tooltip title="Download">
              <IconButton onClick={handleDownload} color="primary">
                <DownloadIcon />
              </IconButton>
            </Tooltip>
            <IconButton onClick={onClose}>
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 0 }}>
        <SyntaxHighlighter
          language="python"
          style={vscDarkPlus}
          showLineNumbers
          customStyle={{
            margin: 0,
            borderRadius: 0,
            fontSize: '14px',
            height: '100%',
          }}
        >
          {tool.code}
        </SyntaxHighlighter>
      </DialogContent>

      <DialogActions>
        <Box sx={{ p: 1, width: '100%' }}>
          <Typography variant="caption" color="text.secondary">
            File Path: {tool.filePath}
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            Created: {new Date(tool.createdAt).toLocaleString()}
          </Typography>
        </Box>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
