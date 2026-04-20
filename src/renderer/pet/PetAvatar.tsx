export interface PetAvatarProps {
  emotion: 'happy' | 'neutral' | 'sad' | 'excited';
}

export function PetAvatar({ emotion }: PetAvatarProps) {
  return (
    <div className={`pet ${emotion}`}>
      <div className="pet-body">
        <div className="pet-eyes">
          <div className="eye left"></div>
          <div className="eye right"></div>
        </div>
        <div className="pet-mouth"></div>
      </div>
    </div>
  );
}
