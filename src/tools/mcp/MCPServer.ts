export class MCPServer {
  async initialize(): Promise<void> {
    console.log('[MCP] Placeholder - MCP integration coming soon');
  }

  async listTools(): Promise<any[]> {
    return [];
  }

  async invokeTool(_serverName: string, _toolName: string, _args: any): Promise<any> {
    return { error: 'MCP not implemented yet' };
  }
}
