import { useEffect, useState } from 'react';
import { getElectronApi, requireElectronApi } from './electronApi';
import { ChatPanel, type ChatMessage } from './chat/ChatPanel';
import { PetAvatar } from './pet/PetAvatar';
import { ENABLE_DESKTOP_DEBUG_LOGS } from '../shared/devFlags';
import { PANEL_VISIBLE_MESSAGE_COUNT } from '../shared/chatConfig';

type PetEmotion = 'happy' | 'neutral' | 'sad';

export default function App() {
  const mode = new URLSearchParams(window.location.search).get('mode') === 'panel' ? 'panel' : 'pet';
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [emotion, setEmotion] = useState<PetEmotion>('neutral');

  useEffect(() => {
    if (ENABLE_DESKTOP_DEBUG_LOGS) {
      console.log('[Renderer] App mounted', {
        mode,
        hasElectronApi: !!getElectronApi(),
      });
    }
  }, [mode]);

  useEffect(() => {
    if (mode !== 'panel') {
      return;
    }

    let isCancelled = false;

    const loadHistory = async () => {
      try {
        const response = await requireElectronApi().history(PANEL_VISIBLE_MESSAGE_COUNT);
        if (!isCancelled) {
          setMessages(response.messages);
        }
      } catch (error) {
        console.error('Load history error:', error);
      }
    };

    void loadHistory();

    return () => {
      isCancelled = true;
    };
  }, [mode]);

  const setPanelOpen = async (nextOpen: boolean) => {
    await requireElectronApi().setPanelOpen(nextOpen);
  };

  const togglePanel = async () => {
    await requireElectronApi().togglePanel();
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
      const response = await requireElectronApi().chat(message);

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
