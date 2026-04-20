import { app, BrowserWindow } from 'electron';
import { createMainWindow } from './app/createMainWindow';
import { bootstrapApp } from './bootstrap';
import { registerIpcHandlers } from './ipc/registerHandlers';

let mainWindow: BrowserWindow | null = null;

app.whenReady().then(async () => {
  console.log('[Main] App ready');
  const services = await bootstrapApp();
  registerIpcHandlers(services.agentCore);

  mainWindow = createMainWindow();
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
  console.log('[Main] Core initialized');

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createMainWindow();
      mainWindow.on('closed', () => {
        mainWindow = null;
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
