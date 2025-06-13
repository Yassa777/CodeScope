import React from 'react';
import {
  Box,
  Typography,
  Paper,
  Divider,
  List,
  ListItem,
  ListItemText,
  Chip,
} from '@mui/material';
import { useStore } from '../store';

const InspectorPanel: React.FC = () => {
  const selectedNode = useStore((state) => state.selectedNode);

  if (!selectedNode) {
    return null;
  }

  const renderNodeDetails = () => {
    switch (selectedNode.type) {
      case 'folder':
        return (
          <>
            <Typography variant="h6" gutterBottom>
              Folder Details
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Path: {selectedNode.id}
            </Typography>
          </>
        );

      case 'file':
        return (
          <>
            <Typography variant="h6" gutterBottom>
              File Details
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Path: {selectedNode.id}
            </Typography>
            {selectedNode.data?.size && (
              <Typography variant="body2" color="text.secondary">
                Size: {formatFileSize(selectedNode.data.size)}
              </Typography>
            )}
          </>
        );

      case 'function':
        return (
          <>
            <Typography variant="h6" gutterBottom>
              Function Details
            </Typography>
            {selectedNode.data?.summary && (
              <Paper sx={{ p: 2, mb: 2, bgcolor: 'background.paper' }}>
                <Typography variant="body2">
                  {selectedNode.data.summary}
                </Typography>
              </Paper>
            )}
            {selectedNode.data?.parameters && (
              <>
                <Typography variant="subtitle2" gutterBottom>
                  Parameters
                </Typography>
                <List dense>
                  {selectedNode.data.parameters.map((param: string, index: number) => (
                    <ListItem key={index}>
                      <ListItemText primary={param} />
                    </ListItem>
                  ))}
                </List>
              </>
            )}
            {selectedNode.data?.returns && (
              <>
                <Typography variant="subtitle2" gutterBottom>
                  Returns
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {selectedNode.data.returns}
                </Typography>
              </>
            )}
            {selectedNode.data?.dependencies && selectedNode.data.dependencies.length > 0 && (
              <>
                <Typography variant="subtitle2" gutterBottom>
                  Dependencies
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {selectedNode.data.dependencies.map((dep: string, index: number) => (
                    <Chip key={index} label={dep} size="small" />
                  ))}
                </Box>
              </>
            )}
          </>
        );

      default:
        return (
          <Typography variant="body2" color="text.secondary">
            No details available
          </Typography>
        );
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6" noWrap>
          {selectedNode.name}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {selectedNode.type}
        </Typography>
      </Box>
      <Box sx={{ p: 2, flex: 1, overflow: 'auto' }}>
        {renderNodeDetails()}
      </Box>
    </Box>
  );
};

function formatFileSize(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

export default InspectorPanel; 