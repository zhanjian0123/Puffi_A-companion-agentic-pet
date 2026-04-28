import { useCallback, useEffect, useRef, useState } from 'react';
import { PANEL_VISIBLE_MESSAGE_COUNT } from '../../shared/chatConfig';
import type { PetState } from '../../shared/types';
import { requireElectronApi } from '../electronApi';
import type { ChatMessage } from './ChatPanel';

interface UseChatMessagesOptions {
  agentMode: string;
  shouldLoadHistory: boolean;
  onDone?: () => void;
  onError?: () => void;
  onPetState?: (state: PetState) => void;
}

interface ActiveStream {
  assistantMessageId: string;
  requestId: string;
}

export function useChatMessages({
  agentMode,
  shouldLoadHistory,
  onDone,
  onError,
  onPetState,
}: UseChatMessagesOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const activeStreamRef = useRef<ActiveStream | null>(null);
  const pendingDeltaRef = useRef('');
  const flushTimerRef = useRef<number | null>(null);

  const clearFlushTimer = useCallback(() => {
    if (flushTimerRef.current !== null) {
      window.clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
  }, []);

  const flushPendingDelta = useCallback(() => {
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
  }, []);

  const scheduleStreamFlush = useCallback(() => {
    if (flushTimerRef.current !== null) {
      return;
    }

    flushTimerRef.current = window.setTimeout(() => {
      flushTimerRef.current = null;
      flushPendingDelta();
    }, 40);
  }, [flushPendingDelta]);

  const appendAssistantMessage = useCallback((content: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: createMessageId(),
        role: 'assistant',
        content,
      },
    ]);
  }, []);

  useEffect(() => {
    const unsubscribeChat = requireElectronApi().onChatStreamEvent((event) => {
      const activeStream = activeStreamRef.current;
      if (!activeStream || event.requestId !== activeStream.requestId) {
        if (event.pet_state) {
          onPetState?.(event.pet_state);
        }
        return;
      }

      if (event.pet_state) {
        onPetState?.(event.pet_state);
      }

      if (event.type === 'state') {
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
        onError?.();
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
      onDone?.();
    });

    return () => {
      clearFlushTimer();
      unsubscribeChat();
    };
  }, [clearFlushTimer, flushPendingDelta, onDone, onError, onPetState, scheduleStreamFlush]);

  useEffect(() => {
    if (!shouldLoadHistory) {
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
  }, [shouldLoadHistory]);

  const sendMessage = useCallback(async () => {
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
    onPetState?.('thinking');

    try {
      await requireElectronApi().startChatStream({
        message,
        mode: agentMode,
        requestId,
      });
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
      onPetState?.('error');
      onError?.();
      setIsLoading(false);
    }
  }, [agentMode, clearFlushTimer, input, onError, onPetState]);

  return {
    appendAssistantMessage,
    input,
    isLoading,
    messages,
    sendMessage,
    setInput,
  };
}

function createMessageId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
