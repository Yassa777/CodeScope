import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { Box, Typography, useTheme } from '@mui/material';
import { useStore } from '../store';
import { useQuery } from 'react-query';

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  type: string;
  name: string;
  data?: Record<string, any>;
}

interface GraphEdge {
  source: GraphNode;
  target: GraphNode;
  type: string;
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

  // Fetch graph data
  const { data: graphData, isLoading } = useQuery<GraphData>(
    ['graph', repoId, level],
    async () => {
      if (!repoId) return { nodes: [], edges: [] };
      const response = await fetch(`${API_BASE_URL}/repo/${repoId}/graph?level=${level}`);
      if (!response.ok) {
        throw new Error('Failed to fetch graph data');
      }
      const data = await response.json();
      // Convert string IDs to node references
      return {
        nodes: data.nodes,
        edges: data.edges.map((edge: any) => ({
          source: data.nodes.find((n: GraphNode) => n.id === edge.source),
          target: data.nodes.find((n: GraphNode) => n.id === edge.target),
          type: edge.type
        }))
      };
    },
    {
      enabled: !!repoId,
      refetchInterval: 5000, // Refetch every 5 seconds while analysis is ongoing
    }
  );

  useEffect(() => {
    if (!svgRef.current || !graphData || graphData.nodes.length === 0) return;

    // Clear previous graph
    d3.select(svgRef.current).selectAll('*').remove();

    // Set up the SVG
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;
    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    // Create a group for the graph
    const g = svg.append('g');

    // Set up zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Set up the force simulation
    const simulation = d3.forceSimulation<GraphNode>()
      .force('link', d3.forceLink<GraphNode, GraphEdge>()
        .id(d => d.id)
        .distance((d: { source: GraphNode; target: GraphNode }) => {
          // Adjust link distance based on node types
          if (d.source.type === 'folder' && d.target.type === 'folder') return 150;
          if (d.source.type === 'file' && d.target.type === 'file') return 100;
          return 120;
        }))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => {
        // Adjust collision radius based on node type
        switch (d.type) {
          case 'folder':
            return 40;
          case 'file':
            return 30;
          case 'function':
            return 20;
          default:
            return 25;
        }
      }));

    // Create the links
    const link = g.append('g')
      .selectAll('line')
      .data(graphData.edges)
      .enter()
      .append('line')
      .attr('stroke', theme.palette.divider)
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', d => {
        // Adjust link width based on relationship type
        switch (d.type) {
          case 'contains':
            return 2;
          case 'references':
            return 1;
          default:
            return 1;
        }
      });

    // Create the nodes
    const node = g.append('g')
      .selectAll('circle')
      .data(graphData.nodes)
      .enter()
      .append('circle')
      .attr('r', d => {
        switch (d.type) {
          case 'folder':
            return 12;
          case 'file':
            return 8;
          case 'function':
            return 6;
          default:
            return 8;
        }
      })
      .attr('fill', d => {
        switch (d.type) {
          case 'folder':
            return theme.palette.primary.main;
          case 'file':
            return theme.palette.secondary.main;
          case 'function':
            return theme.palette.success.main;
          default:
            return theme.palette.grey[500];
        }
      })
      .attr('stroke', d => selectedNode?.id === d.id ? theme.palette.primary.main : 'none')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .call(d3.drag<SVGCircleElement, GraphNode>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended));

    // Add labels
    const label = g.append('g')
      .selectAll('text')
      .data(graphData.nodes)
      .enter()
      .append('text')
      .text(d => d.name)
      .attr('font-size', 12)
      .attr('dx', 12)
      .attr('dy', 4)
      .attr('fill', theme.palette.text.primary)
      .style('pointer-events', 'none');

    // Update the simulation
    simulation
      .nodes(graphData.nodes)
      .on('tick', () => {
        link
          .attr('x1', d => d.source.x!)
          .attr('y1', d => d.source.y!)
          .attr('x2', d => d.target.x!)
          .attr('y2', d => d.target.y!);

        node
          .attr('cx', d => d.x!)
          .attr('cy', d => d.y!);

        label
          .attr('x', d => d.x!)
          .attr('y', d => d.y!);
      });

    simulation.force<d3.ForceLink<GraphNode, GraphEdge>>('link')!
      .links(graphData.edges);

    // Handle node clicks
    node.on('click', (event, d) => {
      setSelectedNode(d);
    });

    // Add hover effects
    node
      .on('mouseover', function(event, d: GraphNode) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('r', () => {
            switch (d.type) {
              case 'folder':
                return 16;
              case 'file':
                return 12;
              case 'function':
                return 10;
              default:
                return 12;
            }
          });
      })
      .on('mouseout', function(event, d: GraphNode) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('r', () => {
            switch (d.type) {
              case 'folder':
                return 12;
              case 'file':
                return 8;
              case 'function':
                return 6;
              default:
                return 8;
            }
          });
      });

    // Drag functions
    function dragstarted(event: d3.D3DragEvent<SVGCircleElement, GraphNode, GraphNode>) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event: d3.D3DragEvent<SVGCircleElement, GraphNode, GraphNode>) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event: d3.D3DragEvent<SVGCircleElement, GraphNode, GraphNode>) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    return () => {
      simulation.stop();
    };
  }, [graphData, selectedNode, theme]);

  return (
    <Box sx={{ height: '100%', position: 'relative' }}>
      <svg
        ref={svgRef}
        style={{
          width: '100%',
          height: '100%',
          backgroundColor: theme.palette.background.default,
        }}
      />
      {isLoading && (
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            textAlign: 'center',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            Loading graph...
          </Typography>
        </Box>
      )}
      {!isLoading && (!graphData || graphData.nodes.length === 0) && (
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            textAlign: 'center',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            No graph data available
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default GraphPanel; 