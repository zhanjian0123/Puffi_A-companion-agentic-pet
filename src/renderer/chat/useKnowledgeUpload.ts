import { useCallback, useEffect, useRef, useState } from 'react';
import { requireElectronApi } from '../electronApi';

type UploadPhase = 'uploading' | 'processing' | null;

interface UseKnowledgeUploadOptions {
  appendAssistantMessage: (content: string) => void;
  onDone?: () => void;
  onError?: () => void;
}

export function useKnowledgeUpload({
  appendAssistantMessage,
  onDone,
  onError,
}: UseKnowledgeUploadOptions) {
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadPhase, setUploadPhase] = useState<UploadPhase>(null);
  const activeUploadRef = useRef<string | null>(null);

  useEffect(() => {
    const unsubscribeUpload = requireElectronApi().onKnowledgeUploadProgress((event) => {
      if (activeUploadRef.current !== event.requestId) {
        return;
      }

      if (event.phase === 'uploading' || event.phase === 'processing') {
        setUploadProgress(event.progress);
        setUploadPhase(event.phase);
        return;
      }

      setUploadProgress(null);
      setUploadPhase(null);
      activeUploadRef.current = null;

      if (event.phase === 'done' && event.message) {
        appendAssistantMessage(event.message);
        onDone?.();
        return;
      }

      if (event.phase === 'error') {
        console.error('Knowledge upload error:', event.message);
        onError?.();
      }
    });

    return unsubscribeUpload;
  }, [appendAssistantMessage, onDone, onError]);

  const uploadKnowledgeFile = useCallback(
    async (file: File) => {
      if (activeUploadRef.current) {
        return;
      }

      const requestId = createMessageId();
      activeUploadRef.current = requestId;
      setUploadProgress(0);
      setUploadPhase('uploading');

      try {
        await requireElectronApi().uploadKnowledgeFile(file, requestId);
      } catch (error) {
        console.error('Knowledge upload error:', error);
        if (activeUploadRef.current === requestId) {
          activeUploadRef.current = null;
          setUploadProgress(null);
          setUploadPhase(null);
          onError?.();
        }
      }
    },
    [onError]
  );

  return {
    uploadKnowledgeFile,
    uploadPhase,
    uploadProgress,
  };
}

function createMessageId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
