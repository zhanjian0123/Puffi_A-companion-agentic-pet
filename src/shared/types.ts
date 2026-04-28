export type PetState = 'idle' | 'thinking' | 'searching' | 'tooling' | 'success' | 'error' | 'sleepy';

export interface ChatHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatStreamEvent {
  requestId: string;
  type: 'delta' | 'done' | 'error' | 'state';
  delta?: string;
  message?: string;
  pet_state?: PetState;
}

export interface ChatRequestPayload {
  message: string;
  mode?: string;
}

export interface KnowledgeUploadProgressEvent {
  requestId: string;
  progress: number;
  phase: 'uploading' | 'processing' | 'done' | 'error';
  message?: string;
}

export interface ReminderDueEvent {
  id: string;
  title: string;
  remindAt: string;
}

export interface ElectronAPI {
  chat: (payload: ChatRequestPayload) => Promise<{ response: string; action?: unknown }>;
  history: (limit?: number) => Promise<{ messages: ChatHistoryMessage[] }>;
  startChatStream: (payload: ChatRequestPayload & { requestId: string }) => Promise<{ requestId: string }>;
  onChatStreamEvent: (callback: (event: ChatStreamEvent) => void) => () => void;
  uploadKnowledgeFile: (file: unknown, requestId: string) => Promise<{ message: string }>;
  onKnowledgeUploadProgress: (callback: (event: KnowledgeUploadProgressEvent) => void) => () => void;
  onReminderDue: (callback: (event: ReminderDueEvent) => void) => () => void;
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
