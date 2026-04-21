import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
import { requireElectronApi } from '../electronApi';
import { ENABLE_DESKTOP_DEBUG_LOGS } from '../../shared/devFlags';

export interface PetAvatarProps {
  emotion: 'happy' | 'neutral' | 'sad' | 'excited';
  onActivate?: () => void;
}

export function PetAvatar({ emotion, onActivate }: PetAvatarProps) {
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef({
    active: false,
    moved: false,
    suppressClick: false,
    startX: 0,
    startY: 0,
  });

  useEffect(() => {
    return () => {
      dragRef.current.active = false;
    };
  }, []);

  const cleanupDrag = () => {
    dragRef.current = {
      active: false,
      moved: false,
      suppressClick: dragRef.current.suppressClick,
      startX: 0,
      startY: 0,
    };
    setIsDragging(false);
    void requireElectronApi().endWindowDrag();
  };

  const handleMouseDown = (event: ReactMouseEvent<HTMLButtonElement>) => {
    if (event.button !== 0) {
      return;
    }

    if (ENABLE_DESKTOP_DEBUG_LOGS) {
      console.log('[Renderer] pet mousedown', {
        screenX: event.screenX,
        screenY: event.screenY,
      });
    }
    event.preventDefault();
    event.stopPropagation();

    dragRef.current = {
      active: true,
      moved: false,
      suppressClick: false,
      startX: event.screenX,
      startY: event.screenY,
    };
    void requireElectronApi().startWindowDrag(event.screenX, event.screenY);

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!dragRef.current.active) {
        return;
      }

      const totalDx = moveEvent.screenX - dragRef.current.startX;
      const totalDy = moveEvent.screenY - dragRef.current.startY;

      if (totalDx === 0 && totalDy === 0) {
        return;
      }

      if (Math.abs(totalDx) > 6 || Math.abs(totalDy) > 6) {
        dragRef.current.moved = true;
        dragRef.current.suppressClick = true;
        setIsDragging(true);
      }

      void requireElectronApi().moveWindowDragTo(moveEvent.screenX, moveEvent.screenY);
    };

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp, true);
      cleanupDrag();
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp, true);
  };

  const handleClick = (event: ReactMouseEvent<HTMLButtonElement>) => {
    if (ENABLE_DESKTOP_DEBUG_LOGS) {
      console.log('[Renderer] pet click', {
        suppressClick: dragRef.current.suppressClick,
      });
    }

    if (dragRef.current.suppressClick) {
      event.preventDefault();
      event.stopPropagation();
      dragRef.current.suppressClick = false;
      return;
    }

    onActivate?.();
  };

  return (
    <div className="pet-shell">
      <button
        className={`pet ${emotion} ${isDragging ? 'dragging' : ''}`}
        draggable={false}
        onClick={handleClick}
        onContextMenu={(event) => event.preventDefault()}
        onDragStart={(event) => event.preventDefault()}
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
