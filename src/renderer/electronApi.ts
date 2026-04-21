import type { ElectronAPI } from '../shared/types';

export function getElectronApi(): ElectronAPI | null {
  return window.electronAPI ?? null;
}

export function requireElectronApi(): ElectronAPI {
  const api = getElectronApi();

  if (!api) {
    throw new Error('Electron preload API 未注入，当前窗口无法调用桌面能力。');
  }

  return api;
}
