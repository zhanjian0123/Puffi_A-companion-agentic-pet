import React, { useState } from 'react';
import { getElectronApi } from './electronApi';
import { AppShell } from './app/AppShell';
import { ChatPanel, type ChatMessage } from './chat/ChatPanel';
import { PetAvatar } from './pet/PetAvatar';
import { usePetStore } from './store/petStore';
import { SHOW_PET_DEBUG } from '../main/app/devFlags';

export default function App() {
  const mode = new URLSearchParams(window.location.search).get('mode') === 'panel' ? 'panel' : 'pet';
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [debugStatus, setDebugStatus] = useState('idle');
  const emotion = usePetStore((state) => state.emotion);
  const { setEmotion, setAction } = usePetStore();

  const pushDebug = (message: string, payload?: unknown) => {
    const api = getElectronApi();
    setDebugStatus(message);
    console.log('[Renderer]', message, payload ?? '');
    void api?.debugLog(message, payload);
  };

  const setPanelOpen = async (nextOpen: boolean) => {
    const api = getElectronApi();
    pushDebug('setPanelOpen', { nextOpen });
    await api?.setPanelOpen(nextOpen);
  };

  const togglePanel = async () => {
    const api = getElectronApi();
    pushDebug('togglePanel');
    await api?.togglePanel();
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: ChatMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setAction('thinking');

    try {
      const api = getElectronApi();
      if (!api) {
        throw new Error('Electron API 未注入，preload 和 fallback 都没有生效。');
      }

      const response = await api.chat(input);

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
      mode={mode}
      pet={
        mode === 'pet' ? (
          <PetAvatar
            emotion={emotion}
            onActivate={() => void togglePanel()}
            onDebug={(message) => pushDebug(message)}
          />
        ) : undefined
      }
      chat={
        mode === 'panel' ? (
          <ChatPanel
            input={input}
            isLoading={isLoading}
            messages={messages}
            onChange={setInput}
            onClose={() => void setPanelOpen(false)}
            onSend={sendMessage}
          />
        ) : undefined
      }
      debug={mode === 'pet' && SHOW_PET_DEBUG ? debugStatus : undefined}
    />
  );
}
