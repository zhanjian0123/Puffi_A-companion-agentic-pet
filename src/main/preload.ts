import { contextBridge, ipcRenderer } from 'electron';
import type {
  ChatRequestPayload,
  ChatStreamEvent,
  KnowledgeUploadProgressEvent,
  ReminderDueEvent,
} from '../shared/types';

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
    uploadKnowledgeFile: (file: unknown, requestId: string) => {
      const filePath = (file as { path?: string }).path;
      if (!filePath) {
        throw new Error('无法读取拖入文件的本地路径。');
      }
      return ipcRenderer.invoke('knowledge:upload-file', { filePath, requestId });
    },
    onKnowledgeUploadProgress: (callback: (event: KnowledgeUploadProgressEvent) => void) => {
      const listener = (_event: Electron.IpcRendererEvent, payload: KnowledgeUploadProgressEvent) => {
        callback(payload);
      };

      ipcRenderer.on('knowledge:upload-progress', listener);

      return () => {
        ipcRenderer.removeListener('knowledge:upload-progress', listener);
      };
    },
    onReminderDue: (callback: (event: ReminderDueEvent) => void) => {
      const listener = (_event: Electron.IpcRendererEvent, payload: ReminderDueEvent) => {
        callback(payload);
      };

      ipcRenderer.on('reminder:due', listener);

      return () => {
        ipcRenderer.removeListener('reminder:due', listener);
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
