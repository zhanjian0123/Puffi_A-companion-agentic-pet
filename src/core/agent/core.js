"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AgentCore = void 0;
const openai_1 = __importDefault(require("openai"));
class AgentCore {
    client = null;
    config;
    systemPrompt;
    model;
    constructor(config) {
        this.config = config;
        // 阿里云百炼平台配置
        const apiKey = process.env.DASHSCOPE_API_KEY;
        const baseURL = process.env.DASHSCOPE_BASE_URL || 'https://dashscope.aliyuncs.com/compatible-mode/v1';
        this.model = process.env.DASHSCOPE_MODEL || 'qwen-plus';
        if (apiKey) {
            this.client = new openai_1.default({
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
    async processMessage(message) {
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
    async processWithDashScope(message, tools) {
        try {
            const response = await this.client.chat.completions.create({
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
            const choice = response.choices[0];
            const message = choice.message;
            // 检查是否有工具调用
            if (message.tool_calls && message.tool_calls.length > 0) {
                const toolCall = message.tool_calls[0];
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
                response: message.content,
                action: null,
            };
        }
        catch (error) {
            console.error('[Agent] Error processing message:', error);
            return {
                response: '出错了，请稍后再试。',
                action: null,
            };
        }
    }
    async searchKnowledge(query) {
        // TODO: 实现 RAG 搜索
        return { results: [] };
    }
    async invokeTool(toolName, params) {
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
exports.AgentCore = AgentCore;
