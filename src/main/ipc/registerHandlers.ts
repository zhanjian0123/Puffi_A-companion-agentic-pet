import { ipcMain } from 'electron';
import type { AgentCore } from '../../agent/core/AgentCore';

export function registerIpcHandlers(agentCore: AgentCore): void {
  ipcMain.handle('chat:message', async (_event, message: string) => {
    return agentCore.processMessage(message);
  });

  ipcMain.handle('kb:search', async (_event, query: string) => {
    return agentCore.searchKnowledge(query);
  });

  ipcMain.handle('tool:invoke', async (_event, toolName: string, params: unknown) => {
    return agentCore.invokeTool(toolName, params);
  });
}
