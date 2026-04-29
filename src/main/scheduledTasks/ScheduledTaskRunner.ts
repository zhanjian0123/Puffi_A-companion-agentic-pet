import { BrowserWindow } from 'electron';
import type { PythonAgentClient, ScheduledTaskItem } from '../python/PythonAgentClient';

export interface ScheduledTaskRunnerOptions {
  agentClient: PythonAgentClient;
  intervalMs?: number;
  onTaskDue: (task: ScheduledTaskItem) => Promise<boolean>;
  onTaskFinished?: (task: ScheduledTaskItem, status: 'done' | 'error') => Promise<void>;
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
    let runId: string | null = null;

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

      const run = await this.options.agentClient.createScheduledTaskRun({
        task_id: task.id,
        task_title: task.title,
        prompt,
      });
      runId = run.run?.id ?? null;

      sendScheduledTaskStatus({
        taskId: task.id,
        runId,
        title: task.title,
        status: 'running',
      });

      const result = await this.options.agentClient.chat({
        message: buildScheduledTaskPrompt(task, prompt),
        mode: 'scheduled',
      });
      const response = result.response || '自动任务已执行，但没有返回可显示内容。';

      if (runId) {
        await this.options.agentClient.finishScheduledTaskRun(runId, {
          status: 'success',
          response,
        });
      }
      await this.options.agentClient.markScheduledTaskCompleted(task.id, {
        success: true,
      });
      await this.options.onTaskFinished?.(task, 'done');
      sendScheduledTaskStatus({
        taskId: task.id,
        runId,
        title: task.title,
        status: 'done',
        content: response,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : '自动任务执行失败。';
      try {
        if (runId) {
          await this.options.agentClient.finishScheduledTaskRun(runId, {
            status: 'error',
            error: message,
          });
        }
        await this.options.agentClient.markScheduledTaskCompleted(task.id, {
          success: false,
          error: message,
        });
      } catch {
        // Keep the runner alive; the task will be picked up again after Python is reachable.
      }
      await this.options.onTaskFinished?.(task, 'error');
      sendScheduledTaskStatus({
        taskId: task.id,
        runId,
        title: task.title,
        status: 'error',
        content: message,
      });
    } finally {
      this.runningTaskIds.delete(task.id);
    }
  }
}

function buildScheduledTaskPrompt(task: ScheduledTaskItem, prompt: string): string {
  return [
    '这是一个自动定时任务，不是用户正在实时对话。',
    '',
    `任务标题：${task.title}`,
    `任务 ID：${task.id}`,
    `执行时间：${new Date().toISOString()}`,
    '',
    '用户设定的任务：',
    prompt,
    '',
    '请完成任务，并输出适合桌面通知和历史记录查看的结果：',
    '1. 先给 1 句摘要。',
    '2. 再给关键内容。',
    '3. 如果使用了外部搜索，列出来源。',
    '4. 不要询问用户是否继续，除非任务无法完成。',
  ].join('\n');
}

function sendScheduledTaskStatus(payload: {
  taskId: string;
  runId?: string | null;
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
