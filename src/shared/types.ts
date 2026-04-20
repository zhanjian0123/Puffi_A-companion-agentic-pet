export interface ElectronAPI {
  chat: (message: string) => Promise<{ response: string; action?: any }>;
  kbSearch: (query: string) => Promise<any>;
  toolInvoke: (toolName: string, params: any) => Promise<any>;
}

// 在 window 上挂载 electron API
declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
