export interface ChatToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface ChatRequest {
  systemPrompt: string;
  userMessage: string;
  context?: string[];
  tools?: ChatToolDefinition[];
}

export interface ChatResult {
  outputText: string;
}

export interface LLMClient {
  chat(request: ChatRequest): Promise<ChatResult>;
}
