import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  IconButton,
  Stack,
  Alert,
  CircularProgress,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { ApiClient } from '../api';
import { UserToolRequirement } from '../types';

interface ManualJobDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (jobId: string) => void;
}

export const ManualJobDialog: React.FC<ManualJobDialogProps> = ({ open, onClose, onSuccess }) => {
  const [requirements, setRequirements] = useState<UserToolRequirement[]>([
    { description: '', input: '', output: '' }
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAddRequirement = () => {
    setRequirements([...requirements, { description: '', input: '', output: '' }]);
  };

  const handleRemoveRequirement = (index: number) => {
    if (requirements.length > 1) {
      setRequirements(requirements.filter((_, i) => i !== index));
    }
  };

  const handleRequirementChange = (index: number, field: keyof UserToolRequirement, value: string) => {
    const updated = [...requirements];
    updated[index] = { ...updated[index], [field]: value };
    setRequirements(updated);
  };

  const handleSubmit = async () => {
    // Validate requirements
    const validRequirements = requirements.filter(
      req => req.description.trim() && req.input.trim() && req.output.trim()
    );

    if (validRequirements.length === 0) {
      setError('Please provide at least one complete tool requirement');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await ApiClient.createJob({
        toolRequirements: validRequirements,
        metadata: {
          clientId: 'web-ui-manual',
        },
      });

      onSuccess(response.jobId);
      handleClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create job');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setRequirements([{ description: '', input: '', output: '' }]);
      setError(null);
      onClose();
    }
  };

  const isValid = requirements.some(
    req => req.description.trim() && req.input.trim() && req.output.trim()
  );

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{ sx: { maxHeight: '90vh' } }}
    >
      <DialogTitle>Create Job (Manual Entry)</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={3}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {requirements.map((req, index) => (
            <Box key={index} sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 2 }}>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Box fontWeight="bold">Tool Requirement #{index + 1}</Box>
                {requirements.length > 1 && (
                  <IconButton
                    size="small"
                    onClick={() => handleRemoveRequirement(index)}
                    color="error"
                  >
                    <DeleteIcon />
                  </IconButton>
                )}
              </Box>

              <Stack spacing={2}>
                <TextField
                  label="Description"
                  placeholder="e.g., Calculate molecular weight from SMILES"
                  value={req.description}
                  onChange={(e) => handleRequirementChange(index, 'description', e.target.value)}
                  fullWidth
                  multiline
                  rows={2}
                  required
                />
                <TextField
                  label="Input"
                  placeholder="e.g., SMILES string"
                  value={req.input}
                  onChange={(e) => handleRequirementChange(index, 'input', e.target.value)}
                  fullWidth
                  required
                />
                <TextField
                  label="Output"
                  placeholder="e.g., Molecular weight in g/mol"
                  value={req.output}
                  onChange={(e) => handleRequirementChange(index, 'output', e.target.value)}
                  fullWidth
                  required
                />
              </Stack>
            </Box>
          ))}

          <Button
            startIcon={<AddIcon />}
            onClick={handleAddRequirement}
            variant="outlined"
          >
            Add Another Requirement
          </Button>
        </Stack>
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
          {loading ? 'Creating...' : 'Create Job'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
