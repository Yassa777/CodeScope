import React, { useState, useEffect, useRef } from 'react';
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
  Button,
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
  data?: {
    size: number;
    hash: string;
  };
}

interface FolderData {
  folders: Record<string, FolderData>;
  files: Array<{
    path: string;
    hash: string;
    size: number;
  }>;
}

interface RepoStructure {
  id: string;
  name: string;
  url: string;
  branch: string;
  folders: Record<string, FolderData>;
  files: Array<{
    path: string;
    hash: string;
    size: number;
  }>;
}

interface AnalysisStatus {
  status: 'processing' | 'completed' | 'error';
  progress: number;
  error: string | null;
  message?: string;
  structure?: RepoStructure;
  graph?: any;
  started_at?: string;
  completed_at?: string;
}

interface TreeNode {
  id: string;
  name: string;
  type: 'file' | 'folder';
  children?: TreeNode[];
  data?: {
    size: number;
    hash: string;
  };
}

interface FileTreePanelProps {
  onRepoIdChange: (repoId: string | null) => void;
}

const API_BASE_URL = 'http://localhost:8000/api';
const WS_BASE_URL = 'ws://localhost:8000/ws';

const FileTreePanel: React.FC<FileTreePanelProps> = ({ onRepoIdChange }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [repoId, setRepoId] = useState<string | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus | null>(null);
  const [wsError, setWsError] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 5;
  const setSelectedNode = useStore((state) => state.setSelectedNode);

  // Update parent component when repoId changes
  useEffect(() => {
    onRepoIdChange(repoId);
  }, [repoId, onRepoIdChange]);

  // Set up WebSocket connection
  useEffect(() => {
    if (repoId) {
      // Clear any existing reconnection timeout
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      // Close existing connection
      if (wsRef.current) {
        wsRef.current.close();
      }

      const connectWebSocket = () => {
        try {
          // Create new WebSocket connection
          const ws = new WebSocket(`${WS_BASE_URL}/repo/${repoId}`);
          wsRef.current = ws;

          ws.onopen = () => {
            console.log('WebSocket connected');
            setWsError(null);
            setWsConnected(true);
            reconnectAttemptsRef.current = 0;
          };

          ws.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              setAnalysisStatus(data);
              setWsError(null);
            } catch (error) {
              console.error('Error parsing WebSocket message:', error);
              setWsError('Error processing server update');
            }
          };

          ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            setWsError('Connection error');
            setWsConnected(false);
          };

          ws.onclose = (event) => {
            console.log('WebSocket connection closed:', event.code, event.reason);
            wsRef.current = null;
            setWsConnected(false);

            // Attempt to reconnect if not a normal closure and haven't exceeded max attempts
            if (event.code !== 1000 && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
              reconnectAttemptsRef.current += 1;
              setWsError(`Connection lost. Reconnecting... (Attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`);
              reconnectTimeoutRef.current = window.setTimeout(() => {
                connectWebSocket();
              }, 3000); // Try to reconnect after 3 seconds
            } else if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
              setWsError('Failed to establish connection after multiple attempts. Please refresh the page.');
            }
          };
        } catch (error) {
          console.error('Error creating WebSocket:', error);
          setWsError('Failed to establish connection');
          setWsConnected(false);
        }
      };

      connectWebSocket();

      return () => {
        if (reconnectTimeoutRef.current) {
          window.clearTimeout(reconnectTimeoutRef.current);
        }
        if (wsRef.current) {
          wsRef.current.close();
        }
      };
    }
  }, [repoId]);

  // Query for repository structure
  const { data: repoStructure, isLoading, error: repoError } = useQuery<AnalysisStatus>(
    ['repo', repoId],
    async () => {
      if (!repoId) return null;
      const response = await fetch(`${API_BASE_URL}/repo/${repoId}`);
      if (!response.ok) {
        const error = await response.text();
        throw new Error(error || 'Failed to fetch repository structure');
      }
      const data = await response.json();
      console.log('Received repository structure:', data);
      return data;
    },
    {
      enabled: !!repoId,
      refetchInterval: (data) => {
        // Only refetch if the analysis is still processing
        return data?.status === 'processing' ? 2000 : false;
      },
      retry: (failureCount, error) => {
        // Don't retry if the analysis is not found (404)
        if (error instanceof Error && error.message.includes('Analysis not found')) {
          return false;
        }
        return failureCount < 3;
      },
    }
  );

  // Update analysis status from query data if available
  useEffect(() => {
    if (repoStructure) {
      console.log('Setting analysis status with structure:', repoStructure);
      setAnalysisStatus(repoStructure);
    }
  }, [repoStructure]);

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
          <ListItemText 
            primary={node.name}
            secondary={!isFolder && node.data?.size ? formatFileSize(node.data.size) : undefined}
          />
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

  // Helper function to format file size
  const formatFileSize = (bytes: number): string => {
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }

    return `${size.toFixed(1)} ${units[unitIndex]}`;
  };

  // Convert repository structure to tree nodes
  const convertToTreeNodes = (structure: RepoStructure | undefined): TreeNode[] => {
    if (!structure) {
      return [];
    }
    const allFiles = structure.files || [];

    // Recursive function to process a folder
    const processFolder = (folderData: Record<string, FolderData>, parentPath: string): TreeNode[] => {
      return Object.entries(folderData).map(([name, data]) => {
        const currentPath = parentPath ? `${parentPath}/${name}` : name;

        // Get files that are direct children of this folder
        const childFiles = allFiles
          .filter(file => {
            const filePath = file.path;
            const lastSlashIndex = filePath.lastIndexOf('/');
            const parentDir = lastSlashIndex === -1 ? '' : filePath.substring(0, lastSlashIndex);
            return parentDir === currentPath;
          })
          .map(file => ({
            id: file.path,
            name: file.path.split('/').pop() || file.path,
            type: 'file' as const,
            data: { size: file.size, hash: file.hash },
          }));

        // Recursively process subfolders
        const childFolders = processFolder(data.folders, currentPath);

        return {
          id: currentPath,
          name: name,
          type: 'folder' as const,
          children: [...childFolders, ...childFiles].sort((a, b) => {
            // Sort so folders come before files
            if (a.type === 'folder' && b.type === 'file') return -1;
            if (a.type === 'file' && b.type === 'folder') return 1;
            return a.name.localeCompare(b.name);
          }),
        };
      });
    };

    // Process root-level folders
    const rootFolders = processFolder(structure.folders, '');

    // Process root-level files
    const rootFiles = allFiles
      .filter(file => !file.path.includes('/'))
      .map(file => ({
        id: file.path,
        name: file.path.split('/').pop() || file.path,
        type: 'file' as const,
        data: { size: file.size, hash: file.hash },
      }));

    return [...rootFolders, ...rootFiles].sort((a, b) => {
        if (a.type === 'folder' && b.type === 'file') return -1;
        if (a.type === 'file' && b.type === 'folder') return 1;
        return a.name.localeCompare(b.name);
    });
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <RepoInput onAnalysisComplete={setRepoId} />
      
      {wsError && (
        <Box sx={{ p: 2 }}>
          <Alert 
            severity="error" 
            onClose={() => setWsError(null)}
            action={
              reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS && (
                <Button color="inherit" size="small" onClick={() => window.location.reload()}>
                  Refresh
                </Button>
              )
            }
          >
            {wsError}
          </Alert>
        </Box>
      )}

      {!wsConnected && !wsError && (
        <Box sx={{ p: 2 }}>
          <Alert severity="info">
            Connecting to server...
          </Alert>
        </Box>
      )}

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
          <LinearProgress 
            variant="determinate" 
            value={analysisStatus.progress} 
            sx={{ height: 8, borderRadius: 4 }}
          />
          <Box sx={{ mt: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              {analysisStatus.message || 'Analyzing repository...'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {Math.round(analysisStatus.progress)}%
            </Typography>
          </Box>
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
        {analysisStatus?.structure ? (
          <List>
            {convertToTreeNodes(analysisStatus.structure).map(node => renderNode(node))}
          </List>
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