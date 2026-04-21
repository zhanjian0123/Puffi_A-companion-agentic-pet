import type { ElectronAPI } from '../shared/types';

export function getElectronApi(): ElectronAPI | null {
  return window.electronAPI ?? null;
}
