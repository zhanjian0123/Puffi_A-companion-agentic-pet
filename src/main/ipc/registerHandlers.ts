import { BrowserWindow, ipcMain } from 'electron';
import type { PythonAgentClient } from '../python/PythonAgentClient';

export interface WindowController {
  closePanel: () => void;
  isPanelOpen: () => boolean;
  openPanel: () => void;
  syncPanelToPet: () => void;
  togglePanel: () => void;
}

interface DragSession {
  startBounds: Electron.Rectangle;
  startX: number;
  startY: number;
}

export function registerIpcHandlers(agentClient: PythonAgentClient, windows: WindowController): void {
  const dragSessions = new Map<number, DragSession>();

  ipcMain.handle('chat:message', async (_event, message: string) => {
    return agentClient.chat(message);
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
    windows.togglePanel();
    return { success: true, isOpen: windows.isPanelOpen() };
  });

  ipcMain.handle('window:drag-start', async (event, point: { x: number; y: number }) => {
    const window = BrowserWindow.fromWebContents(event.sender);
    if (window) {
      dragSessions.set(event.sender.id, {
        startBounds: window.getBounds(),
        startX: point.x,
        startY: point.y,
      });
    }

    return { success: true };
  });

  ipcMain.handle('window:drag-move-to', async (event, point: { x: number; y: number }) => {
    const window = BrowserWindow.fromWebContents(event.sender);
    const session = dragSessions.get(event.sender.id);

    if (window && session) {
      const dx = point.x - session.startX;
      const dy = point.y - session.startY;
      window.setBounds({
        ...session.startBounds,
        x: Math.round(session.startBounds.x + dx),
        y: Math.round(session.startBounds.y + dy),
      });
      windows.syncPanelToPet();
    }

    return { success: true };
  });

  ipcMain.handle('window:drag-end', async (event) => {
    dragSessions.delete(event.sender.id);
    return { success: true };
  });
}
