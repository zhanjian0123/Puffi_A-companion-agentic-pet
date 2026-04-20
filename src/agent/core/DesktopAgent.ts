import type { KnowledgeRetriever } from '../../knowledge/retrieve/types';
import type { ToolExecutor } from '../../tools/registry/types';
import type { LLMClient } from '../../llm/client';
import { buildSystemPrompt } from '../prompts/systemPrompt';

export interface AgentTurnInput {
  message: string;
}

export interface AgentTurnResult {
  response: string;
  citations: string[];
}

export interface DesktopAgentDeps {
  llmClient: LLMClient;
  retriever: KnowledgeRetriever;
  toolExecutor: ToolExecutor;
}

export class DesktopAgent {
  constructor(private readonly deps: DesktopAgentDeps) {}

  async runTurn(input: AgentTurnInput): Promise<AgentTurnResult> {
    const knowledgeHits = await this.deps.retriever.search(input.message, { limit: 3 });
    const tools = await this.deps.toolExecutor.list();
    const completion = await this.deps.llmClient.chat({
      systemPrompt: buildSystemPrompt(),
      userMessage: input.message,
      context: knowledgeHits.map((hit) => hit.content),
      tools,
    });

    return {
      response: completion.outputText,
      citations: knowledgeHits.map((hit) => hit.source),
    };
  }
}
