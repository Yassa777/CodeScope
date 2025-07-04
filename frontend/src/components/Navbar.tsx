import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Chip,
  Avatar,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Search as SearchIcon,
  Dashboard as DashboardIcon,
  Analytics as AnalyticsIcon,
  Timeline as TimelineIcon,
  Settings as SettingsIcon,
  GitHub as GitHubIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
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

const Navbar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const { data: health } = useQuery<SystemHealth>(
    'system-health',
    async () => {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) {
        throw new Error('Failed to fetch system health');
      }
      return response.json();
    },
    {
      refetchInterval: 30000, // Refresh every 30 seconds
      retry: false,
    }
  );

  const isActivePath = (path: string) => location.pathname === path;

  const getStatusColor = () => {
    if (!health) return 'default';
    const activeServices = Object.values(health.services).filter(Boolean).length;
    if (activeServices === 3) return 'success';
    if (activeServices >= 1) return 'warning';
    return 'error';
  };

  const getStatusText = () => {
    if (!health) return 'Connecting...';
    const activeServices = Object.values(health.services).filter(Boolean).length;
    return `${activeServices}/3 Services`;
  };

  return (
    <AppBar
      position="static"
      elevation={0}
      sx={{
        background: 'rgba(26, 31, 46, 0.95)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
      }}
    >
      <Toolbar sx={{ px: 3 }}>
        {/* Logo and Title */}
        <Box sx={{ display: 'flex', alignItems: 'center', mr: 4 }}>
          <Avatar
            sx={{
              bgcolor: 'primary.main',
              width: 40,
              height: 40,
              mr: 2,
              background: 'linear-gradient(135deg, #64b5f6, #1976d2)',
            }}
          >
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
              🧠
            </Typography>
          </Avatar>
          <Box>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 700,
                background: 'linear-gradient(135deg, #64b5f6, #90caf9)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                lineHeight: 1,
              }}
            >
              Scout
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: 'text.secondary',
                fontSize: '0.7rem',
                lineHeight: 1,
              }}
            >
              Operational Intelligence
            </Typography>
          </Box>
        </Box>

        {/* Navigation Buttons */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mr: 'auto' }}>
          <Button
            variant={isActivePath('/') ? 'contained' : 'text'}
            startIcon={<DashboardIcon />}
            onClick={() => navigate('/')}
            sx={{
              color: isActivePath('/') ? 'white' : 'text.secondary',
              '&:hover': { bgcolor: 'rgba(100, 181, 246, 0.1)' },
            }}
          >
            Dashboard
          </Button>
          <Button
            variant={isActivePath('/search') ? 'contained' : 'text'}
            startIcon={<SearchIcon />}
            onClick={() => navigate('/search')}
            sx={{
              color: isActivePath('/search') ? 'white' : 'text.secondary',
              '&:hover': { bgcolor: 'rgba(100, 181, 246, 0.1)' },
            }}
          >
            Search
          </Button>
          <Button
            variant={isActivePath('/analysis') ? 'contained' : 'text'}
            startIcon={<AnalyticsIcon />}
            onClick={() => navigate('/analysis')}
            sx={{
              color: isActivePath('/analysis') ? 'white' : 'text.secondary',
              '&:hover': { bgcolor: 'rgba(100, 181, 246, 0.1)' },
            }}
          >
            Analysis
          </Button>
          <Button
            variant={isActivePath('/timeline') ? 'contained' : 'text'}
            startIcon={<TimelineIcon />}
            onClick={() => navigate('/timeline')}
            sx={{
              color: isActivePath('/timeline') ? 'white' : 'text.secondary',
              '&:hover': { bgcolor: 'rgba(100, 181, 246, 0.1)' },
            }}
          >
            Timeline
          </Button>
        </Box>

        {/* Status and Actions */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* System Status */}
          <Tooltip title="System Health Status">
            <Chip
              label={getStatusText()}
              color={getStatusColor()}
              size="small"
              variant="outlined"
              sx={{
                borderColor: `${getStatusColor()}.main`,
                color: `${getStatusColor()}.main`,
              }}
            />
          </Tooltip>

          {/* GitHub Link */}
          <Tooltip title="View Scout on GitHub">
            <IconButton
              size="small"
              onClick={() => window.open('https://github.com/yourusername/scout', '_blank')}
              sx={{ color: 'text.secondary' }}
            >
              <GitHubIcon />
            </IconButton>
          </Tooltip>

          {/* Settings */}
          <Tooltip title="System Status">
            <IconButton
              size="small"
              onClick={() => navigate('/status')}
              sx={{
                color: isActivePath('/status') ? 'primary.main' : 'text.secondary',
              }}
            >
              <SettingsIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar; 