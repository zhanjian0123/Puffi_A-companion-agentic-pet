export interface ToolDecision {
  shouldUseTool: boolean;
  toolName?: string;
  reason: string;
}

export function createNoToolDecision(reason: string): ToolDecision {
  return {
    shouldUseTool: false,
    reason,
  };
}
