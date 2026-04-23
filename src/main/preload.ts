import { contextBridge, ipcRenderer } from 'electron';
import type { ChatRequestPayload, ChatStreamEvent } from '../shared/types';

try {
  ipcRenderer.send('bridge:ready');

  contextBridge.exposeInMainWorld('electronAPI', {
    chat: (payload: ChatRequestPayload) => ipcRenderer.invoke('chat:message', payload),
    history: (limit?: number) => ipcRenderer.invoke('chat:history', limit),
    startChatStream: (payload: ChatRequestPayload & { requestId: string }) =>
      ipcRenderer.invoke('chat:stream-start', payload),
    onChatStreamEvent: (callback: (event: ChatStreamEvent) => void) => {
      const listener = (_event: Electron.IpcRendererEvent, payload: ChatStreamEvent) => {
        callback(payload);
      };

      ipcRenderer.on('chat:stream-event', listener);

      return () => {
        ipcRenderer.removeListener('chat:stream-event', listener);
      };
    },
    setPanelOpen: (isOpen: boolean) => ipcRenderer.invoke('window:set-panel-open', isOpen),
    togglePanel: () => ipcRenderer.invoke('window:toggle-panel'),
    startWindowDrag: (x: number, y: number) => ipcRenderer.invoke('window:drag-start', { x, y }),
    moveWindowDragTo: (x: number, y: number) => ipcRenderer.invoke('window:drag-move-to', { x, y }),
    endWindowDrag: () => ipcRenderer.invoke('window:drag-end'),
  });
} catch (error) {
  console.error('[Preload] register failed', error);
}
