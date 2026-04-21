export interface PythonAgentClientOptions {
  baseUrl: string;
}

export interface HealthResult {
  configured: boolean;
  runtime: string;
  status: string;
}

export interface ChatResult {
  response: string | null;
  action?: unknown;
}

export class PythonAgentClient {
  constructor(private readonly options: PythonAgentClientOptions) {}

  async health(): Promise<HealthResult> {
    return this.requestJson<HealthResult>('/health');
  }

  async chat(message: string): Promise<ChatResult> {
    return this.requestJson<ChatResult>('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
  }

  private async readJson<T>(response: Response): Promise<T> {
    if (!response.ok) {
      throw new Error(`Python agent request failed: ${response.status} ${response.statusText}`);
    }

    return (await response.json()) as T;
  }

  private async requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    try {
      const response = await fetch(`${this.options.baseUrl}${path}`, init);
      return this.readJson<T>(response);
    } catch (error) {
      if (error instanceof Error && error.message === 'fetch failed') {
        throw new Error(
          `Python agent service is not reachable at ${this.options.baseUrl}. ` +
            'Please start the Python backend with `npm run dev:python`.'
        );
      }

      throw error;
    }
  }
}
