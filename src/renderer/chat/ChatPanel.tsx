import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent } from 'react';
import { PANEL_VISIBLE_MESSAGE_COUNT } from '../../shared/chatConfig';
import { MarkdownMessage } from './MarkdownMessage';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  streaming?: boolean;
}

export interface ChatPanelProps {
  input: string;
  isLoading: boolean;
  messages: ChatMessage[];
  onChange: (value: string) => void;
  onClose: () => void;
  onSend: () => void;
  onUploadFile: (file: File) => void;
  uploadPhase: 'uploading' | 'processing' | null;
  uploadProgress: number | null;
}

export function ChatPanel({
  input,
  isLoading,
  messages,
  onChange,
  onClose,
  onSend,
  onUploadFile,
  uploadPhase,
  uploadProgress,
}: ChatPanelProps) {
  const visibleMessages = messages.slice(-PANEL_VISIBLE_MESSAGE_COUNT);
  const messageViewportRef = useRef<HTMLDivElement | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);

  useEffect(() => {
    const viewport = messageViewportRef.current;
    if (!viewport) {
      return;
    }

    viewport.scrollTop = viewport.scrollHeight;
  }, [visibleMessages, isLoading]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    setIsDragActive(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    const nextTarget = event.relatedTarget;
    if (!(nextTarget instanceof Node) || !event.currentTarget.contains(nextTarget)) {
      setIsDragActive(false);
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragActive(false);

    const file = event.dataTransfer.files.item(0);
    if (file) {
      onUploadFile(file);
    }
  };

  const progress = uploadProgress ?? 0;

  return (
    <div
      className={`chat-drop-surface ${isDragActive ? 'drag-active' : ''}`}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {uploadPhase && (
        <div className={`upload-progress ${uploadPhase}`} aria-hidden="true">
          <div className="upload-progress-bar" style={{ width: `${Math.max(0, Math.min(progress, 100))}%` }} />
        </div>
      )}
      <div className="chat-header">
        <div className="chat-title">AI Pet</div>
        <button className="panel-close" onClick={onClose} type="button" aria-label="关闭悬浮窗">
          ×
        </button>
      </div>
      <div className="messages" ref={messageViewportRef}>
        {visibleMessages.map((message, index) => (
          <div key={message.id} className={`message ${message.role}`}>
            {isLoading &&
            message.role === 'assistant' &&
            !message.content &&
            index === visibleMessages.length - 1 ? (
              <div className="message-status typing">...</div>
            ) : message.streaming ? (
              <div className="streaming-message">{message.content}</div>
            ) : (
              <MarkdownMessage content={message.content} />
            )}
          </div>
        ))}
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
    </div>
  );
}
