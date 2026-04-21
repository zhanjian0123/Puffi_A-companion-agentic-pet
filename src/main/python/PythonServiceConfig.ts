export interface PythonServiceConfig {
  baseUrl: string;
  host: string;
  port: number;
}

export function getPythonServiceConfig(): PythonServiceConfig {
  const host = process.env.AI_PET_AGENT_HOST || '127.0.0.1';
  const port = Number(process.env.AI_PET_AGENT_PORT || '8787');

  return {
    baseUrl: `http://${host}:${port}`,
    host,
    port,
  };
}
