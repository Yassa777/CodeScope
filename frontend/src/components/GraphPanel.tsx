import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { Box, Typography } from '@mui/material';
import { useStore } from '../store';

interface GraphNode {
  id: string;
  type: string;
  name: string;
  data?: Record<string, any>;
}

interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface GraphPanelProps {
  level: number;
}

const GraphPanel: React.FC<GraphPanelProps> = ({ level }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const setSelectedNode = useStore((state) => state.setSelectedNode);
  const selectedNode = useStore((state) => state.selectedNode);

  useEffect(() => {
    if (!svgRef.current) return;

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

    // Set up the force simulation
    const simulation = d3.forceSimulation<GraphNode>()
      .force('link', d3.forceLink<GraphNode, GraphEdge>()
        .id(d => d.id)
        .distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2));

    // TODO: Replace with actual graph data
    const mockData: GraphData = {
      nodes: [
        { id: '1', type: 'folder', name: 'src' },
        { id: '2', type: 'file', name: 'main.ts' },
        { id: '3', type: 'function', name: 'main' },
      ],
      edges: [
        { source: '1', target: '2', type: 'contains' },
        { source: '2', target: '3', type: 'contains' },
      ],
    };

    // Create the links
    const link = g.append('g')
      .selectAll('line')
      .data(mockData.edges)
      .enter()
      .append('line')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 1);

    // Create the nodes
    const node = g.append('g')
      .selectAll('circle')
      .data(mockData.nodes)
      .enter()
      .append('circle')
      .attr('r', 5)
      .attr('fill', d => {
        switch (d.type) {
          case 'folder':
            return '#90caf9';
          case 'file':
            return '#f48fb1';
          case 'function':
            return '#a5d6a7';
          default:
            return '#999';
        }
      })
      .call(d3.drag<SVGCircleElement, GraphNode>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended));

    // Add labels
    const label = g.append('g')
      .selectAll('text')
      .data(mockData.nodes)
      .enter()
      .append('text')
      .text(d => d.name)
      .attr('font-size', 12)
      .attr('dx', 12)
      .attr('dy', 4);

    // Update the simulation
    simulation
      .nodes(mockData.nodes)
      .on('tick', () => {
        link
          .attr('x1', d => (d.source as any).x)
          .attr('y1', d => (d.source as any).y)
          .attr('x2', d => (d.target as any).x)
          .attr('y2', d => (d.target as any).y);

        node
          .attr('cx', d => d.x!)
          .attr('cy', d => d.y!);

        label
          .attr('x', d => d.x!)
          .attr('y', d => d.y!);
      });

    simulation.force<d3.ForceLink<GraphNode, GraphEdge>>('link')!
      .links(mockData.edges);

    // Handle node clicks
    node.on('click', (event, d) => {
      setSelectedNode(d);
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

    // Cleanup
    return () => {
      simulation.stop();
    };
  }, [level, setSelectedNode]);

  return (
    <Box sx={{ height: '100%', position: 'relative' }}>
      <svg
        ref={svgRef}
        style={{
          width: '100%',
          height: '100%',
        }}
      />
      <Typography
        variant="caption"
        sx={{
          position: 'absolute',
          bottom: 8,
          right: 8,
          color: 'text.secondary',
        }}
      >
        Level {level}
      </Typography>
    </Box>
  );
};

export default GraphPanel; 