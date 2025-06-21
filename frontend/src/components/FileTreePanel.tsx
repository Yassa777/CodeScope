import React, { useState, useCallback } from "react";
import { Box, TextField, Button, CircularProgress, Typography } from "@mui/material";
import { SimpleTreeView } from '@mui/x-tree-view';
import { TreeItem } from '@mui/x-tree-view';

// Basic file / directory node type
interface TreeNode {
  id: string;
  name: string;
  path: string;
  type: "blob" | "tree";
  children?: TreeNode[];
}

function parseRepoUrl(url: string): { owner: string; repo: string } | null {
  try {
    const u = new URL(url);
    if (u.hostname !== "github.com") return null;
    const [owner, repo] = u.pathname.replace(/^\//, "").split("/").slice(0, 2);
    if (!owner || !repo) return null;
    return { owner, repo: repo.replace(/\.git$/, "") };
  } catch {
    return null;
  }
}

const API_BASE_URL = 'http://localhost:8000/api';

const FileTreePanel: React.FC = () => {
  const [repoUrl, setRepoUrl] = useState<string>("");
  const [token, setToken] = useState<string>("");
  const [nodes, setNodes] = useState<TreeNode[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = useCallback(async () => {
    setError(null);
    const parsed = parseRepoUrl(repoUrl.trim());
    if (!parsed) {
      setError("Please enter a valid GitHub repository URL");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/repo/tree`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl.trim(), token: token.trim() || undefined })
      });
      if (!response.ok) {
        const err = await response.text();
        throw new Error(err || 'Failed to fetch repository tree');
      }
      const data = await response.json();
      setNodes(data.tree);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [repoUrl, token]);

  const renderTree = (node: TreeNode) => (
    <TreeItem key={node.id} itemId={node.id} label={node.name}>
      {node.children?.map(renderTree)}
    </TreeItem>
  );

  return (
    <Box display="flex" flexDirection="column" gap={2} p={2} maxWidth={600} mx="auto">
      <Typography variant="h5" fontWeight="bold">
        GitHub Repository File Tree
      </Typography>
      <TextField
        label="GitHub repository URL"
        placeholder="https://github.com/facebook/react"
        fullWidth
        value={repoUrl}
        onChange={(e) => setRepoUrl(e.target.value)}
      />
      <TextField
        label="GitHub token (optional)"
        type="password"
        fullWidth
        helperText="Needed for private repos or to increase rate limits"
        value={token}
        onChange={(e) => setToken(e.target.value)}
      />
      <Button variant="contained" onClick={handleLoad} disabled={loading || !repoUrl.trim()}>
        Load tree
      </Button>
      {loading && <CircularProgress />}
      {error && <Typography color="error">{error}</Typography>}
      {nodes && (
        <SimpleTreeView
          sx={{ flexGrow: 1, overflowY: "auto", border: "1px solid #ccc", borderRadius: 2, p: 1 }}
        >
          {nodes.map(renderTree)}
        </SimpleTreeView>
      )}
    </Box>
  );
};

export default FileTreePanel; 