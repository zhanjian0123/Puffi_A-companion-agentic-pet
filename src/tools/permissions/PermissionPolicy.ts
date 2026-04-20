export type PermissionLevel = 'allow' | 'confirm' | 'deny';

export interface PermissionRule {
  toolName: string;
  level: PermissionLevel;
}

export class PermissionPolicy {
  constructor(private readonly rules: PermissionRule[]) {}

  getLevel(toolName: string): PermissionLevel {
    const rule = this.rules.find((item) => item.toolName === toolName);
    return rule?.level ?? 'confirm';
  }
}
