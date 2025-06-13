import React, { useState } from 'react';
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

interface FileNode {
  id: string;
  name: string;
  type: 'folder' | 'file';
  children?: FileNode[];
}

const FileTreePanel: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const setSelectedNode = useStore((state) => state.setSelectedNode);

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

  // TODO: Replace with actual repository data
  const mockData: FileNode = {
    id: 'root',
    name: 'Repository',
    type: 'folder',
    children: [
      {
        id: 'src',
        name: 'src',
        type: 'folder',
        children: [
          {
            id: 'src/main.ts',
            name: 'main.ts',
            type: 'file',
          },
        ],
      },
    ],
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Repository Explorer
        </Typography>
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
        <List>{renderNode(mockData)}</List>
      </Box>
    </Box>
  );
};

export default FileTreePanel; 