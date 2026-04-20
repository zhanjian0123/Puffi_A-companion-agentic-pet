import { contextBridge, ipcRenderer } from 'electron';

export function registerPreloadApi(): void {
  contextBridge.exposeInMainWorld('electronAPI', {
    chat: (message: string) => ipcRenderer.invoke('chat:message', message),
    kbSearch: (query: string) => ipcRenderer.invoke('kb:search', query),
    toolInvoke: (toolName: string, params: unknown) => ipcRenderer.invoke('tool:invoke', toolName, params),
  });
}
