import { BrowserWindow } from 'electron';
import type { PythonAgentClient, ScheduledTaskItem } from '../python/PythonAgentClient';

export interface ScheduledTaskRunnerOptions {
  agentClient: PythonAgentClient;
  intervalMs?: number;
  onTaskDue: (task: ScheduledTaskItem) => Promise<boolean>;
}

export class ScheduledTaskRunner {
  private readonly intervalMs: number;
  private readonly runningTaskIds = new Set<string>();
  private isChecking = false;
  private timer: NodeJS.Timeout | null = null;

  constructor(private readonly options: ScheduledTaskRunnerOptions) {
    this.intervalMs = options.intervalMs ?? 30_000;
  }

  start(): void {
    if (this.timer) {
      return;
    }

    this.timer = setInterval(() => {
      void this.check();
    }, this.intervalMs);
    void this.check();
  }

  stop(): void {
    if (!this.timer) {
      return;
    }

    clearInterval(this.timer);
    this.timer = null;
  }

  private async check(): Promise<void> {
    if (this.isChecking) {
      return;
    }

    this.isChecking = true;
    try {
      const result = await this.options.agentClient.dueScheduledTasks();
      for (const task of result.tasks) {
        if (this.runningTaskIds.has(task.id)) {
          continue;
        }

        void this.runTask(task);
      }
    } catch {
      // Python may be unavailable while the desktop shell is still alive; try again on the next tick.
    } finally {
      this.isChecking = false;
    }
  }

  private async runTask(task: ScheduledTaskItem): Promise<void> {
    this.runningTaskIds.add(task.id);

    try {
      const shouldRun = await this.options.onTaskDue(task);
      if (!shouldRun) {
        return;
      }

      const prompt = typeof task.action.prompt === 'string' ? task.action.prompt.trim() : '';
      if (!prompt) {
        await this.options.agentClient.markScheduledTaskCompleted(task.id, {
          success: false,
          error: '自动任务缺少 action.prompt。',
        });
        return;
      }

      sendScheduledTaskStatus({
        taskId: task.id,
        title: task.title,
        status: 'running',
      });

      const result = await this.options.agentClient.chat({
        message: prompt,
        mode: 'chat',
      });
      const response = result.response || '自动任务已执行，但没有返回可显示内容。';

      sendScheduledTaskStatus({
        taskId: task.id,
        title: task.title,
        status: 'done',
        content: response,
      });
      await this.options.agentClient.markScheduledTaskCompleted(task.id, {
        success: true,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : '自动任务执行失败。';
      sendScheduledTaskStatus({
        taskId: task.id,
        title: task.title,
        status: 'error',
        content: message,
      });
      try {
        await this.options.agentClient.markScheduledTaskCompleted(task.id, {
          success: false,
          error: message,
        });
      } catch {
        // Keep the runner alive; the task will be picked up again after Python is reachable.
      }
    } finally {
      this.runningTaskIds.delete(task.id);
    }
  }
}

function sendScheduledTaskStatus(payload: {
  taskId: string;
  title: string;
  status: 'running' | 'done' | 'error';
  content?: string;
}): void {
  for (const window of BrowserWindow.getAllWindows()) {
    if (!window.isDestroyed() && !window.webContents.isDestroyed()) {
      window.webContents.send('scheduled-task:status', payload);
    }
  }
}
