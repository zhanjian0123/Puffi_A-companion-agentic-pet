import { app, BrowserWindow, screen } from 'electron';
import path from 'path';
import { ENABLE_DESKTOP_DEBUG_LOGS, OPEN_DEVTOOLS } from '../../shared/devFlags';

const PET_WINDOW_SIZE = { width: 220, height: 240 };
const PANEL_WINDOW_SIZE = { width: 380, height: 460 };

function loadRenderer(window: BrowserWindow, mode: 'pet' | 'panel'): void {
  const isDev = !app.isPackaged || process.env.NODE_ENV === 'development';
  const shouldOpenDevTools = OPEN_DEVTOOLS || process.env.OPEN_DEVTOOLS === '1';
  const devUrl = `http://127.0.0.1:5173/?mode=${mode}`;

  console.log('[Main] Creating window, loading:', devUrl);

  if (isDev) {
    void window.loadURL(devUrl);
    if (shouldOpenDevTools) {
      window.webContents.openDevTools({ mode: 'detach' });
    }
  } else {
    void window.loadFile(path.join(__dirname, '../../renderer/index.html'), {
      query: { mode },
    });
  }
}

function attachRendererDiagnostics(window: BrowserWindow, label: 'Main' | 'Panel'): void {
  if (!ENABLE_DESKTOP_DEBUG_LOGS) {
    return;
  }

  window.webContents.on('console-message', (_event, _level, message) => {
    console.log(`[${label} Renderer]`, message);
  });

  window.webContents.on('did-finish-load', () => {
    void window.webContents
      .executeJavaScript(
        `(() => ({
          href: window.location.href,
          mode: new URLSearchParams(window.location.search).get('mode'),
          hasElectronApi: !!window.electronAPI,
          rootExists: !!document.getElementById('root'),
          petExists: !!document.querySelector('.pet'),
        }))()`,
        true
      )
      .then((result) => {
        console.log(`[${label}] Renderer state`, result);
      })
      .catch((error) => {
        console.error(`[${label}] Renderer inspection failed:`, error);
      });
  });
}

export function createPetWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: PET_WINDOW_SIZE.width,
    height: PET_WINDOW_SIZE.height,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    resizable: false,
    focusable: true,
    movable: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, '../preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
    },
  });

  loadRenderer(window, 'pet');
  attachRendererDiagnostics(window, 'Main');

  window.webContents.on('did-fail-load', (_event, errorCode, errorDesc) => {
    console.error('[Main] Page load failed:', errorCode, errorDesc);
  });

  window.webContents.on('did-finish-load', () => {
    console.log('[Main] Page loaded successfully');
    window.setAlwaysOnTop(true, 'screen-saver');
    window.show();
  });

  return window;
}

export function createPanelWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: PANEL_WINDOW_SIZE.width,
    height: PANEL_WINDOW_SIZE.height,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    resizable: false,
    focusable: true,
    movable: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, '../preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
    },
  });

  loadRenderer(window, 'panel');
  attachRendererDiagnostics(window, 'Panel');

  window.webContents.on('did-fail-load', (_event, errorCode, errorDesc) => {
    console.error('[Panel] Page load failed:', errorCode, errorDesc);
  });

  window.setAlwaysOnTop(true, 'floating');

  return window;
}

export function positionPanelWindow(panelWindow: BrowserWindow, petWindow: BrowserWindow): void {
  const petBounds = petWindow.getBounds();
  const display = screen.getDisplayMatching(petBounds);
  const workArea = display.workArea;

  const petVisualWidth = 140;
  const petVisualHeight = 140;
  const petVisualX = petBounds.x + Math.round((petBounds.width - petVisualWidth) / 2);
  const petVisualY = petBounds.y + (petBounds.height - petVisualHeight - 16);

  const nextX = Math.round(petVisualX + (petVisualWidth - PANEL_WINDOW_SIZE.width) / 2);
  const nextY = Math.round(petVisualY + petVisualHeight - 128);

  const boundedX = Math.min(
    Math.max(nextX, workArea.x + 12),
    workArea.x + workArea.width - PANEL_WINDOW_SIZE.width - 12
  );
  const boundedY = Math.max(nextY, workArea.y + 12);

  panelWindow.setPosition(boundedX, boundedY, false);
  panelWindow.setAlwaysOnTop(true, 'floating');
  petWindow.setAlwaysOnTop(true, 'screen-saver');
}
