import type { ReactNode } from 'react';

export interface AppShellProps {
  mode: 'panel' | 'pet';
  pet?: ReactNode;
  chat?: ReactNode;
  debug?: string;
}

export function AppShell({ mode, pet, chat, debug }: AppShellProps) {
  return (
    <div className={`app ${mode === 'panel' ? 'panel-window' : 'pet-window'}`}>
      {mode === 'panel' ? <div className="chat-popover">{chat}</div> : null}
      {mode === 'pet' ? (
        <div className="pet-stage">
          <div className="pet-container">{pet}</div>
          {debug ? <div className="debug-chip">{debug}</div> : null}
        </div>
      ) : null}
    </div>
  );
}
