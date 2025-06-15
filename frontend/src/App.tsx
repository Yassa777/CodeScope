import { Box, CssBaseline, ThemeProvider, createTheme } from '@mui/material';
import { QueryClient, QueryClientProvider } from 'react-query';
import FileTreePanel from './components/FileTreePanel';
import GraphPanel from './components/GraphPanel';
import InspectorPanel from './components/InspectorPanel';
import { useStore } from './store';
import { useState } from 'react';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#f48fb1',
    },
    background: {
      default: '#121212',
      paper: '#1e1e1e',
    },
  },
});

const queryClient = new QueryClient();

function App() {
  const selectedNode = useStore((state) => state.selectedNode);
  const graphLevel = useStore((state) => state.graphLevel);
  const [repoId, setRepoId] = useState<string | null>(null);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box
          sx={{
            display: 'flex',
            height: '100vh',
            width: '100vw',
            overflow: 'hidden',
          }}
        >
          {/* Left Panel - File Tree */}
          <Box
            sx={{
              width: '300px',
              borderRight: 1,
              borderColor: 'divider',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <FileTreePanel onRepoIdChange={setRepoId} />
          </Box>

          {/* Center Panel - Graph */}
          <Box
            sx={{
              flex: 1,
              position: 'relative',
              backgroundColor: 'background.default',
            }}
          >
            <GraphPanel level={graphLevel} repoId={repoId} />
          </Box>

          {/* Right Panel - Inspector */}
          <Box
            sx={{
              width: '400px',
              borderLeft: 1,
              borderColor: 'divider',
              display: 'flex',
              flexDirection: 'column',
              visibility: selectedNode ? 'visible' : 'hidden',
            }}
          >
            <InspectorPanel />
          </Box>
        </Box>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App; 