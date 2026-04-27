import type { WebContents } from 'electron';
import type { PythonAgentClient, ReminderDueItem } from '../python/PythonAgentClient';

export interface ReminderSchedulerOptions {
  agentClient: PythonAgentClient;
  intervalMs?: number;
  onReminderDue: (reminder: ReminderDueItem) => Promise<WebContents | null>;
}

export class ReminderScheduler {
  private readonly intervalMs: number;
  private isChecking = false;
  private timer: NodeJS.Timeout | null = null;

  constructor(private readonly options: ReminderSchedulerOptions) {
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
      const result = await this.options.agentClient.dueReminders();
      for (const reminder of result.reminders) {
        const webContents = await this.options.onReminderDue(reminder);
        if (!webContents || webContents.isDestroyed()) {
          continue;
        }

        webContents.send('reminder:due', {
          id: reminder.id,
          title: reminder.title,
          remindAt: reminder.remind_at,
        });
        await this.options.agentClient.markReminderNotified(reminder.id);
      }
    } catch {
      // Python may be unavailable while the desktop shell is still alive; try again on the next tick.
    } finally {
      this.isChecking = false;
    }
  }
}
