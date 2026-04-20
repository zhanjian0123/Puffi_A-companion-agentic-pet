import { PythonAgentClient } from './python/PythonAgentClient';
import { getPythonServiceConfig, type PythonServiceConfig } from './python/PythonServiceConfig';

export interface AppServices {
  agentClient: PythonAgentClient;
  pythonService: PythonServiceConfig;
}

export async function bootstrapApp(): Promise<AppServices> {
  const pythonService = getPythonServiceConfig();
  const agentClient = new PythonAgentClient({
    baseUrl: pythonService.baseUrl,
  });

  console.log('[Python] Agent service configured:', pythonService.baseUrl);

  return {
    agentClient,
    pythonService,
  };
}
