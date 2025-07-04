import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  TextField,
  Button,
  Grid,
  Card,
  CardContent,
  LinearProgress,
  Alert,
  Stepper,
  Step,
  StepLabel,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Folder as FolderIcon,
  InsertDriveFile as FileIcon,
  Functions as FunctionIcon,
  Code as CodeIcon,
  Analytics as AnalyticsIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  ExpandMore as ExpandMoreIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  GitHub as GitHubIcon,
  FolderOpen as LocalFolderIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from 'react-query';

const API_BASE_URL = 'http://localhost:8000';

interface AnalysisProgress {
  stage: string;
  progress: number;
  message: string;
  completed: boolean;
}

interface CodeChunk {
  chunk_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  ast_type: string;
  parent_symbol?: string;
  content: string;
  docstring?: string;
}

interface AnalysisResult {
  repository_path: string;
  total_files: number;
  total_chunks: number;
  analysis_time: number;
  chunks: CodeChunk[];
  summary: {
    languages: Record<string, number>;
    ast_types: Record<string, number>;
    file_types: Record<string, number>;
  };
}

interface CachedRepository {
  local_path: string;
  owner: string;
  repository: string;
  github_url: string;
  commit_hash: string;
  commit_message: string;
  commit_author: string;
  commit_date: string;
  file_count: number;
  size_mb: number;
  last_updated: number;
}

