export interface ChatHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatStreamEvent {
  requestId: string;
  type: 'delta' | 'done' | 'error';
  delta?: string;
  message?: string;
}

export interface ElectronAPI {
  chat: (message: string) => Promise<{ response: string; action?: unknown }>;
  history: (limit?: number) => Promise<{ messages: ChatHistoryMessage[] }>;
  startChatStream: (payload: { message: string; requestId: string }) => Promise<{ requestId: string }>;
  onChatStreamEvent: (callback: (event: ChatStreamEvent) => void) => () => void;
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
