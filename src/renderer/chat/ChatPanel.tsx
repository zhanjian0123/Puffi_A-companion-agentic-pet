import type { KeyboardEvent } from 'react';
import { PANEL_VISIBLE_MESSAGE_COUNT } from '../../shared/chatConfig';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatPanelProps {
  input: string;
  isLoading: boolean;
  messages: ChatMessage[];
  onChange: (value: string) => void;
  onClose: () => void;
  onSend: () => void;
}

export function ChatPanel({ input, isLoading, messages, onChange, onClose, onSend }: ChatPanelProps) {
  const visibleMessages = messages.slice(-PANEL_VISIBLE_MESSAGE_COUNT);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  };

  return (
    <>
      <div className="chat-header">
        <div className="chat-title">AI Pet</div>
        <button className="panel-close" onClick={onClose} type="button" aria-label="关闭悬浮窗">
          ×
        </button>
      </div>
      <div className="messages">
        {visibleMessages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`message ${message.role}`}>
            {message.content}
          </div>
        ))}
        {isLoading ? <div className="message assistant typing">...</div> : null}
      </div>

      <div className="input-area">
        <textarea
          value={input}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="和你的宠物聊天..."
          rows={3}
        />
        <button onClick={onSend} disabled={isLoading}>
          发送
        </button>
      </div>
    </>
  );
}
