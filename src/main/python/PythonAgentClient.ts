import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import http from 'node:http';
import https from 'node:https';
import path from 'node:path';

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

export interface KnowledgeUploadResult {
  message: string;
  filename: string;
  imported: number;
  skipped: number;
  failed: number;
}

export interface ReminderDueItem {
  id: string;
  title: string;
  remind_at: string;
  completed: boolean;
  created_at: string;
  completed_at?: string | null;
  notified_at?: string | null;
}

export interface RemindersDueResult {
  reminders: ReminderDueItem[];
}

export interface ReminderNotifiedResult {
  success: boolean;
  reminder?: ReminderDueItem | null;
  message: string;
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

  async dueReminders(): Promise<RemindersDueResult> {
    return this.requestJson<RemindersDueResult>('/reminders/due');
  }

  async markReminderNotified(reminderId: string): Promise<ReminderNotifiedResult> {
    return this.requestJson<ReminderNotifiedResult>(
      `/reminders/${encodeURIComponent(reminderId)}/notified`,
      {
        method: 'POST',
      }
    );
  }

  async uploadKnowledgeFile(
    filePath: string,
    onProgress?: (progress: number) => void
  ): Promise<KnowledgeUploadResult> {
    const fileStat = await stat(filePath);
    if (!fileStat.isFile()) {
      throw new Error('Only regular files can be uploaded to the knowledge base.');
    }

    const target = new URL('/knowledge/upload', this.options.baseUrl);
    const boundary = `----ai-pet-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const filename = path.basename(filePath).replace(/"/g, '\\"');
    const preamble = Buffer.from(
      `--${boundary}\r\n` +
        `Content-Disposition: form-data; name="file"; filename="${filename}"\r\n` +
        `Content-Type: application/octet-stream\r\n\r\n`
    );
    const closing = Buffer.from(`\r\n--${boundary}--\r\n`);
    const contentLength = preamble.length + fileStat.size + closing.length;
    const transport = target.protocol === 'https:' ? https : http;

    return new Promise<KnowledgeUploadResult>((resolve, reject) => {
      const request = transport.request(
        {
          method: 'POST',
          hostname: target.hostname,
          port: target.port,
          path: `${target.pathname}${target.search}`,
          headers: {
            'Content-Type': `multipart/form-data; boundary=${boundary}`,
            'Content-Length': contentLength,
          },
        },
        (response) => {
          const chunks: Buffer[] = [];

          response.on('data', (chunk: Buffer) => {
            chunks.push(chunk);
          });

          response.on('end', () => {
            const body = Buffer.concat(chunks).toString('utf-8');
            const statusCode = response.statusCode ?? 0;
            if (statusCode < 200 || statusCode >= 300) {
              reject(new Error(parseErrorMessage(body, statusCode)));
              return;
            }

            try {
              resolve(JSON.parse(body) as KnowledgeUploadResult);
            } catch (error) {
              reject(error);
            }
          });
        }
      );

      request.on('error', reject);
      request.write(preamble);
      onProgress?.(0);

      let uploadedBytes = 0;
      const stream = createReadStream(filePath);

      stream.on('data', (chunk: string | Buffer) => {
        const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        uploadedBytes += buffer.length;
        const progress = fileStat.size > 0 ? Math.round((uploadedBytes / fileStat.size) * 100) : 100;
        const canContinue = request.write(buffer);
        onProgress?.(Math.min(progress, 100));

        if (!canContinue) {
          stream.pause();
          request.once('drain', () => {
            stream.resume();
          });
        }
      });

      stream.on('error', (error) => {
        request.destroy(error);
      });

      stream.on('end', () => {
        onProgress?.(100);
        request.end(closing);
      });
    });
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

function parseErrorMessage(body: string, statusCode: number): string {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === 'string') {
      return parsed.detail;
    }
  } catch {
    // Fall through to the generic message below.
  }

  return `Knowledge upload failed: ${statusCode}`;
}
