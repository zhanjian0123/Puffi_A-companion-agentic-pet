import React, { useState } from 'react';
import { AppShell } from './app/AppShell';
import { ChatPanel, type ChatMessage } from './chat/ChatPanel';
import { PetAvatar } from './pet/PetAvatar';
import { usePetStore } from './store/petStore';

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const emotion = usePetStore((state) => state.emotion);
  const { setEmotion, setAction } = usePetStore();

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: ChatMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setAction('thinking');

    try {
      if (!window.electronAPI) {
        throw new Error('Electron API 未注入，preload 可能没有生效。');
      }

      const response = await window.electronAPI.chat(input);

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response?.response || '...'
      };
      setMessages((prev) => [...prev, assistantMessage]);

      setEmotion('happy');
      setAction('talking');
    } catch (error) {
      console.error('Chat error:', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: error instanceof Error ? error.message : '发送消息失败，请稍后再试。',
        },
      ]);
      setEmotion('sad');
    } finally {
      setIsLoading(false);
      setAction('idle');
    }
  };

  return (
    <AppShell
      pet={<PetAvatar emotion={emotion} />}
      chat={
        <ChatPanel
          input={input}
          isLoading={isLoading}
          messages={messages}
          onChange={setInput}
          onSend={sendMessage}
        />
      }
    />
  );
}
