import { useEffect, useRef, useState } from 'react';
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
  const activeStreamRef = useRef<{ assistantMessageId: string; requestId: string } | null>(null);
  const pendingDeltaRef = useRef('');
  const flushTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (ENABLE_DESKTOP_DEBUG_LOGS) {
      console.log('[Renderer] App mounted', {
        mode,
        hasElectronApi: !!getElectronApi(),
      });
    }
  }, [mode]);

  useEffect(() => {
    const unsubscribe = requireElectronApi().onChatStreamEvent((event) => {
      const activeStream = activeStreamRef.current;
      if (!activeStream || event.requestId !== activeStream.requestId) {
        return;
      }

      if (event.type === 'delta') {
        pendingDeltaRef.current += event.delta ?? '';
        scheduleStreamFlush();
        return;
      }

      if (event.type === 'error') {
        flushPendingDelta();
        setMessages((prev) =>
          prev.map((message) =>
            message.id === activeStream.assistantMessageId
              ? {
                  ...message,
                  content: event.message || '发送消息失败，请稍后再试。',
                  streaming: false,
                }
              : message
          )
        );
        activeStreamRef.current = null;
        setIsLoading(false);
        setEmotion('sad');
        return;
      }

      flushPendingDelta();
      setMessages((prev) =>
        prev.map((message) =>
          message.id === activeStream.assistantMessageId
            ? {
                ...message,
                streaming: false,
              }
            : message
        )
      );
      activeStreamRef.current = null;
      setIsLoading(false);
      setEmotion('happy');
    });

    return () => {
      clearFlushTimer();
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (mode !== 'panel') {
      return;
    }

    let isCancelled = false;

    const loadHistory = async () => {
      try {
        const response = await requireElectronApi().history(PANEL_VISIBLE_MESSAGE_COUNT);
        if (!isCancelled) {
          setMessages(
            response.messages.map((message) => ({
              id: createMessageId(),
              streaming: false,
              ...message,
            }))
          );
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

    const userMessage: ChatMessage = { id: createMessageId(), role: 'user', content: message };
    const assistantMessage: ChatMessage = {
      id: createMessageId(),
      role: 'assistant',
      content: '',
      streaming: true,
    };
    const requestId = createMessageId();

    activeStreamRef.current = {
      requestId,
      assistantMessageId: assistantMessage.id,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput('');
    setIsLoading(true);

    try {
      await requireElectronApi().startChatStream({ message, requestId });
    } catch (error) {
      console.error('Chat error:', error);
      setMessages((prev) =>
        prev.map((existingMessage) =>
          existingMessage.id === assistantMessage.id
            ? {
                ...existingMessage,
                content: error instanceof Error ? error.message : '发送消息失败，请稍后再试。',
                streaming: false,
              }
            : existingMessage
        )
      );
      clearFlushTimer();
      pendingDeltaRef.current = '';
      activeStreamRef.current = null;
      setEmotion('sad');
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

  function scheduleStreamFlush() {
    if (flushTimerRef.current !== null) {
      return;
    }

    flushTimerRef.current = window.setTimeout(() => {
      flushTimerRef.current = null;
      flushPendingDelta();
    }, 40);
  }

  function clearFlushTimer() {
    if (flushTimerRef.current !== null) {
      window.clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
  }

  function flushPendingDelta() {
    const activeStream = activeStreamRef.current;
    const delta = pendingDeltaRef.current;

    if (!activeStream || !delta) {
      pendingDeltaRef.current = '';
      return;
    }

    pendingDeltaRef.current = '';
    setMessages((prev) =>
      prev.map((message) =>
        message.id === activeStream.assistantMessageId
          ? { ...message, content: `${message.content}${delta}` }
          : message
      )
    );
  }
}

function createMessageId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
