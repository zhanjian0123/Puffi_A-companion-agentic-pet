import { create } from 'zustand';

interface PetState {
  emotion: 'happy' | 'neutral' | 'sad' | 'excited';
  action: 'idle' | 'talking' | 'thinking' | 'sleeping';
  energy: number;
  happiness: number;

  setEmotion: (emotion: PetState['emotion']) => void;
  setAction: (action: PetState['action']) => void;
  updateStats: (energy: number, happiness: number) => void;
}

export const usePetStore = create<PetState>((set) => ({
  emotion: 'neutral',
  action: 'idle',
  energy: 100,
  happiness: 100,

  setEmotion: (emotion) => set({ emotion }),
  setAction: (action) => set({ action }),
  updateStats: (energy, happiness) => set({ energy, happiness }),
}));
