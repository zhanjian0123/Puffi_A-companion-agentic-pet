import { Notification } from 'electron';

export interface Tool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  handler: (params: any) => Promise<any>;
}

export interface ToolRegistryOptions {
  searchKnowledge: (query: string) => Promise<any[]>;
}

export class ToolRegistry {
  private readonly tools = new Map<string, Tool>();
  private readonly todos: string[] = [];

  constructor(private readonly options: ToolRegistryOptions) {}

  register(tool: Tool): void {
    this.tools.set(tool.name, tool);
    console.log(`[Tool] Registered: ${tool.name}`);
  }

  registerDefaults(): void {
    this.register({
      name: 'system.screenshot',
      description: 'Capture current screen',
      inputSchema: {
        type: 'object',
        properties: {},
      },
      handler: async () => {
        return { success: true, data: 'screenshot_data' };
      },
    });

    this.register({
      name: 'system.notify',
      description: 'Send system notification',
      inputSchema: {
        type: 'object',
        properties: {
          title: { type: 'string', description: 'Notification title' },
          body: { type: 'string', description: 'Notification body' },
        },
      },
      handler: async ({ title, body }) => {
        new Notification({ title, body }).show();
        return { success: true };
      },
    });

    this.register({
      name: 'kb.search',
      description: 'Search knowledge base',
      inputSchema: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Search query' },
        },
        required: ['query'],
      },
      handler: async ({ query }) => {
        return { results: await this.options.searchKnowledge(query) };
      },
    });

    this.register({
      name: 'todo.add',
      description: 'Add a new todo item',
      inputSchema: {
        type: 'object',
        properties: {
          text: { type: 'string', description: 'Todo text' },
        },
        required: ['text'],
      },
      handler: async ({ text }) => {
        this.todos.push(text);
        console.log('[Todo] Added:', text);
        return { success: true, text };
      },
    });

    this.register({
      name: 'todo.list',
      description: 'List all todos',
      inputSchema: {
        type: 'object',
        properties: {},
      },
      handler: async () => {
        return { todos: [...this.todos] };
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
