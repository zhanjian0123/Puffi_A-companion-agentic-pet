import { randomUUID } from 'node:crypto';
import { BrowserWindow, ipcMain } from 'electron';
import type { PythonAgentClient } from '../python/PythonAgentClient';
import { ENABLE_DESKTOP_DEBUG_LOGS } from '../../shared/devFlags';

export interface WindowController {
  closePanel: () => void;
  isPanelOpen: () => boolean;
  openPanel: () => void;
  syncPanelToPet: () => void;
  togglePanel: () => void;
}

interface DragSession {
  startWindowX: number;
  startWindowY: number;
  startX: number;
  startY: number;
}

interface StreamPayload {
  message: string;
  mode?: string;
  requestId?: string;
}

interface ChatPayload {
  message: string;
  mode?: string;
}

export function registerIpcHandlers(agentClient: PythonAgentClient, windows: WindowController): void {
  const dragSessions = new Map<number, DragSession>();

  ipcMain.on('bridge:ready', () => {
    if (ENABLE_DESKTOP_DEBUG_LOGS) {
      console.log('[Main] Preload bridge ready');
    }
  });

  ipcMain.handle('chat:message', async (_event, payload: ChatPayload) => {
    return agentClient.chat(payload);
  });

  ipcMain.handle('chat:history', async (_event, limit?: number) => {
    return agentClient.history(limit);
  });

  ipcMain.handle('chat:stream-start', async (event, payload: StreamPayload) => {
    const requestId = payload.requestId || randomUUID();
    const sender = event.sender;

    void (async () => {
      try {
        for await (const chunk of agentClient.chatStream({
          message: payload.message,
          mode: payload.mode,
        })) {
          if (sender.isDestroyed()) {
            return;
          }

          sender.send('chat:stream-event', {
            requestId,
            ...chunk,
          });
        }
      } catch (error) {
        if (!sender.isDestroyed()) {
          sender.send('chat:stream-event', {
            requestId,
            type: 'error',
            message: error instanceof Error ? error.message : '流式响应失败，请稍后再试。',
          });
        }
      }
    })();

    return { requestId };
  });

  ipcMain.handle('window:set-panel-open', async (_event, isOpen: boolean) => {
    if (isOpen) {
      windows.openPanel();
    } else {
      windows.closePanel();
    }

    return { success: true };
  });

  ipcMain.handle('window:toggle-panel', async () => {
    if (ENABLE_DESKTOP_DEBUG_LOGS) {
      console.log('[Main] Toggle panel request');
    }
    windows.togglePanel();
    return { success: true, isOpen: windows.isPanelOpen() };
  });

  ipcMain.handle('window:drag-start', async (event, point: { x: number; y: number }) => {
    const window = BrowserWindow.fromWebContents(event.sender);
    if (window) {
      const [startWindowX, startWindowY] = window.getPosition();
      dragSessions.set(event.sender.id, {
        startWindowX,
        startWindowY,
        startX: point.x,
        startY: point.y,
      });
      if (ENABLE_DESKTOP_DEBUG_LOGS) {
        console.log('[Main] Drag start', point.x, point.y);
      }
    }

    return { success: true };
  });

  ipcMain.handle('window:drag-move-to', async (event, point: { x: number; y: number }) => {
    const window = BrowserWindow.fromWebContents(event.sender);
    const session = dragSessions.get(event.sender.id);

    if (window && session) {
      const dx = point.x - session.startX;
      const dy = point.y - session.startY;
      window.setPosition(
        Math.round(session.startWindowX + dx),
        Math.round(session.startWindowY + dy),
        false
      );
      windows.syncPanelToPet();
    }

    return { success: true };
  });

  ipcMain.handle('window:drag-end', async (event) => {
    if (ENABLE_DESKTOP_DEBUG_LOGS) {
      console.log('[Main] Drag end');
    }
    dragSessions.delete(event.sender.id);
    return { success: true };
  });
}
