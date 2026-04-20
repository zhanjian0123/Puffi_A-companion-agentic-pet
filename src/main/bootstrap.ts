import { AgentCore } from '../agent/core/AgentCore';
import { KnowledgeBase } from '../knowledge/store/KnowledgeBase';
import { MCPServer } from '../tools/mcp/MCPServer';
import { ToolRegistry } from '../tools/registry/ToolRegistry';

export interface AppServices {
  agentCore: AgentCore;
  knowledgeBase: KnowledgeBase;
  mcpServer: MCPServer;
  toolRegistry: ToolRegistry;
}

export async function bootstrapApp(): Promise<AppServices> {
  const knowledgeBasePath = process.env.KNOWLEDGE_BASE_PATH || './knowledge';
  const knowledgeBase = new KnowledgeBase(knowledgeBasePath);
  await knowledgeBase.initialize();

  const mcpServer = new MCPServer();
  await mcpServer.initialize();

  const toolRegistry = new ToolRegistry({
    searchKnowledge: async (query) => {
      return knowledgeBase.search(query);
    },
  });
  toolRegistry.registerDefaults();

  const agentCore = new AgentCore({
    knowledgeBase,
    mcpServer,
    toolRegistry,
  });

  return {
    agentCore,
    knowledgeBase,
    mcpServer,
    toolRegistry,
  };
}
