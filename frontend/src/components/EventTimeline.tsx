import React from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Chip,
  Avatar,
  IconButton,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Button,
  Grid,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  GitHub as GitHubIcon,
  TaskAlt as TaskIcon,
  MergeType as MergeIcon,
  BugReport as BugIcon,
  Security as SecurityIcon,
  Warning as WarningIcon,
  Code as CodeIcon,
  Person as PersonIcon,
  FilterList as FilterIcon,
  Refresh as RefreshIcon,
  Link as LinkIcon,
} from '@mui/icons-material';
import { useQuery } from 'react-query';
import { useState } from 'react';

const API_BASE_URL = 'http://localhost:8000';

interface ScoutEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  who: string;
  what: string;
  linked_to?: string;
  repository?: string;
  project?: string;
  severity: string;
  metadata: Record<string, any>;
  enrichments: Record<string, any>;
}

const EventTimeline: React.FC = () => {
  const [repository, setRepository] = useState<string>('');
  const [eventTypes, setEventTypes] = useState<string>('');
  const [limit, setLimit] = useState<number>(50);

  const { data: events, isLoading, error, refetch } = useQuery<{ events: ScoutEvent[] }>(
    ['scout-events', repository, eventTypes, limit],
    async () => {
      const params = new URLSearchParams();
      params.append('limit', limit.toString());
      
      if (repository) params.append('repository', repository);
      if (eventTypes) params.append('event_types', eventTypes);
      
      const response = await fetch(`${API_BASE_URL}/events?${params}`);
      if (!response.ok) throw new Error('Failed to fetch events');
      return response.json();
    },
    { refetchInterval: 30000 }
  );

  const getEventIcon = (eventType: string) => {
    if (eventType.includes('github.pr')) return <MergeIcon />;
    if (eventType.includes('github.push')) return <CodeIcon />;
    if (eventType.includes('asana.task')) return <TaskIcon />;
    if (eventType.includes('system.alert')) return <WarningIcon />;
    return <GitHubIcon />;
  };

  const getEventColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'error';
      case 'high': return 'warning';
      case 'medium': return 'info';
      case 'low': return 'success';
      default: return 'primary';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical': return <BugIcon />;
      case 'high': return <SecurityIcon />;
      case 'medium': return <WarningIcon />;
      default: return null;
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const getRepositoryShortName = (repo?: string) => {
    if (!repo) return '';
    return repo.split('/').pop() || repo;
  };

  const renderEventMetadata = (event: ScoutEvent) => {
    const metadata = event.metadata;
    const badges = [];

    if (metadata.pr_number) {
      badges.push(
        <Chip
          key="pr"
          label={`PR #${metadata.pr_number}`}
          size="small"
          variant="outlined"
          color="primary"
        />
      );
    }

    if (metadata.commit_count && metadata.commit_count > 1) {
      badges.push(
        <Chip
          key="commits"
          label={`${metadata.commit_count} commits`}
          size="small"
          variant="outlined"
        />
      );
    }

    if (metadata.files_changed) {
      badges.push(
        <Chip
          key="files"
          label={`${metadata.files_changed} files`}
          size="small"
          variant="outlined"
        />
      );
    }

    if (event.linked_to) {
      badges.push(
        <Chip
          key="linked"
          label="Linked"
          size="small"
          variant="outlined"
          color="secondary"
          icon={<LinkIcon />}
        />
      );
    }

    return badges;
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 4 }}>
        <Box>
          <Typography variant="h3" sx={{ mb: 1 }}>
            🧠 Scout Timeline
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Operational intelligence from GitHub and Asana activity
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={() => refetch()}
        >
          Refresh
        </Button>
      </Box>

      {/* Filters */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
            <FilterIcon sx={{ mr: 1 }} />
            Filters
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                label="Repository"
                value={repository}
                onChange={(e) => setRepository(e.target.value)}
                placeholder="e.g., owner/repo"
                variant="outlined"
                size="small"
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControl fullWidth size="small">
                <InputLabel>Event Types</InputLabel>
                <Select
                  value={eventTypes}
                  label="Event Types"
                  onChange={(e) => setEventTypes(e.target.value as string)}
                >
                  <MenuItem value="">All Events</MenuItem>
                  <MenuItem value="github.pr.opened,github.pr.merged">PR Activity</MenuItem>
                  <MenuItem value="github.push">Push Events</MenuItem>
                  <MenuItem value="asana.task.updated,asana.task.completed">Task Activity</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                type="number"
                label="Limit"
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value) || 50)}
                variant="outlined"
                size="small"
                inputProps={{ min: 10, max: 500 }}
              />
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Loading State */}
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Error State */}
      {error && (
        <Alert severity="error" sx={{ mb: 4 }}>
          Failed to load events: {error instanceof Error ? error.message : 'Unknown error'}
        </Alert>
      )}

      {/* Events List */}
      {events && events.events && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {events.events.map((event, index) => (
            <Card
              key={event.event_id}
              sx={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                position: 'relative',
                '&::before': {
                  content: '""',
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  bottom: 0,
                  width: 4,
                  bgcolor: `${getEventColor(event.severity)}.main`,
                }
              }}
            >
              <CardContent sx={{ p: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                  {/* Event Icon */}
                  <Avatar 
                    sx={{ 
                      bgcolor: `${getEventColor(event.severity)}.main`,
                      color: 'white',
                      width: 40,
                      height: 40
                    }}
                  >
                    {getEventIcon(event.event_type)}
                  </Avatar>
                  
                  {/* Event Details */}
                  <Box sx={{ flex: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="h6" sx={{ fontWeight: 'medium', flex: 1 }}>
                        {event.what}
                      </Typography>
                      {getSeverityIcon(event.severity) && (
                        <Box sx={{ color: `${getEventColor(event.severity)}.main`, ml: 1 }}>
                          {getSeverityIcon(event.severity)}
                        </Box>
                      )}
                    </Box>
                    
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        {event.event_type.replace(/\./g, ' • ')}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        by {event.who}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {formatTimestamp(event.timestamp)}
                      </Typography>
                    </Box>
                    
                    {/* Repository */}
                    {event.repository && (
                      <Box sx={{ mb: 2 }}>
                        <Chip
                          label={event.repository}
                          size="small"
                          variant="outlined"
                          color="primary"
                        />
                      </Box>
                    )}
                    
                    {/* Metadata badges */}
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                      {renderEventMetadata(event)}
                    </Box>
                    
                    {/* Enrichments */}
                    {event.enrichments && Object.keys(event.enrichments).length > 0 && (
                      <Box sx={{ mt: 1, p: 1, bgcolor: 'rgba(255, 255, 255, 0.05)', borderRadius: 1 }}>
                        <Typography variant="caption" color="text.secondary">
                          Enrichments: {Object.keys(event.enrichments).join(', ')}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}

      {/* Empty State */}
      {events && events.events && events.events.length === 0 && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>
            No events found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Try adjusting your filters or check back later for new activity
          </Typography>
        </Box>
      )}
    </Container>
  );
};

export default EventTimeline; 