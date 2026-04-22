import { contextBridge, ipcRenderer } from 'electron';

try {
  ipcRenderer.send('bridge:ready');

  contextBridge.exposeInMainWorld('electronAPI', {
    chat: (message: string) => ipcRenderer.invoke('chat:message', message),
    history: (limit?: number) => ipcRenderer.invoke('chat:history', limit),
    setPanelOpen: (isOpen: boolean) => ipcRenderer.invoke('window:set-panel-open', isOpen),
    togglePanel: () => ipcRenderer.invoke('window:toggle-panel'),
    startWindowDrag: (x: number, y: number) => ipcRenderer.invoke('window:drag-start', { x, y }),
    moveWindowDragTo: (x: number, y: number) => ipcRenderer.invoke('window:drag-move-to', { x, y }),
    endWindowDrag: () => ipcRenderer.invoke('window:drag-end'),
  });
} catch (error) {
  console.error('[Preload] register failed', error);
}
