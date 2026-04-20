export interface MemoryMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
}

export class ConversationMemory {
  private readonly messages: MemoryMessage[] = [];

  append(message: MemoryMessage): void {
    this.messages.push(message);
  }

  getRecent(limit = 12): MemoryMessage[] {
    return this.messages.slice(-limit);
  }

  clear(): void {
    this.messages.length = 0;
  }
}
