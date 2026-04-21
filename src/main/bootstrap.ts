import { PythonAgentClient } from './python/PythonAgentClient';
import { getPythonServiceConfig } from './python/PythonServiceConfig';

export interface AppServices {
  agentClient: PythonAgentClient;
}

export function bootstrapApp(): AppServices {
  const pythonService = getPythonServiceConfig();
  const agentClient = new PythonAgentClient({
    baseUrl: pythonService.baseUrl,
  });

  console.log('[Python] Agent service target:', pythonService.baseUrl);

  return {
    agentClient,
  };
}
