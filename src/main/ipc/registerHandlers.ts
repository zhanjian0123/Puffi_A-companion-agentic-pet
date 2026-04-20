import { BrowserWindow, ipcMain } from 'electron';
import type { AgentCore } from '../../agent/core/AgentCore';

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

export function registerIpcHandlers(agentCore: AgentCore, windows: WindowController): void {
  const dragSessions = new Map<number, DragSession>();

  ipcMain.handle('chat:message', async (_event, message: string) => {
    return agentCore.processMessage(message);
  });

  ipcMain.handle('kb:search', async (_event, query: string) => {
    return agentCore.searchKnowledge(query);
  });

  ipcMain.handle('tool:invoke', async (_event, toolName: string, params: unknown) => {
    return agentCore.invokeTool(toolName, params);
  });

  ipcMain.handle('window:set-panel-open', async (_event, isOpen: boolean) => {
    console.log('[IPC] window:set-panel-open', { isOpen });
    if (isOpen) {
      windows.openPanel();
    } else {
      windows.closePanel();
    }

    return { success: true };
  });

  ipcMain.handle('window:toggle-panel', async () => {
    console.log('[IPC] window:toggle-panel');
    windows.togglePanel();
    return { success: true, isOpen: windows.isPanelOpen() };
  });

  ipcMain.handle('window:drag-by', async (event, delta: { dx: number; dy: number }) => {
    console.log('[IPC] window:drag-by', delta);
    const window = BrowserWindow.fromWebContents(event.sender);
    if (window) {
      const bounds = window.getBounds();
      window.setBounds({
        ...bounds,
        x: Math.round(bounds.x + delta.dx),
        y: Math.round(bounds.y + delta.dy),
      });
    }

    return { success: true };
  });

  ipcMain.handle('window:drag-start', async (event, point: { x: number; y: number }) => {
    const window = BrowserWindow.fromWebContents(event.sender);
    if (window) {
      dragSessions.set(event.sender.id, {
        startBounds: window.getBounds(),
        startX: point.x,
        startY: point.y,
      });
      console.log('[IPC] window:drag-start', point);
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
      console.log('[IPC] window:drag-move-to', { point, dx, dy });
    }

    return { success: true };
  });

  ipcMain.handle('window:drag-end', async (event) => {
    dragSessions.delete(event.sender.id);
    console.log('[IPC] window:drag-end');
    return { success: true };
  });

  ipcMain.handle('debug:log', async (_event, message: string, payload?: unknown) => {
    console.log('[Renderer]', message, payload ?? '');
    return { success: true };
  });
}
