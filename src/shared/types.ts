export interface ElectronAPI {
  chat: (message: string) => Promise<{ response: string; action?: any }>;
  kbSearch: (query: string) => Promise<any>;
  toolInvoke: (toolName: string, params: any) => Promise<any>;
  setPanelOpen: (isOpen: boolean) => Promise<{ success: boolean }>;
  togglePanel: () => Promise<{ success: boolean; isOpen: boolean }>;
  dragWindowBy: (dx: number, dy: number) => Promise<{ success: boolean }>;
  startWindowDrag: (x: number, y: number) => Promise<{ success: boolean }>;
  moveWindowDragTo: (x: number, y: number) => Promise<{ success: boolean }>;
  endWindowDrag: () => Promise<{ success: boolean }>;
  debugLog: (message: string, payload?: unknown) => Promise<{ success: boolean }>;
}

// 在 window 上挂载 electron API
declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
