import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Alert,
  CircularProgress,
  Typography,
  Box,
} from '@mui/material';
import { ApiClient } from '../api';

interface ExtractAndSubmitDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (jobId: string) => void;
}

export const ExtractAndSubmitDialog: React.FC<ExtractAndSubmitDialogProps> = ({
  open,
  onClose,
  onSuccess,
}) => {
  const [taskDescription, setTaskDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [extractedCount, setExtractedCount] = useState<number | null>(null);

  const handleSubmit = async () => {
    if (!taskDescription.trim()) {
      setError('Please enter a task description');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setExtractedCount(null);

      const response = await ApiClient.extractAndSubmit(taskDescription, 'web-ui-extract');

      setExtractedCount(response.requirements_count);

      // Wait a moment to show the success message
      setTimeout(() => {
        onSuccess(response.job_id);
        handleClose();
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to extract and submit job');
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setTaskDescription('');
      setError(null);
      setExtractedCount(null);
      onClose();
    }
  };

  const isValid = taskDescription.trim().length > 0;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{ sx: { maxHeight: '90vh' } }}
    >
      <DialogTitle>Extract and Submit</DialogTitle>
      <DialogContent dividers>
        <Box mb={2}>
          <Typography variant="body2" color="text.secondary" paragraph>
            Describe your task in natural language. The system will automatically extract tool requirements
            and create a job for you.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <strong>Example:</strong> "I need tools to calculate molecular weight from SMILES, find the
            boiling point of a compound, and optimize molecular geometry using DFT."
          </Typography>
        </Box>

        {error && (
          <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {extractedCount !== null && (
          <Alert severity="success" sx={{ mb: 2 }}>
            Successfully extracted {extractedCount} tool requirement{extractedCount !== 1 ? 's' : ''}!
            Creating job...
          </Alert>
        )}

        <TextField
          label="Task Description"
          placeholder="Describe what tools you need..."
          value={taskDescription}
          onChange={(e) => setTaskDescription(e.target.value)}
          fullWidth
          multiline
          rows={8}
          required
          disabled={loading}
          autoFocus
        />

        <Box mt={2}>
          <Typography variant="caption" color="text.secondary">
            {taskDescription.length} characters
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={!isValid || loading}
          startIcon={loading && <CircularProgress size={16} />}
        >
          {loading ? (extractedCount !== null ? 'Creating Job...' : 'Extracting...') : 'Extract and Submit'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
