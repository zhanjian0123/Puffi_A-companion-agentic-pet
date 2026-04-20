import type { ToolDefinition } from '../registry/types';

export interface MCPServerConfig {
  name: string;
  command: string;
  args?: string[];
}

export class MCPClientManager {
  constructor(private readonly configs: MCPServerConfig[]) {}

  async listTools(): Promise<ToolDefinition[]> {
    return this.configs.map((config) => ({
      name: `mcp.${config.name}.placeholder`,
      description: `Placeholder tool namespace for ${config.name}`,
      inputSchema: { type: 'object', properties: {} },
    }));
  }
}
