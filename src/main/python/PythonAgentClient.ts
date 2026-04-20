export interface PythonAgentClientOptions {
  baseUrl: string;
}

export interface ChatResult {
  response: string | null;
  action?: unknown;
}

export class PythonAgentClient {
  constructor(private readonly options: PythonAgentClientOptions) {}

  async health(): Promise<{ status: string }> {
    const response = await fetch(`${this.options.baseUrl}/health`);
    return this.readJson<{ status: string }>(response);
  }

  async chat(message: string): Promise<ChatResult> {
    const response = await fetch(`${this.options.baseUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    return this.readJson<ChatResult>(response);
  }

  async searchKnowledge(query: string, limit = 5): Promise<{ results: unknown[] }> {
    const response = await fetch(`${this.options.baseUrl}/knowledge/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit }),
    });
    return this.readJson<{ results: unknown[] }>(response);
  }

  async invokeTool(toolName: string, params: Record<string, unknown>): Promise<{ result: unknown }> {
    const response = await fetch(`${this.options.baseUrl}/tools/invoke`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ toolName, params }),
    });
    return this.readJson<{ result: unknown }>(response);
  }

  private async readJson<T>(response: Response): Promise<T> {
    if (!response.ok) {
      throw new Error(`Python agent request failed: ${response.status} ${response.statusText}`);
    }

    return (await response.json()) as T;
  }
}
