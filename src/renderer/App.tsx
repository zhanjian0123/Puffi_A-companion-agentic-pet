import { useCallback, useEffect, useState } from 'react';
import { getElectronApi, requireElectronApi } from './electronApi';
import { ChatPanel } from './chat/ChatPanel';
import { useChatMessages } from './chat/useChatMessages';
import { useKnowledgeUpload } from './chat/useKnowledgeUpload';
import { PetAvatar } from './pet/PetAvatar';
import { ENABLE_DESKTOP_DEBUG_LOGS } from '../shared/devFlags';

type PetEmotion = 'happy' | 'neutral' | 'sad';
const DEFAULT_AGENT_MODE = 'chat';

export default function App() {
  const mode = new URLSearchParams(window.location.search).get('mode') === 'panel' ? 'panel' : 'pet';
  const [emotion, setEmotion] = useState<PetEmotion>('neutral');
  const setHappy = useCallback(() => setEmotion('happy'), []);
  const setSad = useCallback(() => setEmotion('sad'), []);

  const { appendAssistantMessage, input, isLoading, messages, sendMessage, setInput } = useChatMessages({
    agentMode: DEFAULT_AGENT_MODE,
    shouldLoadHistory: mode === 'panel',
    onDone: setHappy,
    onError: setSad,
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

  const setPanelOpen = async (nextOpen: boolean) => {
    await requireElectronApi().setPanelOpen(nextOpen);
  };

  const togglePanel = async () => {
    await requireElectronApi().togglePanel();
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
        <div className="pet-container">
          <PetAvatar emotion={emotion} onActivate={() => void togglePanel()} />
        </div>
      </div>
    </div>
  );
}