const CachedRepositories: React.FC = () => {
  const { data: repositories } = useQuery<{total_repositories: number, repositories: CachedRepository[]}>(
    'cached-repositories',
    async () => {
      const response = await fetch(`${API_BASE_URL}/github/repositories`);
      if (!response.ok) {
        throw new Error('Failed to fetch repositories');
      }
      return response.json();
    },
    { retry: false, refetchInterval: 30000 }
  );

  if (!repositories || repositories.total_repositories === 0) {
    return null;
  }

  return (
    <Card sx={{ mb: 4 }}>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Cached GitHub Repositories ({repositories.total_repositories})
        </Typography>
        <Grid container spacing={2}>
          {repositories.repositories.map((repo) => (
            <Grid item xs={12} md={6} key={repo.github_url}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <GitHubIcon color="primary" />
                    <Typography variant="subtitle1" component="a" 
                      href={repo.github_url} 
                      target="_blank" 
                      sx={{ textDecoration: 'none', color: 'primary.main' }}
                    >
                      {repo.owner}/{repo.repository}
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    {repo.commit_message}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                    <Chip label={`${repo.file_count} files`} size="small" />
                    <Chip label={`${repo.size_mb} MB`} size="small" />
                    <Chip label={`#${repo.commit_hash}`} size="small" variant="outlined" />
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </CardContent>
    </Card>
  );
};

const AnalysisResults: React.FC = () => {
  const [repoPath, setRepoPath] = useState('');
  const [selectedChunk, setSelectedChunk] = useState<CodeChunk | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [isGitHubUrl, setIsGitHubUrl] = useState(false);
  const queryClient = useQueryClient();

  // Check if input is a GitHub URL
  const checkIfGitHubUrl = (input: string) => {
    const gitHubPattern = /^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+/;
    return gitHubPattern.test(input.trim());
  };

  // Update GitHub URL detection when input changes
  React.useEffect(() => {
    setIsGitHubUrl(checkIfGitHubUrl(repoPath));
  }, [repoPath]);

  const { data: currentAnalysis, isLoading: analysisLoading } = useQuery<AnalysisResult>(
    'current-analysis',
    async () => {
      const response = await fetch(`${API_BASE_URL}/analysis/current`);
      if (!response.ok) {
        if (response.status === 404) return null;
        throw new Error('Failed to fetch analysis');
      }
      return response.json();
    },
    { retry: false }
  );

  const analysisMutation = useMutation(
    async (path: string) => {
      const isGitHub = checkIfGitHubUrl(path);
      const endpoint = isGitHub ? `${API_BASE_URL}/github/analyze` : `${API_BASE_URL}/analyze`;
      const payload = isGitHub 
        ? { github_url: path, force_fresh: false }
        : { repo_path: path };

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      if (!response.ok) {
        const error = await response.text();
        throw new Error(error || 'Analysis failed');
      }
      return response.json();
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('current-analysis');
        queryClient.invalidateQueries('index-stats');
      },
    }
  );

  const handleStartAnalysis = () => {
    if (repoPath.trim()) {
      analysisMutation.mutate(repoPath.trim());
    }
  };

  const handleChunkClick = (chunk: CodeChunk) => {
    setSelectedChunk(chunk);
    setDialogOpen(true);
  };

  const getLanguageColor = (language: string) => {
    const colors: Record<string, string> = {
      python: '#3776ab',
      javascript: '#f7df1e',
      typescript: '#3178c6',
      tsx: '#61dafb',
      jsx: '#61dafb',
    };
    return colors[language.toLowerCase()] || '#666';
  };

  const analysisSteps = [
    'Scanning Files',
    'AST Parsing',
    'Lexical Indexing',
    'Vector Embedding',
    'Graph Building',
  ];

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h3" sx={{ mb: 2 }}>
          Repository Analysis
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Analyze codebases to build comprehensive indexes for search and understanding
        </Typography>
      </Box>

      {/* Analysis Input */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Analyze New Repository
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <TextField
              fullWidth
              label={isGitHubUrl ? "GitHub Repository URL" : "Repository Path"}
              placeholder={isGitHubUrl 
                ? "https://github.com/owner/repository" 
                : "/path/to/your/repository or ."}
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
              variant="outlined"
              helperText={isGitHubUrl 
                ? "GitHub repository will be cloned and analyzed" 
                : "Local repository path for analysis"}
            />
            <Button
              variant="contained"
              startIcon={isGitHubUrl ? <GitHubIcon /> : <LocalFolderIcon />}
              onClick={handleStartAnalysis}
              disabled={analysisMutation.isLoading || !repoPath.trim()}
              sx={{ minWidth: 140 }}
            >
              {analysisMutation.isLoading 
                ? (isGitHubUrl ? 'Cloning...' : 'Analyzing...') 
                : (isGitHubUrl ? 'Clone & Analyze' : 'Analyze')}
            </Button>
          </Box>
          {analysisMutation.isLoading && (
            <Box sx={{ mt: 2 }}>
              <LinearProgress />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Analysis in progress... This may take a few minutes for large repositories.
              </Typography>
            </Box>
          )}
          {analysisMutation.error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {(analysisMutation.error as Error).message}
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Cached GitHub Repositories */}
      <CachedRepositories />

      {/* Current Analysis Results */}
      {currentAnalysis && (
        <Grid container spacing={4}>
          {/* Summary Cards */}
          <Grid item xs={12}>
            <Typography variant="h5" sx={{ mb: 3 }}>
              Analysis Results
            </Typography>
            <Grid container spacing={3}>
              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h4" color="primary.main">
                      {currentAnalysis.total_files}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Files Analyzed
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h4" color="secondary.main">
                      {currentAnalysis.total_chunks}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Code Chunks
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h4" color="success.main">
                      {Object.keys(currentAnalysis.summary.languages).length}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Languages
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h4" color="warning.main">
                      {Math.round(currentAnalysis.analysis_time)}s
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Analysis Time
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Grid>

          {/* Language Distribution */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Language Distribution
                </Typography>
                <List dense>
                  {Object.entries(currentAnalysis.summary.languages).map(([lang, count]) => (
                    <ListItem key={lang}>
                      <ListItemIcon>
                        <Box
                          sx={{
                            width: 16,
                            height: 16,
                            borderRadius: '50%',
                            bgcolor: getLanguageColor(lang),
                          }}
                        />
                      </ListItemIcon>
                      <ListItemText
                        primary={lang.toUpperCase()}
                        secondary={`${count} files`}
                      />
                      <Chip
                        label={`${((count / currentAnalysis.total_files) * 100).toFixed(1)}%`}
                        size="small"
                        variant="outlined"
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>

          {/* AST Types */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Code Structure
                </Typography>
                <List dense>
                  {Object.entries(currentAnalysis.summary.ast_types)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 10)
                    .map(([type, count]) => (
                      <ListItem key={type}>
                        <ListItemIcon>
                          {type.includes('function') ? (
                            <FunctionIcon fontSize="small" />
                          ) : type.includes('class') ? (
                            <CodeIcon fontSize="small" />
                          ) : (
                            <FileIcon fontSize="small" />
                          )}
                        </ListItemIcon>
                        <ListItemText
                          primary={type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                          secondary={`${count} occurrences`}
                        />
                      </ListItem>
                    ))}
                </List>
              </CardContent>
            </Card>
          </Grid>

          {/* Code Chunks Preview */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                  <Typography variant="h6">
                    Code Chunks ({currentAnalysis.chunks.length})
                  </Typography>
                  <Button
                    startIcon={<DownloadIcon />}
                    onClick={() => {
                      const data = JSON.stringify(currentAnalysis, null, 2);
                      const blob = new Blob([data], { type: 'application/json' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = 'analysis-results.json';
                      a.click();
                    }}
                  >
                    Export
                  </Button>
                </Box>
                
                <Box sx={{ maxHeight: 600, overflow: 'auto' }}>
                  {currentAnalysis.chunks.slice(0, 50).map((chunk, index) => (
                    <Accordion key={index}>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', flexGrow: 1 }}>
                            {chunk.file_path}:{chunk.start_line}-{chunk.end_line}
                          </Typography>
                          <Chip
                            label={chunk.ast_type}
                            size="small"
                            variant="outlined"
                          />
                          {chunk.parent_symbol && (
                            <Chip
                              label={chunk.parent_symbol}
                              size="small"
                              color="primary"
                              variant="outlined"
                            />
                          )}
                        </Box>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Box
                          sx={{
                            bgcolor: 'grey.900',
                            p: 2,
                            borderRadius: 1,
                            fontFamily: 'monospace',
                            fontSize: '0.875rem',
                            maxHeight: 300,
                            overflow: 'auto',
                            cursor: 'pointer',
                          }}
                          onClick={() => handleChunkClick(chunk)}
                        >
                          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                            {chunk.content.substring(0, 500)}
                            {chunk.content.length > 500 && '...'}
                          </pre>
                        </Box>
                        {chunk.docstring && (
                          <Alert severity="info" sx={{ mt: 2 }}>
                            <Typography variant="body2">{chunk.docstring}</Typography>
                          </Alert>
                        )}
                      </AccordionDetails>
                    </Accordion>
                  ))}
                  
                  {currentAnalysis.chunks.length > 50 && (
                    <Box sx={{ textAlign: 'center', mt: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        Showing first 50 chunks. Use search to explore more.
                      </Typography>
                    </Box>
                  )}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* No Analysis State */}
      {!currentAnalysis && !analysisLoading && !analysisMutation.isLoading && (
        <Card>
          <CardContent sx={{ textAlign: 'center', py: 6 }}>
            <AnalyticsIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" sx={{ mb: 2 }}>
              No Repository Analyzed Yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Enter a repository path above to start your first analysis
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Code Chunk Detail Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          {selectedChunk?.file_path}:{selectedChunk?.start_line}-{selectedChunk?.end_line}
        </DialogTitle>
        <DialogContent>
          <Box
            sx={{
              bgcolor: 'grey.900',
              p: 3,
              borderRadius: 1,
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              maxHeight: 500,
              overflow: 'auto',
            }}
          >
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
              {selectedChunk?.content}
            </pre>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Close</Button>
          <Button
            onClick={() => {
              if (selectedChunk) {
                navigator.clipboard.writeText(selectedChunk.content);
              }
            }}
            variant="contained"
          >
            Copy Code
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default AnalysisResults;
