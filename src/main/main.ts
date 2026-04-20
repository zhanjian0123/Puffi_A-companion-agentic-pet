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
  console.log('[Main] closePanelWindow called');
  if (panelWindow && !panelWindow.isDestroyed()) {
    panelWindow.hide();
    console.log('[Main] Panel window hidden');
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

function openPanelWindow(): void {
  console.log('[Main] openPanelWindow called');
  if (!petWindow || petWindow.isDestroyed()) {
    console.log('[Main] openPanelWindow aborted: petWindow missing');
    return;
  }

  const showPanel = () => {
    if (!panelWindow || panelWindow.isDestroyed()) {
      console.log('[Main] showPanel aborted: panelWindow missing');
      return;
    }

    positionPanelWindow(panelWindow, petWindow!);
    panelWindow.show();
    panelWindow.focus();
    console.log('[Main] Panel window shown');
  };

  if (!panelWindow || panelWindow.isDestroyed()) {
    console.log('[Main] Creating panelWindow');
    panelWindow = createPanelWindow();
    panelWindow.on('closed', () => {
      console.log('[Main] Panel window closed');
      panelWindow = null;
    });
    panelWindow.once('ready-to-show', showPanel);
    return;
  }

  if (panelWindow.webContents.isLoadingMainFrame()) {
    console.log('[Main] Panel window still loading');
    panelWindow.once('ready-to-show', showPanel);
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
  petWindow.on('move', () => {
    syncPanelWindowToPet();
  });
  petWindow.on('closed', () => {
    petWindow = null;
  });
  console.log('[Main] Core initialized');

  app.on('activate', () => {
    if (!petWindow || petWindow.isDestroyed()) {
      petWindow = createPetWindow();
      petWindow.on('move', () => {
        syncPanelWindowToPet();
      });
      petWindow.on('closed', () => {
        petWindow = null;
      });
    }
  });
});

app.on('window-all-closed', () => {
  console.log('[Main] Window all closed');
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// 错误处理
process.on('uncaughtException', (error) => {
  console.error('[Main] Uncaught exception:', error);
});

process.on('unhandledRejection', (reason) => {
  console.error('[Main] Unhandled rejection:', reason);
});
