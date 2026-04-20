import type { ToolDefinition, ToolExecutionRequest, ToolExecutionResult, ToolExecutor } from './types';

export class ToolCatalog implements ToolExecutor {
  private readonly tools = new Map<string, ToolDefinition>();

  register(tool: ToolDefinition): void {
    this.tools.set(tool.name, tool);
  }

  async list(): Promise<ToolDefinition[]> {
    return Array.from(this.tools.values());
  }

  async execute(request: ToolExecutionRequest): Promise<ToolExecutionResult> {
    const tool = this.tools.get(request.toolName);
    if (!tool) {
      return {
        success: false,
        output: { error: `Tool not found: ${request.toolName}` },
      };
    }

    return {
      success: true,
      output: {
        tool: tool.name,
        input: request.input,
      },
    };
  }
}
