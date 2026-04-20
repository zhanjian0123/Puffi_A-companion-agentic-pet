import type { ElectronAPI } from '../shared/types';

type ElectronRequire = {
  ipcRenderer: {
    invoke: (channel: string, ...args: unknown[]) => Promise<any>;
  };
};

declare global {
  interface Window {
    require?: (name: string) => ElectronRequire;
  }
}

function getFallbackApi(): ElectronAPI | null {
  if (typeof window.require !== 'function') {
    return null;
  }

  try {
    const electron = window.require('electron');
    const { ipcRenderer } = electron;

    return {
      chat: (message: string) => ipcRenderer.invoke('chat:message', message),
      kbSearch: (query: string) => ipcRenderer.invoke('kb:search', query),
      toolInvoke: (toolName: string, params: any) => ipcRenderer.invoke('tool:invoke', toolName, params),
      setPanelOpen: (isOpen: boolean) => ipcRenderer.invoke('window:set-panel-open', isOpen),
      togglePanel: () => ipcRenderer.invoke('window:toggle-panel'),
      dragWindowBy: (dx: number, dy: number) => ipcRenderer.invoke('window:drag-by', { dx, dy }),
      startWindowDrag: (x: number, y: number) => ipcRenderer.invoke('window:drag-start', { x, y }),
      moveWindowDragTo: (x: number, y: number) => ipcRenderer.invoke('window:drag-move-to', { x, y }),
      endWindowDrag: () => ipcRenderer.invoke('window:drag-end'),
      debugLog: (message: string, payload?: unknown) => ipcRenderer.invoke('debug:log', message, payload),
    };
  } catch {
    return null;
  }
}

export function getElectronApi(): ElectronAPI | null {
  return window.electronAPI ?? getFallbackApi();
}
