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

export interface ChatPayload {
  message: string;
  mode?: string;
}

export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface HistoryResult {
  messages: HistoryMessage[];
}

export interface ChatStreamChunk {
  type: 'delta' | 'done' | 'error';
  delta?: string;
  message?: string;
}

export class PythonAgentClient {
  constructor(private readonly options: PythonAgentClientOptions) {}

  async health(): Promise<HealthResult> {
    return this.requestJson<HealthResult>('/health');
  }

  async chat(payload: ChatPayload): Promise<ChatResult> {
    return this.requestJson<ChatResult>('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  async history(limit?: number): Promise<HistoryResult> {
    const search = typeof limit === 'number' ? `?limit=${encodeURIComponent(limit)}` : '';
    return this.requestJson<HistoryResult>(`/history${search}`);
  }

  async *chatStream(payload: ChatPayload): AsyncGenerator<ChatStreamChunk> {
    let response: Response;

    try {
      response = await fetch(`${this.options.baseUrl}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      if (error instanceof Error && error.message === 'fetch failed') {
        throw new Error(
          `Python agent service is not reachable at ${this.options.baseUrl}. ` +
            'Please start the Python backend with `npm run dev:python`.'
        );
      }

      throw error;
    }

    if (!response.ok) {
      throw new Error(`Python agent request failed: ${response.status} ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error('Python agent stream returned an empty response body.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
          continue;
        }

        yield JSON.parse(trimmed) as ChatStreamChunk;
      }
    }

    buffer += decoder.decode();
    const trailingLine = buffer.trim();
    if (trailingLine) {
      yield JSON.parse(trailingLine) as ChatStreamChunk;
    }
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
