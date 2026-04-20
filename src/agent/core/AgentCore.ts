import OpenAI from 'openai';
import type { KnowledgeBase } from '../../knowledge/store/KnowledgeBase';
import type { MCPServer } from '../../tools/mcp/MCPServer';
import type { Tool, ToolRegistry } from '../../tools/registry/ToolRegistry';

export interface AgentConfig {
  knowledgeBase: KnowledgeBase;
  mcpServer: MCPServer;
  toolRegistry: ToolRegistry;
}

export class AgentCore {
  private client: OpenAI | null = null;
  private readonly systemPrompt: string;
  private readonly model: string;

  constructor(private readonly config: AgentConfig) {
    const apiKey = process.env.DASHSCOPE_API_KEY;
    const baseURL = process.env.DASHSCOPE_BASE_URL || 'https://dashscope.aliyuncs.com/compatible-mode/v1';
    this.model = process.env.DASHSCOPE_MODEL || 'qwen-plus';

    if (apiKey) {
      this.client = new OpenAI({
        apiKey,
        baseURL,
      });
    }

    this.systemPrompt = `你是一个桌面宠物助手，性格活泼可爱。
你可以帮助用户：
1. 回答问题和聊天
2. 管理个人知识库
3. 执行各种任务（通过工具）
4. 提醒和日程管理

保持回复简洁有趣，像一个真正的宠物伙伴。`;
  }

  async processMessage(message: string): Promise<{ response: string | null; action: any }> {
    const mcpTools = await this.config.mcpServer.listTools();
    const localTools = this.config.toolRegistry.list();
    const allTools = [...mcpTools, ...localTools];

    if (this.client) {
      return this.processWithDashScope(message, allTools);
    }

    return {
      response: '我还没有连接到 AI 服务。请配置 DASHSCOPE_API_KEY 或使用本地 Ollama。',
      action: null,
    };
  }

  async searchKnowledge(query: string): Promise<{ results: any[] }> {
    const results = await this.config.knowledgeBase.search(query);
    return { results };
  }

  async invokeTool(toolName: string, params: any): Promise<any> {
    const localTool = this.config.toolRegistry.get(toolName);
    if (localTool) {
      return localTool.handler(params);
    }

    return { error: 'Tool not found' };
  }

  private async processWithDashScope(message: string, tools: Tool[]): Promise<{ response: string | null; action: any }> {
    try {
      const completion = await this.client!.chat.completions.create({
        model: this.model,
        max_tokens: 1024,
        messages: [
          { role: 'system', content: this.systemPrompt },
          { role: 'user', content: message },
        ],
        tools: tools.length > 0
          ? tools.map((tool) => ({
              type: 'function' as const,
              function: {
                name: tool.name,
                description: tool.description,
                parameters: tool.inputSchema,
              },
            }))
          : undefined,
      });

      const assistantMessage = completion.choices[0]?.message;

      if (assistantMessage?.tool_calls && assistantMessage.tool_calls.length > 0) {
        const toolCall = assistantMessage.tool_calls[0];
        return {
          response: null,
          action: {
            type: 'tool_use',
            name: toolCall.function.name,
            input: JSON.parse(toolCall.function.arguments),
          },
        };
      }

      return {
        response: assistantMessage?.content ?? '',
        action: null,
      };
    } catch (error) {
      console.error('[Agent] Error processing message:', error);
      return {
        response: '出错了，请稍后再试。',
        action: null,
      };
    }
  }
}
