import React, { useState, useEffect, useCallback } from 'react';
import { Volume2, VolumeX } from 'lucide-react';
import { speechService } from '../services/speechService';

interface AudioButtonProps {
  text: string;
  lang?: string;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  title?: string;
}

export const AudioButton: React.FC<AudioButtonProps> = ({
  text,
  lang = 'en',
  className = '',
  size = 'md',
  title = 'Listen to voice summary',
}) => {
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    const unsubscribe = speechService.addListener((state, activeText) => {
      if (state === 'speaking' && activeText === text.replace(/[*#_`]/g, '').trim()) {
        setIsPlaying(true);
      } else {
        setIsPlaying(false);
      }
    });
    return () => unsubscribe();
  }, [text]);

  const handlePlay = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();

      if (!text) return;

      if (isPlaying) {
        speechService.stop();
        setIsPlaying(false);
        return;
      }

      speechService.speak(text, lang, {
        onStart: () => setIsPlaying(true),
        onEnd: () => setIsPlaying(false),
        onError: () => setIsPlaying(false),
      });
    },
    [isPlaying, text, lang]
  );

  if (!text) return null;

  const sizeClasses = {
    sm: 'w-7 h-7 text-xs',
    md: 'w-8 h-8 text-sm',
    lg: 'w-10 h-10 text-base',
  };

  const iconSizes = {
    sm: 'w-3.5 h-3.5',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  return (
    <button
      type="button"
      onClick={handlePlay}
      className={`relative inline-flex items-center justify-center rounded-full transition-all duration-150 shrink-0 select-none shadow-xs focus:outline-none ${
        sizeClasses[size]
      } ${
        isPlaying
          ? 'bg-[#1C2B3A] text-white font-bold ring-2 ring-[#1C2B3A]/30 shadow-md'
          : 'bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] border border-[#D8D2C6] hover:border-[#1C2B3A]'
      } ${className}`}
      aria-label={isPlaying ? 'Stop voice readout' : title}
      title={isPlaying ? 'Click to stop voice readout' : title}
    >
      {isPlaying ? (
        <VolumeX className={iconSizes[size]} />
      ) : (
        <Volume2 className={iconSizes[size]} />
      )}
      {isPlaying && (
        <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-600" />
        </span>
      )}
    </button>
  );
};
