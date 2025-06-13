import { create } from 'zustand';

interface Node {
  id: string;
  type: string;
  name: string;
  data?: Record<string, any>;
}

interface GraphState {
  selectedNode: Node | null;
  graphLevel: number;
  setSelectedNode: (node: Node | null) => void;
  setGraphLevel: (level: number) => void;
}

export const useStore = create<GraphState>((set) => ({
  selectedNode: null,
  graphLevel: 1,
  setSelectedNode: (node) => set({ selectedNode: node }),
  setGraphLevel: (level) => set({ graphLevel: level }),
})); 