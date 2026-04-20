import { app, BrowserWindow, Tray, Menu, ipcMain } from 'electron';
import path from 'path';
import { MCPServer } from './mcp/server';
import { ToolRegistry } from './tools/registry';
import { AgentCore } from '../core/agent/core';

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let mcpServer: MCPServer | null = null;
let agentCore: AgentCore | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 400,
    height: 600,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  // 开发环境加载 Vite，生产环境加载构建文件
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray() {
  const trayPath = path.join(__dirname, '../../resources/icon.png');
  tray = new Tray(trayPath);

  const contextMenu = Menu.buildFromTemplate([
    { label: '打开 AI Pet', click: () => mainWindow?.show() },
    { label: '退出', click: () => app.quit() },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => mainWindow?.show());
}

async function initializeCore() {
  // 初始化 MCP 服务器
  mcpServer = new MCPServer();
  await mcpServer.initialize();

  // 初始化工具注册表
  const toolRegistry = new ToolRegistry();
  toolRegistry.registerDefaults();

  // 初始化 Agent 核心
  agentCore = new AgentCore({
    mcpServer,
    toolRegistry,
  });
}

app.whenReady().then(async () => {
  createWindow();
  createTray();
  await initializeCore();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC 处理器
ipcMain.handle('chat:message', async (_, message) => {
  return agentCore?.processMessage(message);
});

ipcMain.handle('kb:search', async (_, query) => {
  return agentCore?.searchKnowledge(query);
});

ipcMain.handle('tool:invoke', async (_, toolName, params) => {
  return agentCore?.invokeTool(toolName, params);
});
