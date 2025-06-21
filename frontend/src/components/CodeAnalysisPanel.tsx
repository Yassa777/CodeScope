import React, { useState, useCallback } from "react";
import {
  Box,
  TextField,
  Button,
  CircularProgress,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  Card,
  CardContent,
  Divider,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Collapse,
} from "@mui/material";
import {
  ExpandMore as ExpandMoreIcon,
  Code as CodeIcon,
  Functions as FunctionIcon,
  Folder as FolderIcon,
  Description as DescriptionIcon,
} from "@mui/icons-material";

interface CodeChunk {
  id: string;
  path: string;
  start_line: number;
  end_line: number;
  ast_type: string;
  content: string;
  parent_symbol?: string;
  docstring?: string;
  hash: string;
}

interface FileSummary {
  path: string;
  summary: string;
  chunks: CodeChunk[];
  functions: CodeChunk[];
  hash: string;
}

interface ModuleSummary {
  path: string;
  summary: string;
  files: FileSummary[];
  submodules: ModuleSummary[];
  hash: string;
}

interface AnalysisResult {
  repository: string;
  total_files: number;
  total_chunks: number;
  modules: ModuleSummary[];
  chunks: CodeChunk[];
}

const API_BASE_URL = 'http://localhost:8000/api';

const CodeAnalysisPanel: React.FC = () => {
  const [repoUrl, setRepoUrl] = useState<string>("");
  const [token, setToken] = useState<string>("");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set());
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [expandedFunctions, setExpandedFunctions] = useState<Set<string>>(new Set());

  const handleAnalyze = useCallback(async () => {
    setError(null);
    if (!repoUrl.trim()) {
      setError("Please enter a GitHub repository URL");
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/repo/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          repo_url: repoUrl.trim(), 
          token: token.trim() || undefined 
        })
      });
      
      if (!response.ok) {
        const err = await response.text();
        throw new Error(err || 'Failed to analyze repository');
      }
      
      const data = await response.json();
      setAnalysis(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [repoUrl, token]);

  const handleModuleToggle = (modulePath: string) => {
    setExpandedModules(prev => {
      const next = new Set(prev);
      if (next.has(modulePath)) {
        next.delete(modulePath);
      } else {
        next.add(modulePath);
      }
      return next;
    });
  };

  const handleFileToggle = (filePath: string) => {
    setExpandedFiles(prev => {
      const next = new Set(prev);
      if (next.has(filePath)) {
        next.delete(filePath);
      } else {
        next.add(filePath);
      }
      return next;
    });
  };

  const handleFunctionToggle = (functionId: string) => {
    setExpandedFunctions(prev => {
      const next = new Set(prev);
      if (next.has(functionId)) {
        next.delete(functionId);
      } else {
        next.add(functionId);
      }
      return next;
    });
  };

  const renderFunction = (func: CodeChunk) => {
    const isExpanded = expandedFunctions.has(func.id);
    
    return (
      <Card key={func.id} sx={{ mb: 1, ml: 2 }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Box display="flex" alignItems="center" gap={1}>
              <FunctionIcon fontSize="small" />
              <Typography variant="subtitle2">
                {func.parent_symbol || func.ast_type}
              </Typography>
              <Chip 
                label={`${func.start_line}-${func.end_line}`} 
                size="small" 
                variant="outlined" 
              />
            </Box>
            <IconButton 
              size="small" 
              onClick={() => handleFunctionToggle(func.id)}
            >
              <ExpandMoreIcon 
                sx={{ 
                  transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s'
                }} 
              />
            </IconButton>
          </Box>
          
          {func.docstring && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {func.docstring}
            </Typography>
          )}
          
          <Collapse in={isExpanded}>
            <Box sx={{ mt: 2 }}>
              <Typography variant="caption" color="text.secondary">
                Code Preview:
              </Typography>
              <Paper 
                sx={{ 
                  p: 1, 
                  mt: 1, 
                  bgcolor: 'grey.50', 
                  fontFamily: 'monospace',
                  fontSize: '0.8rem',
                  maxHeight: 200,
                  overflow: 'auto'
                }}
              >
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                  {func.content}
                </pre>
              </Paper>
            </Box>
          </Collapse>
        </CardContent>
      </Card>
    );
  };

  const renderFile = (file: FileSummary) => {
    const isExpanded = expandedFiles.has(file.path);
    
    return (
      <Accordion 
        key={file.path} 
        expanded={isExpanded}
        onChange={() => handleFileToggle(file.path)}
        sx={{ mb: 1 }}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box display="flex" alignItems="center" gap={1}>
            <DescriptionIcon fontSize="small" />
            <Typography variant="subtitle1">
              {file.path.split('/').pop()}
            </Typography>
            <Chip label={`${file.chunks.length} chunks`} size="small" />
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {file.summary}
          </Typography>
          
          <Typography variant="h6" sx={{ mb: 1 }}>
            Functions ({file.functions.length})
          </Typography>
          
          {file.functions.map(renderFunction)}
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderModule = (module: ModuleSummary) => {
    const isExpanded = expandedModules.has(module.path);
    
    return (
      <Accordion 
        key={module.path} 
        expanded={isExpanded}
        onChange={() => handleModuleToggle(module.path)}
        sx={{ mb: 2 }}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box display="flex" alignItems="center" gap={1}>
            <FolderIcon fontSize="small" />
            <Typography variant="h6">
              {module.path === "root" ? "Root" : module.path}
            </Typography>
            <Chip label={`${module.files.length} files`} size="small" />
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {module.summary}
          </Typography>
          
          {module.files.map(renderFile)}
          
          {module.submodules.map(renderModule)}
        </AccordionDetails>
      </Accordion>
    );
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1200, mx: "auto" }}>
      <Typography variant="h4" gutterBottom>
        Code Analysis
      </Typography>
      
      <Box sx={{ mb: 3 }}>
        <TextField
          label="GitHub repository URL"
          placeholder="https://github.com/facebook/react"
          fullWidth
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          sx={{ mb: 2 }}
        />
        <TextField
          label="GitHub token (optional)"
          type="password"
          fullWidth
          helperText="Needed for private repos or to increase rate limits"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          sx={{ mb: 2 }}
        />
        <Button 
          variant="contained" 
          onClick={handleAnalyze} 
          disabled={loading || !repoUrl.trim()}
          startIcon={loading ? <CircularProgress size={20} /> : <CodeIcon />}
        >
          {loading ? "Analyzing..." : "Analyze Repository"}
        </Button>
      </Box>
      
      {error && (
        <Typography color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}
      
      {analysis && (
        <Box>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h5" gutterBottom>
                Repository Summary
              </Typography>
              <Typography variant="body1">
                <strong>Repository:</strong> {analysis.repository}
              </Typography>
              <Typography variant="body1">
                <strong>Total Files:</strong> {analysis.total_files}
              </Typography>
              <Typography variant="body1">
                <strong>Total Chunks:</strong> {analysis.total_chunks}
              </Typography>
            </CardContent>
          </Card>
          
          <Typography variant="h5" gutterBottom>
            Module Structure
          </Typography>
          
          {analysis.modules.map(renderModule)}
        </Box>
      )}
    </Box>
  );
};

export default CodeAnalysisPanel; 