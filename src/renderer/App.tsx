import { useCallback, useEffect, useRef, useState } from 'react';
import { getElectronApi, requireElectronApi } from './electronApi';
import { ChatPanel } from './chat/ChatPanel';
import { useChatMessages } from './chat/useChatMessages';
import { useKnowledgeUpload } from './chat/useKnowledgeUpload';
import { PetAvatar, type PetMood } from './pet/PetAvatar';
import { ENABLE_DESKTOP_DEBUG_LOGS } from '../shared/devFlags';
import type { PetState, ReminderDueEvent } from '../shared/types';

type PetEmotion = 'happy' | 'neutral' | 'sad';
const DEFAULT_AGENT_MODE = 'chat';

export default function App() {
  const mode = new URLSearchParams(window.location.search).get('mode') === 'panel' ? 'panel' : 'pet';
  const [emotion, setEmotion] = useState<PetEmotion>('neutral');
  const [petMood, setPetMood] = useState<PetMood>('idle');
  const [reminderNotice, setReminderNotice] = useState<ReminderDueEvent | null>(null);
  const petMoodRef = useRef<PetMood>('idle');
  const moodTimerRef = useRef<number | null>(null);
  const reminderTimerRef = useRef<number | null>(null);

  const clearMoodTimer = useCallback(() => {
    if (moodTimerRef.current !== null) {
      window.clearTimeout(moodTimerRef.current);
      moodTimerRef.current = null;
    }
  }, []);

  const clearReminderTimer = useCallback(() => {
    if (reminderTimerRef.current !== null) {
      window.clearTimeout(reminderTimerRef.current);
      reminderTimerRef.current = null;
    }
  }, []);

  const schedulePetMood = useCallback(
    (nextMood: PetMood, delayMs: number) => {
      clearMoodTimer();
      moodTimerRef.current = window.setTimeout(() => {
        moodTimerRef.current = null;
        petMoodRef.current = nextMood;
        setPetMood(nextMood);
      }, delayMs);
    },
    [clearMoodTimer]
  );

  const applyPetState = useCallback(
    (state: PetState) => {
      clearMoodTimer();
      petMoodRef.current = state;
      setPetMood(state);

      if (state === 'success') {
        schedulePetMood('idle', 1800);
      } else if (state === 'error') {
        schedulePetMood('idle', 2600);
      } else if (state === 'idle') {
        schedulePetMood('sleepy', 60000);
      }
    },
    [clearMoodTimer, schedulePetMood]
  );

  const setHappy = useCallback(() => {
    setEmotion('happy');
    applyPetState('success');
  }, [applyPetState]);

  const setSad = useCallback(() => {
    setEmotion('sad');
    applyPetState('error');
  }, [applyPetState]);

  const { appendAssistantMessage, input, isLoading, messages, sendMessage, setInput } = useChatMessages({
    agentMode: DEFAULT_AGENT_MODE,
    shouldLoadHistory: mode === 'panel',
    onDone: setHappy,
    onError: setSad,
    onPetState: applyPetState,
  });

  const { uploadKnowledgeFile, uploadPhase, uploadProgress } = useKnowledgeUpload({
    appendAssistantMessage,
    onDone: setHappy,
    onError: setSad,
  });

  useEffect(() => {
    if (ENABLE_DESKTOP_DEBUG_LOGS) {
      console.log('[Renderer] App mounted', {
        mode,
        hasElectronApi: !!getElectronApi(),
      });
    }
  }, [mode]);

  useEffect(() => {
    petMoodRef.current = petMood;
  }, [petMood]);

  useEffect(() => {
    return () => {
      clearMoodTimer();
      clearReminderTimer();
    };
  }, [clearMoodTimer, clearReminderTimer]);

  useEffect(() => {
    if (mode !== 'pet') {
      return () => {
        clearMoodTimer();
      };
    }

    schedulePetMood('sleepy', 60000);

    const wakePet = () => {
      if (petMoodRef.current === 'sleepy') {
        setEmotion('neutral');
        applyPetState('idle');
        return;
      }

      if (petMoodRef.current === 'idle') {
        schedulePetMood('sleepy', 60000);
      }
    };

    window.addEventListener('pointerdown', wakePet);
    window.addEventListener('pointermove', wakePet);

    return () => {
      clearMoodTimer();
      window.removeEventListener('pointerdown', wakePet);
      window.removeEventListener('pointermove', wakePet);
    };
  }, [applyPetState, clearMoodTimer, mode, schedulePetMood]);

  useEffect(() => {
    const api = getElectronApi();
    if (!api) {
      return undefined;
    }

    return api.onReminderDue((event) => {
      setHappy();
      setReminderNotice(event);
      clearReminderTimer();
      reminderTimerRef.current = window.setTimeout(() => {
        reminderTimerRef.current = null;
        setReminderNotice(null);
      }, mode === 'pet' ? 12000 : 9000);

      if (mode === 'panel') {
        appendAssistantMessage(`提醒你：${event.title}\n\n时间：${event.remindAt}\nID：${event.id}`);
      }
    });
  }, [appendAssistantMessage, clearReminderTimer, mode, setHappy]);

  const setPanelOpen = async (nextOpen: boolean) => {
    await requireElectronApi().setPanelOpen(nextOpen);
  };

  const togglePanel = async () => {
    await requireElectronApi().togglePanel();
  };

  const openReminderPanel = async () => {
    setReminderNotice(null);
    clearReminderTimer();
    await requireElectronApi().setPanelOpen(true);
  };

  if (mode === 'panel') {
    return (
      <div className="app panel-window">
        <div className="chat-popover">
          {reminderNotice ? (
            <div className="reminder-banner" role="status">
              <div className="reminder-banner-icon">!</div>
              <div className="reminder-banner-copy">
                <div className="reminder-banner-title">{reminderNotice.title}</div>
                <div className="reminder-banner-time">{reminderNotice.remindAt}</div>
              </div>
              <button
                className="reminder-banner-close"
                onClick={() => {
                  setReminderNotice(null);
                  clearReminderTimer();
                }}
                type="button"
                aria-label="关闭提醒"
              >
                ×
              </button>
            </div>
          ) : null}
          <ChatPanel
            input={input}
            isLoading={isLoading}
            messages={messages}
            onChange={setInput}
            onClose={() => void setPanelOpen(false)}
            onSend={sendMessage}
            onUploadFile={(file) => void uploadKnowledgeFile(file)}
            uploadPhase={uploadPhase}
            uploadProgress={uploadProgress}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="app pet-window">
      <div className="pet-stage">
        {reminderNotice ? (
          <button className="pet-reminder-pop" onClick={() => void openReminderPanel()} type="button">
            <span className="pet-reminder-title">{reminderNotice.title}</span>
            <span className="pet-reminder-time">{reminderNotice.remindAt}</span>
          </button>
        ) : null}
        <div className="pet-container">
          <PetAvatar emotion={emotion} mood={petMood} onActivate={() => void togglePanel()} />
        </div>
      </div>
    </div>
  );
}
