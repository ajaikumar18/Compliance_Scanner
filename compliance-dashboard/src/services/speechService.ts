/**
 * Multilingual Speech Synthesis Service
 * =====================================
 * Dual-tier voice synthesizer:
 * 1. Primary: High-fidelity native speech streaming via backend `/tts` endpoint (gTTS).
 *    Guarantees authentic pronunciation for Tamil (ta), Hindi (hi), Telugu (te),
 *    Kannada (kn), Malayalam (ml), and English (en) across all browsers (including
 *    Windows environments without native Indic SAPI voices).
 * 2. Fallback: Browser Web Speech API (`window.speechSynthesis`) if backend is unavailable.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

type SpeechState = 'idle' | 'speaking' | 'paused';
type StateListener = (state: SpeechState, activeText?: string) => void;

class SpeechService {
  private currentAudio: HTMLAudioElement | null = null;
  private state: SpeechState = 'idle';
  private currentText: string = '';
  private currentLang: string = 'en';
  private listeners: Set<StateListener> = new Set();
  private isBrowserSynthActive: boolean = false;

  constructor() {
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => this.stop());
    }
  }

  public getState(): SpeechState {
    return this.state;
  }

  public isSpeaking(): boolean {
    return this.state === 'speaking';
  }

  public isPaused(): boolean {
    return this.state === 'paused';
  }

  public getCurrentText(): string {
    return this.currentText;
  }

  public getCurrentLang(): string {
    return this.currentLang;
  }

  public addListener(listener: StateListener): () => void {
    this.listeners.add(listener);
    listener(this.state, this.currentText);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private emitState(state: SpeechState) {
    this.state = state;
    this.listeners.forEach(l => l(state, this.currentText));
  }

  /**
   * Speak the provided text in the target language.
   */
  public async speak(
    text: string,
    lang: string = 'en',
    callbacks?: {
      onStart?: () => void;
      onEnd?: () => void;
      onError?: (err: any) => void;
    }
  ): Promise<void> {
    const cleanText = (text || '').replace(/[*#_`]/g, '').trim();
    if (!cleanText) return;

    this.stop();

    this.currentText = cleanText;
    this.currentLang = lang;

    const langCode = lang.split('-')[0].toLowerCase();

    // Tier 1: Try backend high-fidelity audio stream
    try {
      const audioUrl = `${API_BASE_URL}/tts?text=${encodeURIComponent(cleanText)}&lang=${langCode}`;
      const audio = new Audio(audioUrl);
      this.currentAudio = audio;

      audio.onplay = () => {
        this.emitState('speaking');
        callbacks?.onStart?.();
      };

      audio.onended = () => {
        this.emitState('idle');
        this.currentAudio = null;
        callbacks?.onEnd?.();
      };

      audio.onerror = (e) => {
        console.warn('Backend TTS failed, falling back to browser SpeechSynthesis:', e);
        this.currentAudio = null;
        this.speakWithBrowserSynth(cleanText, langCode, callbacks);
      };

      await audio.play();
    } catch (err) {
      console.warn('Audio play error, falling back to browser SpeechSynthesis:', err);
      this.currentAudio = null;
      this.speakWithBrowserSynth(cleanText, langCode, callbacks);
    }
  }

  /**
   * Browser SpeechSynthesis fallback
   */
  private speakWithBrowserSynth(
    text: string,
    langCode: string,
    callbacks?: {
      onStart?: () => void;
      onEnd?: () => void;
      onError?: (err: any) => void;
    }
  ) {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      this.emitState('idle');
      callbacks?.onError?.(new Error('Speech Synthesis not supported'));
      return;
    }

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    const bcpMap: Record<string, string> = {
      en: 'en-IN',
      hi: 'hi-IN',
      ta: 'ta-IN',
      te: 'te-IN',
      kn: 'kn-IN',
      ml: 'ml-IN',
    };
    utterance.lang = bcpMap[langCode] || 'en-IN';
    utterance.rate = 0.92;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const matchingVoice = voices.find(v => 
      v.lang.toLowerCase().replace('_', '-').startsWith(langCode) ||
      v.name.toLowerCase().includes(langCode)
    );
    if (matchingVoice) {
      utterance.voice = matchingVoice;
    }

    utterance.onstart = () => {
      this.isBrowserSynthActive = true;
      this.emitState('speaking');
      callbacks?.onStart?.();
    };

    utterance.onend = () => {
      this.isBrowserSynthActive = false;
      this.emitState('idle');
      callbacks?.onEnd?.();
    };

    utterance.onerror = (e) => {
      this.isBrowserSynthActive = false;
      this.emitState('idle');
      callbacks?.onError?.(e);
    };

    window.speechSynthesis.speak(utterance);
  }

  /**
   * Pause speech playback
   */
  public pause(): void {
    if (this.currentAudio && !this.currentAudio.paused) {
      this.currentAudio.pause();
      this.emitState('paused');
    } else if (this.isBrowserSynthActive && typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.pause();
      this.emitState('paused');
    }
  }

  /**
   * Resume speech playback
   */
  public resume(): void {
    if (this.currentAudio && this.currentAudio.paused) {
      this.currentAudio.play();
      this.emitState('speaking');
    } else if (this.isBrowserSynthActive && typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.resume();
      this.emitState('speaking');
    }
  }

  /**
   * Stop speech playback completely
   */
  public stop(): void {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio.currentTime = 0;
      this.currentAudio = null;
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      this.isBrowserSynthActive = false;
    }
    this.emitState('idle');
  }
}

export const speechService = new SpeechService();
