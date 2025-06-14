import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import { useMutation } from 'react-query';

interface RepoInputProps {
  onAnalysisComplete: (repoId: string) => void;
}

const API_BASE_URL = 'http://localhost:8000/api';

const RepoInput: React.FC<RepoInputProps> = ({ onAnalysisComplete }) => {
  const [repoUrl, setRepoUrl] = useState('');
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (url: string) => {
      const response = await fetch(`${API_BASE_URL}/repo`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url }),
      });
      
      if (!response.ok) {
        const error = await response.text();
        throw new Error(error || 'Failed to analyze repository');
      }
      
      return response.json();
    },
    onSuccess: (data) => {
      onAnalysisComplete(data.id);
    },
    onError: (error: Error) => {
      setError(error.message);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate GitHub URL
    const githubUrlPattern = /^https:\/\/github\.com\/[\w-]+\/[\w-]+$/;
    if (!githubUrlPattern.test(repoUrl)) {
      setError('Please enter a valid GitHub repository URL');
      return;
    }

    mutation.mutate(repoUrl);
  };

  return (
    <Box
      component="form"
      onSubmit={handleSubmit}
      sx={{
        p: 2,
        borderBottom: 1,
        borderColor: 'divider',
      }}
    >
      <Typography variant="h6" gutterBottom>
        Analyze Repository
      </Typography>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <TextField
          fullWidth
          size="small"
          placeholder="Enter GitHub repository URL"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          disabled={mutation.isLoading}
          error={!!error}
          helperText={error}
        />
        <Button
          type="submit"
          variant="contained"
          disabled={mutation.isLoading || !repoUrl}
          sx={{ minWidth: 100 }}
        >
          {mutation.isLoading ? (
            <CircularProgress size={24} color="inherit" />
          ) : (
            'Analyze'
          )}
        </Button>
      </Box>
      {error && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {error}
        </Alert>
      )}
    </Box>
  );
};

export default RepoInput; 