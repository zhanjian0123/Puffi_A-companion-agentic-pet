import { Document } from 'langchain/document';

export interface KnowledgeChunk {
  id: string;
  content: string;
  metadata: {
    source: string;
    type: string;
    createdAt: number;
  };
}

export class KnowledgeBase {
  private documents: KnowledgeChunk[] = [];
  private dbPath: string;

  constructor(dbPath: string) {
    this.dbPath = dbPath;
  }

  async initialize() {
    console.log('[KB] Knowledge base initialized (memory mode)');
    // TODO: 持久化到本地
  }

  async addDocument(doc: Document) {
    const chunk: KnowledgeChunk = {
      id: crypto.randomUUID(),
      content: doc.pageContent,
      metadata: {
        source: doc.metadata.source || 'unknown',
        type: doc.metadata.type || 'text',
        createdAt: Date.now(),
      },
    };

    this.documents.push(chunk);
    console.log(`[KB] Added document: ${doc.metadata.source}`);
  }

  async search(query: string, limit: number = 5): Promise<Document[]> {
    // 简单的关键词匹配 (后续可替换为向量搜索)
    const queryLower = query.toLowerCase();

    const results = this.documents
      .filter(doc => doc.content.toLowerCase().includes(queryLower))
      .slice(0, limit);

    return results.map(r => ({
      pageContent: r.content,
      metadata: r.metadata,
    }));
  }

  async addText(text: string, source?: string) {
    const chunks = this.chunkText(text);

    for (const chunk of chunks) {
      await this.addDocument(
        new Document({
          pageContent: chunk,
          metadata: { source: source || 'manual', type: 'text' },
        })
      );
    }
  }

  private chunkText(text: string, size: number = 500): string[] {
    const chunks: string[] = [];
    for (let i = 0; i < text.length; i += size) {
      chunks.push(text.slice(i, i + size));
    }
    return chunks;
  }

  getDocumentCount(): number {
    return this.documents.length;
  }
}
