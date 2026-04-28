import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
} from 'react';
import { requireElectronApi } from '../electronApi';
import { ENABLE_DESKTOP_DEBUG_LOGS } from '../../shared/devFlags';
import type { PetDockSide } from '../../shared/types';

export type PetMood = 'idle' | 'thinking' | 'searching' | 'tooling' | 'success' | 'error' | 'sleepy';

export interface PetAvatarProps {
  dockSide?: PetDockSide;
  emotion: 'happy' | 'neutral' | 'sad' | 'excited';
  mood?: PetMood;
  onActivate?: () => void;
}

function moodFromEmotion(emotion: PetAvatarProps['emotion']): PetMood {
  if (emotion === 'happy' || emotion === 'excited') {
    return 'success';
  }

  if (emotion === 'sad') {
    return 'error';
  }

  return 'idle';
}

export function PetAvatar({ dockSide = null, emotion, mood, onActivate }: PetAvatarProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isPressed, setIsPressed] = useState(false);
  const [lookOffset, setLookOffset] = useState({ x: 0, y: 0 });
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
    setIsPressed(false);
    void requireElectronApi().endWindowDrag();
  };

  const petMood = mood ?? moodFromEmotion(emotion);
  const dockClass = !isDragging && dockSide ? `docked-${dockSide}` : '';
  const petStyle = {
    '--look-x': `${lookOffset.x}px`,
    '--look-y': `${lookOffset.y}px`,
  } as CSSProperties;

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
    setIsPressed(true);
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

  const handleMouseMove = (event: ReactMouseEvent<HTMLButtonElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const centerX = bounds.left + bounds.width / 2;
    const centerY = bounds.top + bounds.height / 2;
    const nextX = Math.max(-4, Math.min(4, (event.clientX - centerX) / 14));
    const nextY = Math.max(-3, Math.min(3, (event.clientY - centerY) / 18));

    setLookOffset({ x: nextX, y: nextY });
  };

  const handleMouseLeave = () => {
    setLookOffset({ x: 0, y: 0 });
  };

  return (
    <div className={`pet-shell ${dockClass}`}>
      <div className={`pet-drag-echo ${isDragging ? 'visible' : ''}`}></div>
      <button
        className={`pet blob-pet ${petMood} ${dockClass} ${isDragging ? 'dragging' : ''} ${
          isPressed ? 'pressed' : ''
        }`}
        draggable={false}
        style={petStyle}
        onClick={handleClick}
        onContextMenu={(event) => event.preventDefault()}
        onDragStart={(event) => event.preventDefault()}
        onMouseLeave={handleMouseLeave}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        type="button"
        aria-label="唤醒宠物助手"
      >
        <div className="blob-body">
          <div className="blob-shadow"></div>
          <div className="blob-gloss"></div>
          <div className="blob-arm left"></div>
          <div className="blob-arm right"></div>
          <div className="blob-face">
            <div className="blob-eyes">
              <div className="blob-eye left"></div>
              <div className="blob-eye right"></div>
            </div>
            <div className="blob-mouth"></div>
          </div>
          <div className="blob-cheek left"></div>
          <div className="blob-cheek right"></div>
          <div className="blob-effect question">?</div>
          <div className="blob-effect search"></div>
          <div className="blob-effect gear"></div>
          <div className="blob-effect sparkles">
            <span></span>
            <span></span>
          </div>
          <div className="blob-effect bolt">!</div>
          <div className="blob-effect sleep">z</div>
        </div>
      </button>
    </div>
  );
}
