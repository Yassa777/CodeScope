import React, { useState, useEffect } from 'react';
import {
  Box,
  TextField,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Collapse,
  IconButton,
  Typography,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  Folder as FolderIcon,
  FolderOpen as FolderOpenIcon,
  InsertDriveFile as FileIcon,
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import { useStore } from '../store';
import RepoInput from './RepoInput';
import { useQuery } from 'react-query';

interface FileNode {
  id: string;
  name: string;
  type: 'folder' | 'file';
  children?: FileNode[];
}

const FileTreePanel: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [repoId, setRepoId] = useState<string | null>(null);
  const setSelectedNode = useStore((state) => state.setSelectedNode);

  // Query for repository structure
  const { data: repoStructure, isLoading, error: repoError } = useQuery(
    ['repo', repoId],
    async () => {
      if (!repoId) return null;
      const response = await fetch(`/api/repo/${repoId}/graph?level=1`);
      if (!response.ok) throw new Error('Failed to fetch repository structure');
      return response.json();
    },
    {
      enabled: !!repoId,
      refetchInterval: (data) => (data?.status === 'processing' ? 1000 : false),
    }
  );

  // Query for analysis status
  const { data: analysisStatus } = useQuery(
    ['repo-status', repoId],
    async () => {
      if (!repoId) return null;
      const response = await fetch(`/api/repo/${repoId}/status`);
      if (!response.ok) throw new Error('Failed to fetch analysis status');
      return response.json();
    },
    {
      enabled: !!repoId,
      refetchInterval: (data) => (data?.status === 'processing' ? 1000 : false),
    }
  );

  const handleFolderClick = (folderId: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        next.delete(folderId);
      } else {
        next.add(folderId);
      }
      return next;
    });
  };

  const handleNodeClick = (node: FileNode) => {
    setSelectedNode({
      id: node.id,
      type: node.type,
      name: node.name,
    });
  };

  const renderNode = (node: FileNode, level: number = 0) => {
    if (!node || !node.id) return null;

    const isExpanded = expandedFolders.has(node.id);
    const isFolder = node.type === 'folder';

    return (
      <React.Fragment key={node.id}>
        <ListItem
          button
          onClick={() => (isFolder ? handleFolderClick(node.id) : handleNodeClick(node))}
          sx={{ pl: level * 2 }}
        >
          <ListItemIcon>
            {isFolder ? (
              isExpanded ? (
                <FolderOpenIcon color="primary" />
              ) : (
                <FolderIcon color="primary" />
              )
            ) : (
              <FileIcon />
            )}
          </ListItemIcon>
          <ListItemText primary={node.name} />
          {isFolder && (
            <IconButton size="small">
              {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          )}
        </ListItem>
        {isFolder && node.children && (
          <Collapse in={isExpanded} timeout="auto" unmountOnExit>
            <List component="div" disablePadding>
              {node.children.map((child) => renderNode(child, level + 1))}
            </List>
          </Collapse>
        )}
      </React.Fragment>
    );
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <RepoInput onAnalysisComplete={setRepoId} />
      
      {isLoading && (
        <Box sx={{ p: 2 }}>
          <LinearProgress />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
            Loading repository structure...
          </Typography>
        </Box>
      )}

      {repoError instanceof Error && (
        <Box sx={{ p: 2 }}>
          <Alert severity="error">
            Failed to load repository structure: {repoError.message}
          </Alert>
        </Box>
      )}

      {analysisStatus?.status === 'processing' && (
        <Box sx={{ p: 2 }}>
          <LinearProgress variant="determinate" value={analysisStatus.progress * 100} />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
            {analysisStatus.message}
          </Typography>
        </Box>
      )}

      <Box sx={{ p: 2 }}>
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Search files..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
          }}
          size="small"
        />
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {repoStructure?.nodes && repoStructure.nodes.length > 0 ? (
          <List>{renderNode(repoStructure.nodes[0])}</List>
        ) : (
          <Box sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Enter a GitHub repository URL to begin
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default FileTreePanel; 