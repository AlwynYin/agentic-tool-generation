import { useState } from 'react';
import {
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import { ApiClient } from '../api';
import { UserToolRequirement } from '../types';

interface JobSubmissionFormProps {
  onJobCreated: (jobId: string) => void;
}

export function JobSubmissionForm({ onJobCreated }: JobSubmissionFormProps) {
  const [requirement, setRequirement] = useState<UserToolRequirement>({
    description: 'Calculate molecular weight from SMILES string',
    input: 'SMILES string representation of a molecule',
    output: 'Molecular weight as a float',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await ApiClient.createJob({
        toolRequirements: [requirement],
      });
      onJobCreated(response.jobId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create job');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h5" gutterBottom>
          Create Tool Generation Job
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Submit a tool requirement to generate a Python chemistry tool
        </Typography>

        <Box component="form" onSubmit={handleSubmit} sx={{ mt: 2 }}>
          <TextField
            fullWidth
            label="Description"
            placeholder="What should the tool do?"
            value={requirement.description}
            onChange={(e) =>
              setRequirement({ ...requirement, description: e.target.value })
            }
            margin="normal"
            required
            multiline
            rows={2}
          />

          <TextField
            fullWidth
            label="Input"
            placeholder="Describe the input parameters"
            value={requirement.input}
            onChange={(e) =>
              setRequirement({ ...requirement, input: e.target.value })
            }
            margin="normal"
            required
            multiline
            rows={2}
          />

          <TextField
            fullWidth
            label="Output"
            placeholder="Describe the expected output"
            value={requirement.output}
            onChange={(e) =>
              setRequirement({ ...requirement, output: e.target.value })
            }
            margin="normal"
            required
            multiline
            rows={2}
          />

          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}

          <Button
            type="submit"
            variant="contained"
            size="large"
            fullWidth
            disabled={loading}
            endIcon={<SendIcon />}
            sx={{ mt: 3 }}
          >
            {loading ? 'Creating Job...' : 'Generate Tool'}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}
