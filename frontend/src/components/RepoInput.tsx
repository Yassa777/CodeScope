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

const RepoInput: React.FC<RepoInputProps> = ({ onAnalysisComplete }) => {
  const [repoUrl, setRepoUrl] = useState('');
  const [error, setError] = useState<string | null>(null);

  const { mutate: analyzeRepo, isLoading } = useMutation(
    async (url: string) => {
      const response = await fetch('/api/repo', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) {
        const errorData = await response.text();
        throw new Error(errorData || 'Failed to analyze repository');
      }

      const data = await response.json();
      return data;
    },
    {
      onSuccess: (data) => {
        if (data.id) {
          onAnalysisComplete(data.id);
        } else {
          setError('Invalid response from server');
        }
      },
      onError: (error: Error) => {
        setError(error.message);
      },
    }
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate GitHub URL
    const githubUrlPattern = /^https:\/\/github\.com\/[\w-]+\/[\w-]+$/;
    if (!githubUrlPattern.test(repoUrl)) {
      setError('Please enter a valid GitHub repository URL');
      return;
    }

    analyzeRepo(repoUrl);
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
          disabled={isLoading}
          error={!!error}
          helperText={error}
        />
        <Button
          type="submit"
          variant="contained"
          disabled={isLoading || !repoUrl}
          sx={{ minWidth: 100 }}
        >
          {isLoading ? (
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