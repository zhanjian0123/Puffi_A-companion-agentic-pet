import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

export interface MCPServerConfig {
  name: string;
  command: string;
  args: string[];
}

export class MCPServer {
  private clients: Map<string, Client> = new Map();
  private configs: MCPServerConfig[] = [];

  constructor() {
    this.loadDefaultConfigs();
  }

  private loadDefaultConfigs() {
    // 默认 MCP 服务器配置
    this.configs = [
      {
        name: 'filesystem',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-filesystem', process.env.HOME || '~'],
      },
      {
        name: 'memory',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-memory'],
      },
    ];
  }

  async initialize() {
    console.log('[MCP] Initializing servers...');

    for (const config of this.configs) {
      try {
        await this.connectServer(config);
        console.log(`[MCP] Connected to ${config.name}`);
      } catch (error) {
        console.error(`[MCP] Failed to connect ${config.name}:`, error);
      }
    }
  }

  private async connectServer(config: MCPServerConfig) {
    const transport = new StdioClientTransport({
      command: config.command,
      args: config.args,
    });

    const client = new Client(
      {
        name: `aipet-${config.name}`,
        version: '0.1.0',
      },
      {
        capabilities: {},
      }
    );

    await client.connect(transport);
    this.clients.set(config.name, client);
  }

  getClient(name: string): Client | undefined {
    return this.clients.get(name);
  }

  async listTools(): Promise<any[]> {
    const allTools: any[] = [];

    for (const [name, client] of this.clients) {
      try {
        const { tools } = await client.listTools();
        allTools.push(...tools.map((t) => ({ ...t, source: name })));
      } catch (error) {
        console.error(`[MCP] Failed to list tools from ${name}:`, error);
      }
    }

    return allTools;
  }

  async invokeTool(serverName: string, toolName: string, args: any) {
    const client = this.clients.get(serverName);
    if (!client) {
      throw new Error(`MCP server ${serverName} not found`);
    }

    return client.callTool({ name: toolName, arguments: args });
  }

  async shutdown() {
    for (const client of this.clients.values()) {
      await client.close();
    }
    this.clients.clear();
  }
}
