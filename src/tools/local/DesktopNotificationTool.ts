import type { ToolDefinition } from '../registry/types';

export const desktopNotificationTool: ToolDefinition = {
  name: 'system.notify',
  description: 'Send a desktop notification to the user.',
  inputSchema: {
    type: 'object',
    properties: {
      title: { type: 'string' },
      body: { type: 'string' },
    },
  },
};
