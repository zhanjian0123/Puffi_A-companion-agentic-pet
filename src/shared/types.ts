export interface ChatHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ElectronAPI {
  chat: (message: string) => Promise<{ response: string; action?: unknown }>;
  history: (limit?: number) => Promise<{ messages: ChatHistoryMessage[] }>;
  setPanelOpen: (isOpen: boolean) => Promise<{ success: boolean }>;
  togglePanel: () => Promise<{ success: boolean; isOpen: boolean }>;
  startWindowDrag: (x: number, y: number) => Promise<{ success: boolean }>;
  moveWindowDragTo: (x: number, y: number) => Promise<{ success: boolean }>;
  endWindowDrag: () => Promise<{ success: boolean }>;
}
declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
