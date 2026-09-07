/**
 * Multilingual Speech Synthesis Service
 * =====================================
 * Dual-tier robust voice synthesizer:
 * 1. Primary: High-fidelity native speech audio streamed from backend `/tts` (powered by gTTS).
 *    Guarantees authentic pronunciation for Tamil (ta), Hindi (hi), Telugu (te),
 *    Kannada (kn), Malayalam (ml), and Indian English (en) across all browsers.
 *    Uses Blob object URL caching to prevent audio playback interruptions and race conditions.
 * 2. Fallback: Browser Web Speech API (`window.speechSynthesis`) with smart voice discovery,
 *    BCP-47 matching, and fallback safeguards to prevent "language-unavailable" errors.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

type SpeechState = 'idle' | 'speaking' | 'paused';
type StateListener = (state: SpeechState, activeText?: string) => void;

class SpeechService {
  private currentAudio: HTMLAudioElement | null = null;
  private currentAudioUrl: string | null = null;
  private state: SpeechState = 'idle';
  private currentText: string = '';
  private currentLang: string = 'en';
  private listeners: Set<StateListener> = new Set();
  private isBrowserSynthActive: boolean = false;
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private cachedVoices: SpeechSynthesisVoice[] = [];
  private abortController: AbortController | null = null;

  constructor() {
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => this.stop());
      this.initVoices();
    }
  }

  private initVoices() {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;

    const loadVoices = () => {
      try {
        const voices = window.speechSynthesis.getVoices();
        if (voices && voices.length > 0) {
          this.cachedVoices = voices;
        }
      } catch {
        // Ignore voice load error
      }
    };

    loadVoices();
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = loadVoices;
    }
  }

  private getBestVoiceForLanguage(langCode: string): SpeechSynthesisVoice | null {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null;

    let voices = this.cachedVoices.length > 0 ? this.cachedVoices : window.speechSynthesis.getVoices();
    if (!voices || voices.length === 0) return null;

    const code = langCode.toLowerCase().split('-')[0];

    // Priority prefixes and voice names for each supported language
    const langMap: Record<string, string[]> = {
      en: ['en-in', 'en-us', 'en-gb', 'en', 'george', 'susan', 'hazel', 'david', 'zira'],
      hi: ['hi-in', 'hi', 'hindi', 'madhur', 'swara', 'kalpana', 'hemant'],
      ta: ['ta-in', 'ta', 'tamil', 'valluvar', 'pallavi'],
      te: ['te-in', 'te', 'telugu', 'mohan', 'shruti'],
      kn: ['kn-in', 'kn', 'kannada', 'gagan', 'sapna'],
      ml: ['ml-in', 'ml', 'malayalam', 'midhun', 'sobhana'],
    };

    const targetPrefixes = langMap[code] || [code];

    // 1. Look for targeted voice
    for (const prefix of targetPrefixes) {
      const match = voices.find(v => {
        const vLang = v.lang.toLowerCase().replace('_', '-');
        const vName = v.name.toLowerCase();
        return vLang === prefix || vLang.startsWith(prefix) || vName.includes(prefix);
      });
      if (match) return match;
    }

    // 2. If English, find any English voice
    if (code === 'en') {
      const enVoice = voices.find(v => v.lang.toLowerCase().startsWith('en'));
      if (enVoice) return enVoice;
      const indianEnglish = voices.find(v => v.lang.toLowerCase().replace('_', '-').includes('en-in'));
      if (indianEnglish) return indianEnglish;
      return voices.find(v => v.default) || voices[0] || null;
    }

    // 3. For non-English Indic languages: DO NOT fallback to an English voice!
    // An English voice speaking Tamil or Hindi produces total silence or garbled phonemes.
    return null;
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

  public getCurrentUtterance(): SpeechSynthesisUtterance | null {
    return this.currentUtterance;
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

  private cleanupAudio() {
    if (this.currentAudio) {
      try {
        this.currentAudio.pause();
        this.currentAudio.src = '';
        this.currentAudio.load();
      } catch {
        // Ignore audio cleanup errors
      }
      this.currentAudio = null;
    }
    if (this.currentAudioUrl) {
      try {
        URL.revokeObjectURL(this.currentAudioUrl);
      } catch {
        // Ignore revoke errors
      }
      this.currentAudioUrl = null;
    }
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
    const cleanText = (text || '')
      .replace(/[*#_`]/g, '')
      .replace(/\s+/g, ' ')
      .trim();

    if (!cleanText) return;

    this.stop();

    this.currentText = cleanText;
    this.currentLang = lang;
    const langCode = lang.split('-')[0].toLowerCase();

    // Tier 1: Try backend high-fidelity audio stream via fetch (with generous 20s timeout)
    try {
      this.abortController = new AbortController();
      const timeoutId = setTimeout(() => {
        this.abortController?.abort();
      }, 20000);

      // Truncate to ~350 chars for speech synthesis (first 2-3 sentences) to ensure sub-2s generation
      let ttsText = cleanText;
      if (cleanText.length > 350) {
        const slice = cleanText.slice(0, 350);
        const lastPunct = Math.max(
          slice.lastIndexOf('.'),
          slice.lastIndexOf('?'),
          slice.lastIndexOf('!'),
          slice.lastIndexOf('।'),
          slice.lastIndexOf('\n')
        );
        ttsText = lastPunct > 80 ? slice.slice(0, lastPunct + 1) : slice + '...';
      }

      const url = `${API_BASE_URL}/tts?text=${encodeURIComponent(ttsText)}&lang=${langCode}`;

      const response = await fetch(url, {
        method: 'GET',
        signal: this.abortController.signal,
      });
      clearTimeout(timeoutId);

      if (response.ok) {
        const blob = await response.blob();
        if (blob.size > 200) {
          const blobUrl = URL.createObjectURL(blob);
          this.currentAudioUrl = blobUrl;
          const audio = new Audio(blobUrl);
          audio.preload = 'auto';
          this.currentAudio = audio;

          audio.onplay = () => {
            this.emitState('speaking');
            callbacks?.onStart?.();
          };

          audio.onended = () => {
            this.cleanupAudio();
            this.emitState('idle');
            callbacks?.onEnd?.();
          };

          audio.onerror = () => {
            this.cleanupAudio();
            this.speakWithBrowserSynth(cleanText, langCode, callbacks);
          };

          try {
            await audio.play();
            return;
          } catch (playErr: any) {
            console.warn('Audio play() promise rejected:', playErr);
            this.cleanupAudio();
            this.speakWithBrowserSynth(cleanText, langCode, callbacks);
            return;
          }
        }
      }
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        console.warn('Backend TTS not reached, attempting fallback:', err?.message || err);
      }
    }

    // Tier 2: Fallback to Browser SpeechSynthesis (if supported voice exists)
    this.speakWithBrowserSynth(cleanText, langCode, callbacks);
  }

  /**
   * Browser SpeechSynthesis fallback with smart voice matching
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

    try {
      window.speechSynthesis.cancel();
    } catch {
      // Ignore cancel error
    }

    // Give browser speech synthesis queue 50ms to settle after cancellation
    setTimeout(() => {
      try {
        const bestVoice = this.getBestVoiceForLanguage(langCode);
        if (!bestVoice && langCode !== 'en') {
          console.warn(`No native browser voice available for language '${langCode}' and backend TTS was unreachable.`);
          this.emitState('idle');
          callbacks?.onError?.(new Error(`No voice available for language ${langCode}`));
          return;
        }

        const utterance = new SpeechSynthesisUtterance(text);
        this.currentUtterance = utterance;

        if (bestVoice) {
          utterance.voice = bestVoice;
          // CRITICAL: Set utterance.lang to match the chosen voice's lang.
          // This prevents the browser from throwing "language-unavailable" error.
          utterance.lang = bestVoice.lang;
        } else {
          utterance.lang = 'en-US';
        }

        utterance.rate = 0.95;
        utterance.pitch = 1.0;

        utterance.onstart = () => {
          this.isBrowserSynthActive = true;
          this.emitState('speaking');
          callbacks?.onStart?.();
        };

        utterance.onend = () => {
          this.isBrowserSynthActive = false;
          this.currentUtterance = null;
          this.emitState('idle');
          callbacks?.onEnd?.();
        };

        utterance.onerror = (e) => {
          this.isBrowserSynthActive = false;
          this.currentUtterance = null;
          this.emitState('idle');
          // Don't report benign interruptions as user errors
          if (e.error !== 'interrupted' && e.error !== 'canceled') {
            console.warn('Browser SpeechSynthesis error:', e.error);
            callbacks?.onError?.(e);
          }
        };

        window.speechSynthesis.speak(utterance);
      } catch (synthErr) {
        console.warn('SpeechSynthesis invocation failed:', synthErr);
        this.emitState('idle');
        callbacks?.onError?.(synthErr);
      }
    }, 50);
  }

  /**
   * Pause speech playback
   */
  public pause(): void {
    if (this.currentAudio && !this.currentAudio.paused) {
      this.currentAudio.pause();
      this.emitState('paused');
    } else if (this.isBrowserSynthActive && typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.pause();
      } catch {}
      this.emitState('paused');
    }
  }

  /**
   * Resume speech playback
   */
  public resume(): void {
    if (this.currentAudio && this.currentAudio.paused) {
      this.currentAudio.play().catch(() => {});
      this.emitState('speaking');
    } else if (this.isBrowserSynthActive && typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.resume();
      } catch {}
      this.emitState('speaking');
    }
  }

  /**
   * Stop speech playback completely
   */
  public stop(): void {
    if (this.abortController) {
      try {
        this.abortController.abort();
      } catch {}
      this.abortController = null;
    }

    this.cleanupAudio();

    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {}
      this.isBrowserSynthActive = false;
      this.currentUtterance = null;
    }
    this.emitState('idle');
  }
}

export const speechService = new SpeechService();
