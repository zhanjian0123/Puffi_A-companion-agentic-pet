import type { ChatRequest, ChatResult, LLMClient } from '../client';

export interface OllamaProviderOptions {
  baseURL: string;
  model: string;
}

export class OllamaProvider implements LLMClient {
  constructor(private readonly options: OllamaProviderOptions) {}

  async chat(request: ChatRequest): Promise<ChatResult> {
    const summary = [
      `Ollama provider placeholder for model ${this.options.model}.`,
      `Base URL: ${this.options.baseURL}.`,
      `User message: ${request.userMessage}`,
    ].join(' ');

    return { outputText: summary };
  }
}
