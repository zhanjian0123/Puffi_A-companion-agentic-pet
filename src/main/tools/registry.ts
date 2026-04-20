export interface Tool {
  name: string;
  description: string;
  handler: (params: any) => Promise<any>;
}

export class ToolRegistry {
  private tools: Map<string, Tool> = new Map();

  register(tool: Tool) {
    this.tools.set(tool.name, tool);
    console.log(`[Tool] Registered: ${tool.name}`);
  }

  registerDefaults() {
    // 系统工具
    this.register({
      name: 'system.screenshot',
      description: 'Capture current screen',
      handler: async () => {
        // TODO: 实现截图
        return { success: true, data: 'screenshot_data' };
      },
    });

    this.register({
      name: 'system.clipboard.read',
      description: 'Read clipboard content',
      handler: async () => {
        const { clipboard } = await import('electron');
        return { content: clipboard.readText() };
      },
    });

    this.register({
      name: 'system.notify',
      description: 'Send system notification',
      handler: async ({ title, body }) => {
        const { Notification } = await import('electron');
        new Notification({ title, body }).show();
        return { success: true };
      },
    });

    // 知识库工具
    this.register({
      name: 'kb.search',
      description: 'Search knowledge base',
      handler: async ({ query }) => {
        // TODO: 连接到 RAG 引擎
        return { results: [] };
      },
    });

    // Web 搜索
    this.register({
      name: 'web.search',
      description: 'Search the web',
      handler: async ({ query }) => {
        // TODO: 实现 web 搜索
        return { results: [] };
      },
    });
  }

  get(name: string): Tool | undefined {
    return this.tools.get(name);
  }

  list(): Tool[] {
    return Array.from(this.tools.values());
  }
}
