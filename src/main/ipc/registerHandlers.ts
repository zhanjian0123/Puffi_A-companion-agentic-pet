import { randomUUID } from 'node:crypto';
import { BrowserWindow, ipcMain, screen } from 'electron';
import type { PythonAgentClient } from '../python/PythonAgentClient';
import { ENABLE_DESKTOP_DEBUG_LOGS } from '../../shared/devFlags';
import type { PetDockSide } from '../../shared/types';

export interface WindowController {
  closePanel: () => void;
  isPanelOpen: () => boolean;
  openPanel: () => void;
  syncPanelToPet: () => void;
  togglePanel: () => void;
}

interface DragSession {
  moved: boolean;
  startWindowX: number;
  startWindowY: number;
  startX: number;
  startY: number;
}

const SIDE_SNAP_THRESHOLD = 80; // Distance in pixels from screen edge to trigger snap
const PET_BODY_LEFT = 26;
const PET_BODY_WIDTH = 128;
const PET_BODY_SIDE_OVERHANG = 80;

interface StreamPayload {
  message: string;
  mode?: string;
  requestId?: string;
}

interface ChatPayload {
  message: string;
  mode?: string;
}

interface KnowledgeUploadPayload {
  filePath: string;
  requestId?: string;
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
          sendChatStreamEvent({
            requestId,
            ...chunk,
          });
        }
      } catch (error) {
        if (!sender.isDestroyed()) {
          sendChatStreamEvent({
            requestId,
            type: 'error',
            message: error instanceof Error ? error.message : '流式响应失败，请稍后再试。',
            pet_state: 'error',
          });
        }
      }
    })();

    return { requestId };
  });

  ipcMain.handle('knowledge:upload-file', async (event, payload: KnowledgeUploadPayload) => {
    const requestId = payload.requestId || randomUUID();
    const sender = event.sender;

    try {
      const result = await agentClient.uploadKnowledgeFile(payload.filePath, (progress) => {
        if (!sender.isDestroyed()) {
          sender.send('knowledge:upload-progress', {
            requestId,
            phase: progress >= 100 ? 'processing' : 'uploading',
            progress,
          });
        }
      });

      if (!sender.isDestroyed()) {
        sender.send('knowledge:upload-progress', {
          requestId,
          phase: 'done',
          progress: 100,
          message: result.message,
        });
      }

      return { message: result.message };
    } catch (error) {
      const message = error instanceof Error ? error.message : '知识库文件上传失败。';
      console.error('[Knowledge] upload ipc error:', message);
      if (!sender.isDestroyed()) {
        sender.send('knowledge:upload-progress', {
          requestId,
          phase: 'error',
          progress: 100,
          message,
        });
      }
      throw error;
    }
  });

  ipcMain.handle('scheduled-task:runs', async (_event, taskId?: string, limit?: number) => {
    return agentClient.scheduledTaskRuns(taskId, limit);
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
        moved: false,
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
      session.moved = session.moved || Math.abs(dx) > 6 || Math.abs(dy) > 6;
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
    const window = BrowserWindow.fromWebContents(event.sender);
    const session = dragSessions.get(event.sender.id);

    if (ENABLE_DESKTOP_DEBUG_LOGS) {
      console.log('[Main] Drag end');
    }

    if (window && session?.moved) {
      const dockSide = snapPetWindowToSide(window);
      sendPetDockChange(window, dockSide);
      windows.syncPanelToPet();
    }

    dragSessions.delete(event.sender.id);
    return { success: true };
  });
}

function snapPetWindowToSide(window: BrowserWindow): PetDockSide {
  if (window.isDestroyed()) {
    return null;
  }

  const bounds = window.getBounds();
  const display = screen.getDisplayMatching(bounds);
  const workArea = display.workArea;
  const windowCenterX = bounds.x + Math.round(bounds.width / 2);
  const leftDistance = Math.abs(windowCenterX - workArea.x);
  const rightEdge = workArea.x + workArea.width;
  const rightDistance = Math.abs(rightEdge - windowCenterX);

  if (leftDistance > SIDE_SNAP_THRESHOLD && rightDistance > SIDE_SNAP_THRESHOLD) {
    return null;
  }

  const dockSide: PetDockSide = leftDistance <= rightDistance ? 'left' : 'right';
  const leftSnapX = workArea.x - PET_BODY_LEFT - PET_BODY_SIDE_OVERHANG;
  const rightSnapX = rightEdge - PET_BODY_LEFT - PET_BODY_WIDTH + PET_BODY_SIDE_OVERHANG;
  const nextX = dockSide === 'left' ? leftSnapX : rightSnapX;
  const nextY = Math.min(Math.max(bounds.y, workArea.y + 12), workArea.y + workArea.height - bounds.height - 12);
  window.setPosition(Math.round(nextX), Math.round(nextY), true);
  return dockSide;
}

function sendPetDockChange(window: BrowserWindow, side: PetDockSide): void {
  if (!window.isDestroyed() && !window.webContents.isDestroyed()) {
    window.webContents.send('pet:dock-change', { side });
  }
}

function sendChatStreamEvent(payload: unknown): void {
  for (const window of BrowserWindow.getAllWindows()) {
    if (!window.isDestroyed() && !window.webContents.isDestroyed()) {
      window.webContents.send('chat:stream-event', payload);
    }
  }
}
