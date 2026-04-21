import { app, BrowserWindow } from 'electron';
import { createPanelWindow, createPetWindow, positionPanelWindow } from './app/createMainWindow';
import { bootstrapApp } from './bootstrap';
import { registerIpcHandlers } from './ipc/registerHandlers';

let petWindow: BrowserWindow | null = null;
let panelWindow: BrowserWindow | null = null;

function syncPanelWindowToPet(): void {
  if (petWindow && panelWindow && !petWindow.isDestroyed() && !panelWindow.isDestroyed() && panelWindow.isVisible()) {
    positionPanelWindow(panelWindow, petWindow);
  }
}

function closePanelWindow(): void {
  if (panelWindow && !panelWindow.isDestroyed()) {
    panelWindow.hide();
  }
}

function isPanelWindowOpen(): boolean {
  return Boolean(panelWindow && !panelWindow.isDestroyed() && panelWindow.isVisible());
}

function togglePanelWindow(): void {
  if (isPanelWindowOpen()) {
    closePanelWindow();
    return;
  }

  openPanelWindow();
}

function attachPetWindow(window: BrowserWindow): void {
  window.on('move', () => {
    syncPanelWindowToPet();
  });
  window.on('closed', () => {
    petWindow = null;
    closePanelWindow();
  });
}

function ensurePanelWindow(): BrowserWindow | null {
  if (!petWindow || petWindow.isDestroyed()) {
    return null;
  }

  if (!panelWindow || panelWindow.isDestroyed()) {
    panelWindow = createPanelWindow();
    panelWindow.on('closed', () => {
      panelWindow = null;
    });
  }

  return panelWindow;
}

function openPanelWindow(): void {
  if (!petWindow || petWindow.isDestroyed()) {
    return;
  }

  const nextPanelWindow = ensurePanelWindow();
  if (!nextPanelWindow) {
    return;
  }

  const showPanel = () => {
    if (!petWindow || petWindow.isDestroyed() || !panelWindow || panelWindow.isDestroyed()) {
      return;
    }

    positionPanelWindow(panelWindow, petWindow);
    panelWindow.show();
    panelWindow.focus();
  };

  if (nextPanelWindow.webContents.isLoadingMainFrame()) {
    nextPanelWindow.once('ready-to-show', showPanel);
    return;
  }

  showPanel();
}

app.whenReady().then(async () => {
  console.log('[Main] App ready');
  const services = await bootstrapApp();
  registerIpcHandlers(services.agentClient, {
    openPanel: openPanelWindow,
    closePanel: closePanelWindow,
    isPanelOpen: isPanelWindowOpen,
    syncPanelToPet: syncPanelWindowToPet,
    togglePanel: togglePanelWindow,
  });

  petWindow = createPetWindow();
  attachPetWindow(petWindow);
  console.log('[Main] Core initialized');

  app.on('activate', () => {
    if (!petWindow || petWindow.isDestroyed()) {
      petWindow = createPetWindow();
      attachPetWindow(petWindow);
    }
  });
});

app.on('window-all-closed', () => {
  console.log('[Main] Window all closed');
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

process.on('uncaughtException', (error) => {
  console.error('[Main] Uncaught exception:', error);
});

process.on('unhandledRejection', (reason) => {
  console.error('[Main] Unhandled rejection:', reason);
});
