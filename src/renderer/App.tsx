import React, { useState } from 'react';
import { usePetStore } from './store/petStore';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { setEmotion, setAction } = usePetStore();

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: ChatMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setAction('thinking');

    try {
      const response = await window.electronAPI?.chat(input);

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response?.response || '...'
      };
      setMessages((prev) => [...prev, assistantMessage]);

      setEmotion('happy');
      setAction('talking');
    } catch (error) {
      console.error('Chat error:', error);
    } finally {
      setIsLoading(false);
      setAction('idle');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="app">
      <div className="pet-container">
        <div className={`pet ${usePetStore().emotion}`}>
          <div className="pet-body">
            <div className="pet-eyes">
              <div className="eye left"></div>
              <div className="eye right"></div>
            </div>
            <div className="pet-mouth"></div>
          </div>
        </div>
      </div>

      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              {msg.content}
            </div>
          ))}
          {isLoading && <div className="message assistant typing">...</div>}
        </div>

        <div className="input-area">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="和你的宠物聊天..."
            rows={3}
          />
          <button onClick={sendMessage} disabled={isLoading}>
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
