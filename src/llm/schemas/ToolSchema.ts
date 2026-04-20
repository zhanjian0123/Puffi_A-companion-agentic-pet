export interface ToolSchemaProperty {
  type: string;
  description: string;
}

export interface ToolSchema {
  type: 'object';
  properties: Record<string, ToolSchemaProperty>;
  required?: string[];
}
