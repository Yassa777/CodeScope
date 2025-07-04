import React from 'react';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  Chip,
  Avatar,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  Search as SearchIcon,
  Code as CodeIcon,
  Analytics as AnalyticsIcon,
  Psychology as AIIcon,
  PlayArrow as PlayIcon,
  TrendingUp as TrendingUpIcon,
  Storage as StorageIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useQuery } from 'react-query';

const API_BASE_URL = 'http://localhost:8000';

interface SystemHealth {
  status: string;
  services: {
    openai: boolean;
    qdrant: boolean;
    memgraph: boolean;
  };
  analyzer_ready: boolean;
}

interface IndexStats {
  lexical_index: {
    document_count: number;
    last_updated: string;
  };
  vector_index: {
    collection_exists: boolean;
    points_count: number;
  };
  dependency_graph: {
    nodes: number;
    edges: number;
  };
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate();

  const { data: health, isLoading: healthLoading } = useQuery<SystemHealth>(
    'system-health',
    async () => {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) throw new Error('Failed to fetch health');
      return response.json();
    },
    { refetchInterval: 30000 }
  );

  const { data: stats, isLoading: statsLoading } = useQuery<IndexStats>(
    'index-stats',
    async () => {
      const response = await fetch(`${API_BASE_URL}/index/stats`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      return response.json();
    },
    { refetchInterval: 60000 }
  );

  const quickActions = [
    {
      title: 'Analyze Repository',
      description: 'Start analyzing a new codebase',
      icon: <CodeIcon />,
      action: () => navigate('/analysis'),
      primary: true,
    },
    {
      title: 'Search Code',
      description: 'Search existing analyzed code',
      icon: <SearchIcon />,
      action: () => navigate('/search'),
      primary: false,
    },
    {
      title: 'View Statistics',
      description: 'System health and performance',
      icon: <TrendingUpIcon />,
      action: () => navigate('/status'),
      primary: false,
    },
  ];

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Hero Section */}
      <Box sx={{ textAlign: 'center', mb: 6 }}>
        <Typography
          variant="h1"
          sx={{
            background: 'linear-gradient(135deg, #64b5f6, #90caf9)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            mb: 2,
          }}
        >
          🧠 Scout
        </Typography>
        <Typography
          variant="h5"
          color="text.secondary"
          sx={{ mb: 4, maxWidth: 600, mx: 'auto' }}
        >
          AI-Native Operational Intelligence for Engineering Teams
        </Typography>
        
        {/* System Status Alert */}
        {!healthLoading && (
          <Alert
            severity={health?.analyzer_ready ? 'success' : 'warning'}
            sx={{
              maxWidth: 600,
              mx: 'auto',
              mb: 4,
              backgroundColor: 'rgba(26, 31, 46, 0.8)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
            }}
          >
            {health?.analyzer_ready
              ? '🚀 System Ready - All analysis capabilities available'
              : '⚠️ Limited functionality - Some services offline'}
          </Alert>
        )}
      </Box>

      {/* Quick Actions */}
      <Box sx={{ mb: 6 }}>
        <Typography variant="h4" sx={{ mb: 3, textAlign: 'center' }}>
          Quick Actions
        </Typography>
        <Grid container spacing={3} justifyContent="center">
          {quickActions.map((action, index) => (
            <Grid item xs={12} sm={6} md={4} key={index}>
              <Card
                sx={{
                  height: '100%',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: 4,
                  },
                }}
                onClick={action.action}
              >
                <CardContent sx={{ textAlign: 'center', py: 4 }}>
                  <Avatar
                    sx={{
                      bgcolor: action.primary ? 'primary.main' : 'secondary.main',
                      width: 64,
                      height: 64,
                      mx: 'auto',
                      mb: 2,
                    }}
                  >
                    {action.icon}
                  </Avatar>
                  <Typography variant="h6" sx={{ mb: 1 }}>
                    {action.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {action.description}
                  </Typography>
                </CardContent>
                <CardActions sx={{ justifyContent: 'center', pb: 3 }}>
                  <Button
                    variant={action.primary ? 'contained' : 'outlined'}
                    startIcon={<PlayIcon />}
                    onClick={(e) => {
                      e.stopPropagation();
                      action.action();
                    }}
                  >
                    {action.primary ? 'Get Started' : 'Explore'}
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>

      {/* System Statistics */}
      <Box>
        <Typography variant="h4" sx={{ mb: 3, textAlign: 'center' }}>
          System Statistics
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Lexical Index
                </Typography>
                {statsLoading ? (
                  <LinearProgress />
                ) : (
                  <Box>
                    <Typography variant="h4" color="primary.main">
                      {stats?.lexical_index.document_count || 0}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Documents indexed
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Vector Database
                </Typography>
                {statsLoading ? (
                  <LinearProgress />
                ) : (
                  <Box>
                    <Typography variant="h4" color="secondary.main">
                      {stats?.vector_index.points_count || 0}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Vector embeddings
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Dependency Graph
                </Typography>
                {statsLoading ? (
                  <LinearProgress />
                ) : (
                  <Box>
                    <Typography variant="h4" color="success.main">
                      {stats?.dependency_graph.nodes || 0}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Graph nodes
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>

      {/* Footer */}
      <Box sx={{ mt: 8, pt: 4, borderTop: '1px solid rgba(255, 255, 255, 0.12)' }}>
        <Typography variant="body2" color="text.secondary" textAlign="center">
          Built with ❤️ for developers who want to understand code better
        </Typography>
      </Box>
    </Container>
  );
};

export default Dashboard;
