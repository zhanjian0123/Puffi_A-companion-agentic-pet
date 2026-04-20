import type { ReactNode } from 'react';

export interface AppShellProps {
  pet: ReactNode;
  chat: ReactNode;
}

export function AppShell({ pet, chat }: AppShellProps) {
  return (
    <div className="app">
      <div className="pet-container">{pet}</div>
      <div className="chat-container">{chat}</div>
    </div>
  );
}
