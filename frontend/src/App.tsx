import { Box, CssBaseline, ThemeProvider, createTheme } from '@mui/material';
import { QueryClient, QueryClientProvider } from 'react-query';
import CodeAnalysisPanel from './components/CodeAnalysisPanel';

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
          <CodeAnalysisPanel />
        </Box>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App; 