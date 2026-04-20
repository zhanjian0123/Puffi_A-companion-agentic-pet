import OpenAI from 'openai';
import { MCPServer } from '../../main/mcp/server';
import { ToolRegistry } from '../../main/tools/registry';

export interface AgentConfig {
  mcpServer: MCPServer;
  toolRegistry: ToolRegistry;
}

export class AgentCore {
  private client: OpenAI | null = null;
  private config: AgentConfig;
  private systemPrompt: string;
  private model: string;

  constructor(config: AgentConfig) {
    this.config = config;

    // 阿里云百炼平台配置
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

  async processMessage(message: string): Promise<any> {
    // 获取可用工具
    const mcpTools = await this.config.mcpServer.listTools();
    const localTools = this.config.toolRegistry.list();
    const allTools = [...mcpTools, ...localTools];

    // 如果有 API key，使用阿里云百炼
    if (this.client) {
      return this.processWithDashScope(message, allTools);
    }

    // 否则返回本地响应
    return {
      response: '我还没有连接到 AI 服务。请配置 DASHSCOPE_API_KEY 或使用本地 Ollama。',
      action: null,
    };
  }

  private async processWithDashScope(message: string, tools: any[]) {
    try {
      const completion = await this.client!.chat.completions.create({
        model: this.model,
        max_tokens: 1024,
        messages: [
          { role: 'system', content: this.systemPrompt },
          { role: 'user', content: message },
        ],
        tools: tools.length > 0 ? tools.map((t) => ({
          type: 'function',
          function: {
            name: t.name,
            description: t.description,
            parameters: { type: 'object', properties: {} },
          },
        })) : undefined,
      });

      const choice = completion.choices[0];
      const assistantMessage = choice.message;

      // 检查是否有工具调用
      if (assistantMessage.tool_calls && assistantMessage.tool_calls.length > 0) {
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
        response: assistantMessage.content,
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

  async searchKnowledge(query: string) {
    // TODO: 实现 RAG 搜索
    return { results: [] };
  }

  async invokeTool(toolName: string, params: any) {
    // 先尝试本地工具
    const localTool = this.config.toolRegistry.get(toolName);
    if (localTool) {
      return localTool.handler(params);
    }

    // 再尝试 MCP 工具
    // TODO: 解析 toolName 获取 serverName
    return { error: 'Tool not found' };
  }
}
