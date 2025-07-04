import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Alert,
  Chip,
  CircularProgress,
} from '@mui/material';
import { GitHub as GitHubIcon } from '@mui/icons-material';

const API_BASE_URL = 'http://localhost:8000';

const GitHubRepoTest: React.FC = () => {
  const [repoUrl, setRepoUrl] = useState('https://github.com/octocat/Hello-World');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleClone = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/github/clone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ github_url: repoUrl, force_fresh: false }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/github/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ github_url: repoUrl, force_fresh: false }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 800, mx: 'auto' }}>
      <Typography variant="h4" sx={{ mb: 3 }}>
        GitHub Repository Test
      </Typography>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Test GitHub Integration
          </Typography>
          
          <TextField
            fullWidth
            label="GitHub Repository URL"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            sx={{ mb: 2 }}
          />

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              startIcon={loading ? <CircularProgress size={16} /> : <GitHubIcon />}
              onClick={handleClone}
              disabled={loading}
            >
              Clone Only
            </Button>
            <Button
              variant="contained"
              startIcon={loading ? <CircularProgress size={16} /> : <GitHubIcon />}
              onClick={handleAnalyze}
              disabled={loading}
            >
              Clone & Analyze
            </Button>
          </Box>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {result && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Result
            </Typography>
            
            {result.github_info ? (
              // Full analysis result
              <Box>
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                  GitHub Info:
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                  <Chip label={`${result.github_info.owner}/${result.github_info.repository}`} />
                  <Chip label={`${result.github_info.action}`} color="primary" />
                  <Chip label={`${result.github_info.file_count} files`} />
                  <Chip label={`${result.github_info.size_mb} MB`} />
                  <Chip label={`#${result.github_info.commit_hash}`} variant="outlined" />
                </Box>
                
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                  Analysis Info:
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                  <Chip label={`${result.analysis_result.total_files} analyzed files`} />
                  <Chip label={`${result.analysis_result.total_chunks} chunks`} />
                </Box>
              </Box>
            ) : (
              // Clone only result
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip label={`${result.owner}/${result.repository}`} />
                <Chip label={`${result.action}`} color="primary" />
                <Chip label={`${result.file_count} files`} />
                <Chip label={`${result.size_mb} MB`} />
                <Chip label={`#${result.commit_hash}`} variant="outlined" />
              </Box>
            )}

            <Typography variant="caption" sx={{ mt: 2, display: 'block' }}>
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </Typography>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default GitHubRepoTest; 