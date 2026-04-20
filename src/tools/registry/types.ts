export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface ToolExecutionRequest {
  toolName: string;
  input: unknown;
}

export interface ToolExecutionResult {
  success: boolean;
  output: unknown;
}

export interface ToolExecutor {
  list(): Promise<ToolDefinition[]>;
  execute(request: ToolExecutionRequest): Promise<ToolExecutionResult>;
}
