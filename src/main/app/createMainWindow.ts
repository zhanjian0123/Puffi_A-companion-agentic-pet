import { app, BrowserWindow } from 'electron';
import path from 'path';

export function createMainWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 400,
    height: 600,
    frame: true,
    transparent: false,
    alwaysOnTop: false,
    skipTaskbar: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, '../preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,
    },
  });

  const isDev = !app.isPackaged || process.env.NODE_ENV === 'development';
  const devUrl = 'http://127.0.0.1:5173';

  console.log('[Main] Creating window, loading:', devUrl);

  if (isDev) {
    void window.loadURL(devUrl);
    window.webContents.openDevTools();
  } else {
    void window.loadFile(path.join(__dirname, '../../renderer/index.html'));
  }

  window.webContents.on('did-fail-load', (_event, errorCode, errorDesc) => {
    console.error('[Main] Page load failed:', errorCode, errorDesc);
  });

  window.webContents.on('did-finish-load', () => {
    console.log('[Main] Page loaded successfully');
    window.show();
    window.focus();
  });

  return window;
}
