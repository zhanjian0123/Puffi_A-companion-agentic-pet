import { useState } from 'react';
import { getElectronApi } from './electronApi';
import { ChatPanel, type ChatMessage } from './chat/ChatPanel';
import { PetAvatar } from './pet/PetAvatar';

type PetEmotion = 'happy' | 'neutral' | 'sad';

export default function App() {
  const mode = new URLSearchParams(window.location.search).get('mode') === 'panel' ? 'panel' : 'pet';
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [emotion, setEmotion] = useState<PetEmotion>('neutral');

  const setPanelOpen = async (nextOpen: boolean) => {
    const api = getElectronApi();
    await api?.setPanelOpen(nextOpen);
  };

  const togglePanel = async () => {
    const api = getElectronApi();
    await api?.togglePanel();
  };

  const sendMessage = async () => {
    const message = input.trim();
    if (!message) {
      return;
    }

    const userMessage: ChatMessage = { role: 'user', content: message };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const api = getElectronApi();
      if (!api) {
        throw new Error('Electron preload API 未注入，请检查桌面端主进程是否正常启动。');
      }

      const response = await api.chat(message);

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response?.response || '...',
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setEmotion('happy');
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
    }
  };

  if (mode === 'panel') {
    return (
      <div className="app panel-window">
        <div className="chat-popover">
          <ChatPanel
            input={input}
            isLoading={isLoading}
            messages={messages}
            onChange={setInput}
            onClose={() => void setPanelOpen(false)}
            onSend={sendMessage}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="app pet-window">
      <div className="pet-stage">
        <div className="pet-container">
          <PetAvatar emotion={emotion} onActivate={() => void togglePanel()} />
        </div>
      </div>
    </div>
  );
}
