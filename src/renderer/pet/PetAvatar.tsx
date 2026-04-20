import { useRef, type MouseEvent as ReactMouseEvent } from 'react';
import { getElectronApi } from '../electronApi';

export interface PetAvatarProps {
  emotion: 'happy' | 'neutral' | 'sad' | 'excited';
  onActivate?: () => void;
  onDebug?: (message: string) => void;
}

export function PetAvatar({ emotion, onActivate, onDebug }: PetAvatarProps) {
  const dragRef = useRef({
    active: false,
    button: 0,
    moved: false,
    startX: 0,
    startY: 0,
    lastX: 0,
    lastY: 0,
  });

  const handleMouseDown = (event: ReactMouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    onDebug?.(`mouseDown button=${event.button} x=${event.screenX} y=${event.screenY}`);

    const hostWindow = event.currentTarget.ownerDocument.defaultView;
    if (!hostWindow) {
      onDebug?.('mouseDown aborted: no hostWindow');
      return;
    }

    dragRef.current = {
      active: true,
      button: event.button,
      moved: false,
      startX: event.screenX,
      startY: event.screenY,
      lastX: event.screenX,
      lastY: event.screenY,
    };
    void getElectronApi()?.startWindowDrag(event.screenX, event.screenY);

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!dragRef.current.active) {
        return;
      }

      const totalDx = moveEvent.screenX - dragRef.current.startX;
      const totalDy = moveEvent.screenY - dragRef.current.startY;
      const dx = moveEvent.screenX - dragRef.current.lastX;
      const dy = moveEvent.screenY - dragRef.current.lastY;

      if (totalDx === 0 && totalDy === 0 && dx === 0 && dy === 0) {
        return;
      }

      if (Math.abs(totalDx) > 6 || Math.abs(totalDy) > 6) {
        dragRef.current.moved = true;
        onDebug?.(`drag totalDx=${totalDx} totalDy=${totalDy}`);
      }

      dragRef.current.lastX = moveEvent.screenX;
      dragRef.current.lastY = moveEvent.screenY;

      void getElectronApi()?.moveWindowDragTo(moveEvent.screenX, moveEvent.screenY);
    };

    const cleanup = () => {
      hostWindow.removeEventListener('mousemove', handleMouseMove);
      hostWindow.removeEventListener('mouseup', handleMouseUp, true);
      dragRef.current.active = false;
      void getElectronApi()?.endWindowDrag();
    };

    const handleMouseUp = (upEvent: MouseEvent) => {
      const shouldActivate = dragRef.current.button === 0 && !dragRef.current.moved;
      onDebug?.(`mouseUp moved=${dragRef.current.moved} activate=${shouldActivate}`);
      cleanup();

      if (shouldActivate) {
        upEvent.preventDefault();
        onDebug?.('trigger onActivate');
        onActivate?.();
      }
    };

    hostWindow.addEventListener('mousemove', handleMouseMove);
    hostWindow.addEventListener('mouseup', handleMouseUp, true);
  };

  return (
    <div className="pet-shell">
      <button
        className={`pet ${emotion}`}
        onContextMenu={(event) => event.preventDefault()}
        onMouseDown={handleMouseDown}
        type="button"
        aria-label="唤醒宠物助手"
      >
        <div className="pet-body">
          <div className="pet-eyes">
            <div className="eye left"></div>
            <div className="eye right"></div>
          </div>
          <div className="pet-mouth"></div>
        </div>
      </button>
    </div>
  );
}
