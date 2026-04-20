import OpenAI from 'openai';
import type { ChatRequest, ChatResult, LLMClient } from '../client';

export interface DashScopeProviderOptions {
  apiKey: string;
  baseURL?: string;
  model: string;
}

export class DashScopeProvider implements LLMClient {
  private readonly client: OpenAI;

  constructor(private readonly options: DashScopeProviderOptions) {
    this.client = new OpenAI({
      apiKey: options.apiKey,
      baseURL: options.baseURL,
    });
  }

  async chat(request: ChatRequest): Promise<ChatResult> {
    const contextBlock = request.context?.length ? `\n\n上下文:\n${request.context.join('\n\n')}` : '';
    const completion = await this.client.chat.completions.create({
      model: this.options.model,
      messages: [
        { role: 'system', content: request.systemPrompt },
        { role: 'user', content: `${request.userMessage}${contextBlock}` },
      ],
    });

    return {
      outputText: completion.choices[0]?.message?.content ?? '',
    };
  }
}
