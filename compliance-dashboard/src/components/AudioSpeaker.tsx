import React, { useState, useEffect } from 'react';
import { Volume2, VolumeX, Pause, Play } from 'lucide-react';
import { speechService } from '../services/speechService';

interface AudioSpeakerProps {
  text: string;
  label?: string;
  lang?: string;
  className?: string;
}

export const AudioSpeaker: React.FC<AudioSpeakerProps> = ({
  text,
  label,
  lang = 'en',
  className = '',
}) => {
  const [speaking, setSpeaking] = useState(false);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const unsubscribe = speechService.addListener((state, activeText) => {
      const clean = text.replace(/[*#_`]/g, '').trim();
      if (activeText === clean) {
        setSpeaking(state === 'speaking');
        setPaused(state === 'paused');
      } else {
        setSpeaking(false);
        setPaused(false);
      }
    });
    return () => unsubscribe();
  }, [text]);

  const toggleSpeech = () => {
    if (speaking) {
      speechService.stop();
      setSpeaking(false);
      setPaused(false);
      return;
    }

    speechService.speak(text, lang, {
      onStart: () => {
        setSpeaking(true);
        setPaused(false);
      },
      onEnd: () => {
        setSpeaking(false);
        setPaused(false);
      },
      onError: () => {
        setSpeaking(false);
        setPaused(false);
      },
    });
  };

  const togglePause = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (paused) {
      speechService.resume();
      setPaused(false);
    } else {
      speechService.pause();
      setPaused(true);
    }
  };

  return (
    <div className={`inline-flex items-center gap-1.5 ${className}`}>
      <button
        onClick={toggleSpeech}
        type="button"
        className={`inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold tracking-wide transition-all shadow-xs select-none border rounded-none ${
          speaking
            ? 'bg-[#1C2B3A] text-white border-[#1C2B3A] shadow-md ring-1 ring-[#1C2B3A]'
            : 'bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] border-[#D8D2C6] hover:border-[#1C2B3A]'
        }`}
        title={speaking ? 'Stop Voice Report readout' : 'Listen to Full Spoken Inspection Report'}
      >
        {speaking ? (
          <>
            <VolumeX className="w-4 h-4 text-white animate-pulse" />
            <div className="flex items-center gap-0.5 h-3 px-1">
              <span className="w-0.5 h-3 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-0.5 h-3 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-0.5 h-3 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <span className="text-white font-bold">Stop Voice Report</span>
          </>
        ) : (
          <>
            <Volume2 className="w-4 h-4 text-[#1C2B3A]" />
            <span className="font-semibold text-[#1C2B3A]">{label || 'Listen to Voice Report'}</span>
          </>
        )}
      </button>

      {speaking && (
        <button
          onClick={togglePause}
          type="button"
          className="p-2 bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] border border-[#D8D2C6] transition shadow-xs rounded-none"
          title={paused ? 'Resume speech' : 'Pause speech'}
        >
          {paused ? <Play className="w-3.5 h-3.5 text-emerald-600" /> : <Pause className="w-3.5 h-3.5 text-[#1C2B3A]" />}
        </button>
      )}
    </div>
  );
};
