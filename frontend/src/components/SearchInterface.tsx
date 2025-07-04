import React, { useState, useCallback } from 'react';
import {
  Box,
  Container,
  Typography,
  TextField,
  Button,
  Grid,
  Card,
  CardContent,
  Chip,
  IconButton,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Slider,
  Switch,
  FormControlLabel,
  CircularProgress,
  Alert,
  Paper,
  List,
  ListItem,
  ListItemText,
  Divider,
  Tabs,
  Tab,
  Badge,
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Code as CodeIcon,
  Psychology as AIIcon,
  Speed as SpeedIcon,
  ExpandMore as ExpandMoreIcon,
  ContentCopy as CopyIcon,
  OpenInNew as OpenIcon,
} from '@mui/icons-material';
import { useQuery } from 'react-query';

const API_BASE_URL = 'http://localhost:8000';

interface SearchResult {
  chunk_id: string;
  content: string;
  file_path: string;
  start_line: number;
  end_line: number;
  ast_type: string;
  parent_symbol?: string;
  score: number;
  search_type: string;
}

interface SearchFilters {
  language?: string;
  fileType?: string;
  astType?: string;
  minScore?: number;
}

const SearchInterface: React.FC = () => {
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<'lexical' | 'semantic' | 'hybrid'>('hybrid');
  const [filters, setFilters] = useState<SearchFilters>({});
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [limit, setLimit] = useState(20);
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const endpoint = searchType === 'hybrid' 
        ? '/search/hybrid'
        : `/search/${searchType}`;
      
      const body: any = {
        query: query.trim(),
        limit,
        ...filters,
      };

      if (searchType === 'hybrid') {
        body.lexical_weight = 0.3;
        body.semantic_weight = 0.7;
      } else if (searchType === 'semantic') {
        body.score_threshold = filters.minScore || 0.7;
      } else if (searchType === 'lexical') {
        body.search_type = 'bm25';
      }

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error('Search failed');
      }

      const data = await response.json();
      setResults(data.results || data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [query, searchType, filters, limit]);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const getSearchTypeColor = (type: string) => {
    switch (type) {
      case 'semantic': return 'primary';
      case 'lexical': return 'success';
      case 'hybrid': return 'secondary';
      default: return 'default';
    }
  };

  const getAstTypeIcon = (astType: string) => {
    if (astType.includes('function')) return '🔧';
    if (astType.includes('class')) return '🏗️';
    if (astType.includes('import')) return '📦';
    if (astType.includes('comment')) return '💬';
    return '📄';
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h3" sx={{ mb: 2 }}>
          Code Search
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Search your codebase using AI-powered semantic understanding or fast lexical matching
        </Typography>
      </Box>

      {/* Search Interface */}
      <Grid container spacing={4}>
        {/* Search Panel */}
        <Grid item xs={12} lg={8}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              {/* Search Type Tabs */}
              <Tabs
                value={searchType}
                onChange={(_, value) => setSearchType(value)}
                sx={{ mb: 3 }}
              >
                <Tab
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <AIIcon fontSize="small" />
                      Hybrid
                    </Box>
                  }
                  value="hybrid"
                />
                <Tab
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <AIIcon fontSize="small" />
                      Semantic
                    </Box>
                  }
                  value="semantic"
                />
                <Tab
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <SpeedIcon fontSize="small" />
                      Lexical
                    </Box>
                  }
                  value="lexical"
                />
              </Tabs>

              {/* Search Input */}
              <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                <TextField
                  fullWidth
                  placeholder={
                    searchType === 'semantic'
                      ? 'Describe the code you are looking for...'
                      : searchType === 'lexical'
                      ? 'Enter keywords to search...'
                      : 'Search using natural language or keywords...'
                  }
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyPress={handleKeyPress}
                  variant="outlined"
                  size="large"
                  InputProps={{
                    endAdornment: (
                      <IconButton onClick={() => setShowFilters(!showFilters)}>
                        <FilterIcon />
                      </IconButton>
                    ),
                  }}
                />
                <Button
                  variant="contained"
                  size="large"
                  onClick={handleSearch}
                  disabled={loading || !query.trim()}
                  sx={{ minWidth: 120 }}
                >
                  {loading ? <CircularProgress size={24} /> : <SearchIcon />}
                </Button>
              </Box>

              {/* Search Description */}
              <Typography variant="body2" color="text.secondary">
                {searchType === 'semantic' && 
                  '🧠 AI-powered search that understands code meaning and context'}
                {searchType === 'lexical' && 
                  '⚡ Fast text-based search using BM25 ranking'}
                {searchType === 'hybrid' && 
                  '🚀 Best of both worlds: AI understanding + fast text matching'}
              </Typography>

              {/* Filters */}
              {showFilters && (
                <Accordion sx={{ mt: 2 }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography>Search Filters</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6} md={3}>
                        <FormControl fullWidth size="small">
                          <InputLabel>File Type</InputLabel>
                          <Select
                            value={filters.fileType || ''}
                            onChange={(e) => setFilters(prev => ({ ...prev, fileType: e.target.value }))}
                          >
                            <MenuItem value="">All</MenuItem>
                            <MenuItem value=".py">Python</MenuItem>
                            <MenuItem value=".js">JavaScript</MenuItem>
                            <MenuItem value=".ts">TypeScript</MenuItem>
                            <MenuItem value=".tsx">TSX</MenuItem>
                          </Select>
                        </FormControl>
                      </Grid>
                      <Grid item xs={12} sm={6} md={3}>
                        <FormControl fullWidth size="small">
                          <InputLabel>AST Type</InputLabel>
                          <Select
                            value={filters.astType || ''}
                            onChange={(e) => setFilters(prev => ({ ...prev, astType: e.target.value }))}
                          >
                            <MenuItem value="">All</MenuItem>
                            <MenuItem value="function_definition">Functions</MenuItem>
                            <MenuItem value="class_definition">Classes</MenuItem>
                            <MenuItem value="import_statement">Imports</MenuItem>
                          </Select>
                        </FormControl>
                      </Grid>
                      <Grid item xs={12} sm={6} md={3}>
                        <Typography variant="body2" sx={{ mb: 1 }}>
                          Results Limit: {limit}
                        </Typography>
                        <Slider
                          value={limit}
                          onChange={(_, value) => setLimit(value as number)}
                          min={5}
                          max={50}
                          step={5}
                          size="small"
                        />
                      </Grid>
                      {searchType === 'semantic' && (
                        <Grid item xs={12} sm={6} md={3}>
                          <Typography variant="body2" sx={{ mb: 1 }}>
                            Min Score: {filters.minScore || 0.7}
                          </Typography>
                          <Slider
                            value={filters.minScore || 0.7}
                            onChange={(_, value) => setFilters(prev => ({ ...prev, minScore: value as number }))}
                            min={0.1}
                            max={1.0}
                            step={0.1}
                            size="small"
                          />
                        </Grid>
                      )}
                    </Grid>
                  </AccordionDetails>
                </Accordion>
              )}
            </CardContent>
          </Card>

          {/* Error Display */}
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          {/* Results */}
          <Box>
            {results.length > 0 && (
              <Typography variant="h6" sx={{ mb: 2 }}>
                Found {results.length} results
              </Typography>
            )}
            
            {results.map((result, index) => (
              <Card
                key={index}
                sx={{
                  mb: 2,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  '&:hover': {
                    transform: 'translateY(-1px)',
                    boxShadow: 2,
                  },
                }}
                onClick={() => setSelectedResult(result)}
              >
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                    <Typography variant="h6" sx={{ fontSize: '1.5rem' }}>
                      {getAstTypeIcon(result.ast_type)}
                    </Typography>
                    <Box sx={{ flexGrow: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <Typography variant="h6" sx={{ fontSize: '1rem' }}>
                          {result.parent_symbol || result.ast_type}
                        </Typography>
                        <Chip
                          label={`Score: ${result.score.toFixed(2)}`}
                          size="small"
                          color={getSearchTypeColor(result.search_type)}
                          variant="outlined"
                        />
                        <Chip
                          label={`${result.start_line}-${result.end_line}`}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        {result.file_path}
                      </Typography>
                      <Paper
                        sx={{
                          p: 2,
                          bgcolor: 'grey.900',
                          fontFamily: 'monospace',
                          fontSize: '0.85rem',
                          maxHeight: 200,
                          overflow: 'auto',
                        }}
                      >
                        <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                          {result.content.substring(0, 300)}
                          {result.content.length > 300 && '...'}
                        </pre>
                      </Paper>
                    </Box>
                    <Box>
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          copyToClipboard(result.content);
                        }}
                      >
                        <CopyIcon />
                      </IconButton>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            ))}
          </Box>
        </Grid>

        {/* Side Panel */}
        <Grid item xs={12} lg={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Search Tips
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText
                    primary="Semantic Search"
                    secondary="Try: 'functions that handle user authentication'"
                  />
                </ListItem>
                <Divider />
                <ListItem>
                  <ListItemText
                    primary="Lexical Search"
                    secondary="Try: 'async def login' or 'class UserManager'"
                  />
                </ListItem>
                <Divider />
                <ListItem>
                  <ListItemText
                    primary="Hybrid Search"
                    secondary="Combines both approaches for best results"
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

export default SearchInterface;
