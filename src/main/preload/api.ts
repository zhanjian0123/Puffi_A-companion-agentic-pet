import { contextBridge, ipcRenderer } from 'electron';

export function registerPreloadApi(): void {
  contextBridge.exposeInMainWorld('electronAPI', {
    chat: (message: string) => ipcRenderer.invoke('chat:message', message),
    kbSearch: (query: string) => ipcRenderer.invoke('kb:search', query),
    toolInvoke: (toolName: string, params: unknown) => ipcRenderer.invoke('tool:invoke', toolName, params),
    setPanelOpen: (isOpen: boolean) => ipcRenderer.invoke('window:set-panel-open', isOpen),
    togglePanel: () => ipcRenderer.invoke('window:toggle-panel'),
    dragWindowBy: (dx: number, dy: number) => ipcRenderer.invoke('window:drag-by', { dx, dy }),
    startWindowDrag: (x: number, y: number) => ipcRenderer.invoke('window:drag-start', { x, y }),
    moveWindowDragTo: (x: number, y: number) => ipcRenderer.invoke('window:drag-move-to', { x, y }),
    endWindowDrag: () => ipcRenderer.invoke('window:drag-end'),
    debugLog: (message: string, payload?: unknown) => ipcRenderer.invoke('debug:log', message, payload),
  });
}
