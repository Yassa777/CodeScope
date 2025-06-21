import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { Box, Typography, useTheme } from '@mui/material';
import { useStore } from '../store';
import { useQuery } from 'react-query';

// Define interfaces for our graph data
interface GraphNode extends d3.SimulationNodeDatum {
  id: string; // File path
  type: 'file';
  name: string; // File name
  data?: Record<string, any>;
}

interface GraphEdge extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode; // Can be ID or Node object
  target: string | GraphNode; // Can be ID or Node object
  type: 'imports';
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface GraphPanelProps {
  level: number;
  repoId: string | null;
}

const API_BASE_URL = 'http://localhost:8000/api';

const GraphPanel: React.FC<GraphPanelProps> = ({ level, repoId }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const setSelectedNode = useStore((state) => state.setSelectedNode);
  const selectedNode = useStore((state) => state.selectedNode);
  const theme = useTheme();

  // Fetch graph data from the new endpoint
  const { data: graphData, isLoading } = useQuery<GraphData>(
    ['graph', repoId],
    async () => {
      if (!repoId) return { nodes: [], edges: [] };
      const response = await fetch(`${API_BASE_URL}/repo/${repoId}/graph`);
      if (!response.ok) {
        throw new Error('Failed to fetch graph data');
      }
      const data: GraphData = await response.json();
      console.log('Received graph data:', data);
      
      // Ensure nodes have default positions for the simulation
      data.nodes.forEach(node => {
        node.x = 0;
        node.y = 0;
      });
      
      return data;
    },
    {
      enabled: !!repoId,
      // Poll for data if the graph is empty, as analysis is likely ongoing
      refetchInterval: (data) => {
        return (!data || data.nodes.length === 0) ? 3000 : false;
      },
    }
  );

  useEffect(() => {
    if (!svgRef.current || !graphData || !graphData.nodes) {
      d3.select(svgRef.current).selectAll('*').remove();
      return;
    }

    // Clear previous graph
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    // Set up the force simulation
    const simulation = d3.forceSimulation<GraphNode>(graphData.nodes)
      .force('link', d3.forceLink<GraphNode, GraphEdge>(graphData.edges).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(16));

    // Main container for zoom and pan
    const g = svg.append('g');

    // Arrowhead marker definition
    g.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 23)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 10)
      .attr('markerHeight', 10)
      .attr('xoverflow', 'visible')
      .append('svg:path')
      .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
      .attr('fill', theme.palette.text.secondary)
      .style('stroke', 'none');

    // Create the links (edges)
    const link = g.append('g')
      .attr('stroke-opacity', 0.6)
      .selectAll('line')
      .data(graphData.edges)
      .join('line')
      .attr('stroke', theme.palette.divider)
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrowhead)');

    // Create the nodes
    const node = g.append('g')
      .selectAll('circle')
      .data(graphData.nodes)
      .join('circle')
      .attr('r', 8)
      .attr('fill', theme.palette.primary.main)
      .attr('stroke', theme.palette.background.paper)
      .attr('stroke-width', 1.5)
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        setSelectedNode(d);
        // Center view on clicked node
        const transform = d3.zoomIdentity.translate(width / 2, height / 2).scale(1.5).translate(-d.x!, -d.y!);
        svg.transition().duration(750).call(zoom.transform, transform);
      });

    // Add labels to nodes
    const label = g.append('g')
      .selectAll('text')
      .data(graphData.nodes)
      .join('text')
      .text(d => d.name)
      .attr('font-size', 10)
      .attr('dx', 12)
      .attr('dy', 4)
      .attr('fill', theme.palette.text.secondary)
      .style('pointer-events', 'none');

    // Define drag behavior
    const drag = d3.drag<SVGCircleElement, GraphNode>()
        .on('start', (event) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          event.subject.fx = event.subject.x;
          event.subject.fy = event.subject.y;
        })
        .on('drag', (event) => {
          event.subject.fx = event.x;
          event.subject.fy = event.y;
        })
        .on('end', (event) => {
          if (!event.active) simulation.alphaTarget(0);
          event.subject.fx = null;
          event.subject.fy = null;
        });
    
    node.call(drag as any);

    // HIGHLIGHTING LOGIC
    // We update the node appearance directly, without a separate effect
    node.attr('stroke', d => selectedNode?.id === d.id ? theme.palette.secondary.main : theme.palette.background.paper)
        .attr('stroke-width', d => selectedNode?.id === d.id ? 3 : 1.5);

    // Update positions on each simulation 'tick'
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as GraphNode).x!)
        .attr('y1', d => (d.source as GraphNode).y!)
        .attr('x2', d => (d.target as GraphNode).x!)
        .attr('y2', d => (d.target as GraphNode).y!);

      node
        .attr('cx', d => d.x!)
        .attr('cy', d => d.y!);

      label
        .attr('x', d => d.x!)
        .attr('y', d => d.y!);
    });

    // Set up zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 5])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

  }, [graphData, theme, setSelectedNode, selectedNode]);

  if (isLoading && !graphData) {
    return <Box sx={{ p: 2, textAlign: 'center' }}><Typography>Loading graph...</Typography></Box>;
  }

  if (!repoId) {
      return <Box sx={{ p: 2, textAlign: 'center' }}><Typography color="text.secondary">Select a repository to see the dependency graph.</Typography></Box>;
  }

  if (!graphData || graphData.nodes.length === 0) {
    return <Box sx={{ p: 2, textAlign: 'center' }}><Typography color="text.secondary">No graph data available for this repository.</Typography></Box>;
  }

  return (
    <Box sx={{ width: '100%', height: '100%', overflow: 'hidden' }}>
      <svg ref={svgRef} style={{ width: '100%', height: '100%' }}></svg>
    </Box>
  );
};

export default GraphPanel; 