import React from 'react';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  LinearProgress,
  Alert,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Chip,
  Button,
  IconButton,
  Divider,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
  CloudQueue as CloudIcon,
  Storage as StorageIcon,
  Psychology as AIIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  NetworkCheck as NetworkIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from 'react-query';

const API_BASE_URL = 'http://localhost:8000';

interface SystemHealth {
  status: string;
  services: {
    openai: boolean;
    qdrant: boolean;
    memgraph: boolean;
  };
  analyzer_ready: boolean;
  uptime: number;
  version: string;
}

interface IndexStats {
  lexical_index: {
    document_count: number;
    last_updated: string;
    index_size_mb: number;
  };
  vector_index: {
    collection_exists: boolean;
    points_count: number;
    vectors_size_mb: number;
  };
  dependency_graph: {
    nodes: number;
    edges: number;
    last_updated: string;
  };
}

interface ServiceConfig {
  openai_model: string;
  qdrant_url: string;
  memgraph_host: string;
  cache_size_mb: number;
  max_file_size_mb: number;
}

const SystemStatus: React.FC = () => {
  const queryClient = useQueryClient();

  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useQuery<SystemHealth>(
    'system-health',
    async () => {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) throw new Error('Failed to fetch health');
      return response.json();
    },
    { refetchInterval: 30000 }
  );

  const { data: stats, isLoading: statsLoading, refetch: refetchStats } = useQuery<IndexStats>(
    'index-stats',
    async () => {
      const response = await fetch(`${API_BASE_URL}/index/stats`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      return response.json();
    },
    { refetchInterval: 60000 }
  );

  const { data: config } = useQuery<ServiceConfig>(
    'service-config',
    async () => {
      const response = await fetch(`${API_BASE_URL}/config`);
      if (!response.ok) throw new Error('Failed to fetch config');
      return response.json();
    }
  );

  const clearIndexMutation = useMutation(
    async (indexType: string) => {
      const response = await fetch(`${API_BASE_URL}/index/${indexType}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error(`Failed to clear ${indexType} index`);
      return response.json();
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('index-stats');
      },
    }
  );

  const getStatusIcon = (status: boolean) => {
    return status ? (
      <CheckIcon sx={{ color: 'success.main' }} />
    ) : (
      <ErrorIcon sx={{ color: 'error.main' }} />
    );
  };

  const getStatusColor = (status: boolean) => {
    return status ? 'success' : 'error';
  };

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const formatFileSize = (mb: number) => {
    if (mb < 1) return `${(mb * 1024).toFixed(1)} KB`;
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    return `${(mb / 1024).toFixed(1)} GB`;
  };

  const services = [
    {
      name: 'OpenAI API',
      description: 'Semantic embeddings and AI features',
      status: health?.services.openai || false,
      icon: <AIIcon />,
      details: config?.openai_model || 'text-embedding-3-small',
    },
    {
      name: 'Qdrant Vector DB',
      description: 'Vector similarity search',
      status: health?.services.qdrant || false,
      icon: <StorageIcon />,
      details: config?.qdrant_url ? 'Cloud Connected' : 'Local/Offline',
    },
    {
      name: 'Memgraph',
      description: 'Dependency graph analysis',
      status: health?.services.memgraph || false,
      icon: <NetworkIcon />,
      details: config?.memgraph_host || 'Not configured',
    },
  ];

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 4 }}>
        <Box>
          <Typography variant="h3" sx={{ mb: 1 }}>
            System Status
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Monitor system health, performance, and configuration
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => {
              refetchHealth();
              refetchStats();
            }}
          >
            Refresh
          </Button>
        </Box>
      </Box>

      {/* System Overview */}
      <Grid container spacing={4} sx={{ mb: 4 }}>
        <Grid item xs={12} md={6} lg={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                {health?.analyzer_ready ? (
                  <CheckIcon sx={{ color: 'success.main', mr: 1 }} />
                ) : (
                  <WarningIcon sx={{ color: 'warning.main', mr: 1 }} />
                )}
                <Typography variant="h6">System Status</Typography>
              </Box>
              <Typography variant="h4" color={health?.analyzer_ready ? 'success.main' : 'warning.main'}>
                {health?.analyzer_ready ? 'Ready' : 'Limited'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {health?.analyzer_ready ? 'All systems operational' : 'Some services offline'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6} lg={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <SpeedIcon sx={{ color: 'primary.main', mr: 1 }} />
                <Typography variant="h6">Uptime</Typography>
              </Box>
              <Typography variant="h4" color="primary.main">
                {health?.uptime ? formatUptime(health.uptime) : '0h 0m'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                System running time
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6} lg={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <CloudIcon sx={{ color: 'secondary.main', mr: 1 }} />
                <Typography variant="h6">Services</Typography>
              </Box>
              <Typography variant="h4" color="secondary.main">
                {health ? Object.values(health.services).filter(Boolean).length : 0}/3
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active services
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6} lg={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <MemoryIcon sx={{ color: 'warning.main', mr: 1 }} />
                <Typography variant="h6">Cache Size</Typography>
              </Box>
              <Typography variant="h4" color="warning.main">
                {stats ? formatFileSize(
                  (stats.lexical_index.index_size_mb || 0) + 
                  (stats.vector_index.vectors_size_mb || 0)
                ) : '0 MB'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total index size
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Service Status */}
      <Grid container spacing={4}>
        <Grid item xs={12} lg={8}>
          <Card sx={{ mb: 4 }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Service Health
              </Typography>
              <List>
                {services.map((service, index) => (
                  <React.Fragment key={service.name}>
                    <ListItem>
                      <ListItemIcon>{service.icon}</ListItemIcon>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Typography variant="subtitle1">{service.name}</Typography>
                            <Chip
                              label={service.status ? 'Online' : 'Offline'}
                              color={getStatusColor(service.status)}
                              size="small"
                              variant="outlined"
                              icon={getStatusIcon(service.status)}
                            />
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {service.description}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {service.details}
                            </Typography>
                          </Box>
                        }
                      />
                    </ListItem>
                    {index < services.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            </CardContent>
          </Card>

          {/* Index Statistics */}
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Index Statistics
              </Typography>
              <TableContainer component={Paper} variant="outlined">
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Index Type</TableCell>
                      <TableCell align="right">Documents/Points</TableCell>
                      <TableCell align="right">Size</TableCell>
                      <TableCell align="right">Last Updated</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    <TableRow>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <SpeedIcon fontSize="small" />
                          Lexical Index
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        {stats?.lexical_index.document_count || 0}
                      </TableCell>
                      <TableCell align="right">
                        {formatFileSize(stats?.lexical_index.index_size_mb || 0)}
                      </TableCell>
                      <TableCell align="right">
                        {stats?.lexical_index.last_updated || 'Never'}
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          onClick={() => clearIndexMutation.mutate('lexical')}
                          disabled={clearIndexMutation.isLoading}
                        >
                          Clear
                        </Button>
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <StorageIcon fontSize="small" />
                          Vector Index
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        {stats?.vector_index.points_count || 0}
                      </TableCell>
                      <TableCell align="right">
                        {formatFileSize(stats?.vector_index.vectors_size_mb || 0)}
                      </TableCell>
                      <TableCell align="right">
                        {stats?.vector_index.collection_exists ? 'Active' : 'Empty'}
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          onClick={() => clearIndexMutation.mutate('vector')}
                          disabled={clearIndexMutation.isLoading}
                        >
                          Clear
                        </Button>
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <NetworkIcon fontSize="small" />
                          Dependency Graph
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        {stats?.dependency_graph.nodes || 0} nodes
                      </TableCell>
                      <TableCell align="right">
                        {stats?.dependency_graph.edges || 0} edges
                      </TableCell>
                      <TableCell align="right">
                        {stats?.dependency_graph.last_updated || 'Never'}
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          onClick={() => clearIndexMutation.mutate('graph')}
                          disabled={clearIndexMutation.isLoading}
                        >
                          Clear
                        </Button>
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Configuration Panel */}
        <Grid item xs={12} lg={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Configuration
              </Typography>
              
              {config && (
                <List dense>
                  <ListItem>
                    <ListItemText
                      primary="OpenAI Model"
                      secondary={config.openai_model}
                    />
                  </ListItem>
                  <Divider />
                  <ListItem>
                    <ListItemText
                      primary="Cache Size Limit"
                      secondary={`${config.cache_size_mb} MB`}
                    />
                  </ListItem>
                  <Divider />
                  <ListItem>
                    <ListItemText
                      primary="Max File Size"
                      secondary={`${config.max_file_size_mb} MB`}
                    />
                  </ListItem>
                </List>
              )}

              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle2" sx={{ mb: 2 }}>
                  Quick Actions
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => clearIndexMutation.mutate('all')}
                    disabled={clearIndexMutation.isLoading}
                  >
                    Clear All Indexes
                  </Button>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => window.open(`${API_BASE_URL}/docs`, '_blank')}
                  >
                    API Documentation
                  </Button>
                </Box>
              </Box>
            </CardContent>
          </Card>

          {/* System Info */}
          <Card sx={{ mt: 3 }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                System Information
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText
                    primary="Version"
                    secondary={health?.version || '1.0.0'}
                  />
                </ListItem>
                <Divider />
                <ListItem>
                  <ListItemText
                    primary="API Base URL"
                    secondary={API_BASE_URL}
                  />
                </ListItem>
                <Divider />
                <ListItem>
                  <ListItemText
                    primary="Status"
                    secondary={health?.status || 'Unknown'}
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Container>
  );
};

export default SystemStatus;
