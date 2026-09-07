import React, { useState, useEffect, useRef } from 'react';
import { 
  Mic, 
  MicOff, 
  Volume2, 
  VolumeX, 
  ChevronLeft, 
  ChevronRight, 
  Sparkles, 
  Send, 
  Pause, 
  Play, 
  Scale, 
  Keyboard 
} from 'lucide-react';
import { useLanguage } from '../i18n/i18nContext';
import { metrologyAdvisorEngine } from '../services/metrologyAdvisorEngine';
import { speechService } from '../services/speechService';
import type { ScanResult } from '../types';

interface LeftVoiceAIPanelProps {
  activeTab: string;
  activeScan?: ScanResult | null;
}

export const LeftVoiceAIPanel: React.FC<LeftVoiceAIPanelProps> = ({
  activeTab,
  activeScan,
}) => {
  const { language, t, currentLangObj } = useLanguage();
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [assistantState, setAssistantState] = useState<'idle' | 'listening' | 'processing' | 'speaking'>('idle');
  const [textInput, setTextInput] = useState('');
  const [isSpeechPaused, setIsSpeechPaused] = useState(false);
  const [messages, setMessages] = useState<any[]>([]);

  const chatBottomRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);

  // Global Keyboard Shortcut: Alt+V toggles Left Voice Panel
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && (e.key === 'v' || e.key === 'V')) {
        e.preventDefault();
        setIsExpanded(prev => !prev);
      }
      if (e.key === 'Escape' && isExpanded) {
        setIsExpanded(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded]);

  // Initial greeting
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        {
          id: 'welcome',
          sender: 'bot',
          text: t('home.welcomeSubtitle'),
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }
  }, [language]);

  useEffect(() => {
    if (isExpanded) {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, assistantState, isExpanded]);

  // Listen to speechService state changes
  useEffect(() => {
    const unsubscribe = speechService.addListener((state) => {
      if (state === 'speaking') {
        setAssistantState('speaking');
        setIsSpeechPaused(false);
      } else if (state === 'paused') {
        setIsSpeechPaused(true);
      } else if (state === 'idle') {
        setAssistantState(prev => prev === 'speaking' ? 'idle' : prev);
        setIsSpeechPaused(false);
      }
    });
    return () => unsubscribe();
  }, []);

  // Cleanup speech synthesis on unmount
  useEffect(() => {
    return () => {
      speechService.stop();
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, []);

  // Speech Synthesis
  const speakText = (text: string) => {
    const clean = text.replace(/[*#_`]/g, '').trim();
    if (!clean) return;

    speechService.speak(clean, currentLangObj.code, {
      onStart: () => {
        setAssistantState('speaking');
        setIsSpeechPaused(false);
      },
      onEnd: () => {
        setAssistantState('idle');
        setIsSpeechPaused(false);
      },
      onError: () => {
        setAssistantState('idle');
        setIsSpeechPaused(false);
      },
    });
  };

  const handleStopSpeaking = () => {
    speechService.stop();
    setAssistantState('idle');
    setIsSpeechPaused(false);
  };

  const handleTogglePause = () => {
    if (isSpeechPaused) {
      speechService.resume();
      setIsSpeechPaused(false);
    } else {
      speechService.pause();
      setIsSpeechPaused(true);
    }
  };

  // Generate Current Page Voice Report
  const handleReadPageReport = () => {
    let reportText = '';
    const langCode = language;

    if (activeTab === 'results' && activeScan) {
      reportText = metrologyAdvisorEngine.generateSpokenReport(activeScan, langCode);
    } else if (activeTab === 'dashboard') {
      reportText = langCode === 'ta'
        ? 'சட்ட அளவியல் தேசிய பதிவு முகப்புப் பக்கம். பொட்டலப் பொருட்கள் விதிகள் 2011-ன் கீழ் ஆய்வுகள், இணக்க விகிதங்கள் மற்றும் சமீபத்திய பதிவுகள் இங்கே காட்டப்பட்டுள்ளன.'
        : langCode === 'hi'
        ? 'विधिक मापविज्ञान राष्ट्रीय रजिस्ट्री डैशबोर्ड। पैकेज्ड कमोडिटी नियम 2011 के तहत कुल स्कैन, अनुपालन दर और हालिया निरीक्षण यहाँ उपलब्ध हैं।'
        : 'National Legal Metrology Registry Dashboard. Showing automated compliance rate, inspected packaged commodities, flagged violations, and recent scans under PCR 2011.';
    } else if (activeTab === 'upload') {
      reportText = langCode === 'ta'
        ? 'புதிய பொருள் பதிவேற்ற பக்கம். பொட்டலப் படங்களை பதிவேற்றவும் அல்லது மின்-வணிக இணைப்பை உள்ளிடவும்.'
        : langCode === 'hi'
        ? 'नया उत्पाद अपलोड पृष्ठ। विधिक मापविज्ञान नियमों के विरुद्ध निरीक्षण के लिए छवियां अपलोड करें।'
        : 'New Scan Upload page. Upload packaged product panel images or provide an e-commerce URL to inspect mandatory statutory declarations.';
    } else if (activeTab === 'review') {
      reportText = langCode === 'ta'
        ? 'ஆய்வாளர் மதிப்பாய்வு வரிசை. குறைந்த நம்பிக்கை அல்லது கூடுதல் ஆய்வு தேவைப்படும் பொருட்கள் இங்கே பட்டியலிடப்பட்டுள்ளன.'
        : 'Inspector Review Queue. Packaging scans flagged with low confidence or statutory warnings awaiting officer sign-off.';
    } else if (activeTab === 'rules') {
      reportText = 'Rules Registry. Official statutory repository for Legal Metrology Act 2009, PCR 2011 amendments, and Schedule II font height standards.';
    } else if (activeTab === 'audit') {
      reportText = 'Gazette Audit Trail. Immutable audit logs with timestamped verification records for Legal Metrology legal chains.';
    } else {
      reportText = `You are on the ${activeTab} page of the Legal Metrology Compliance Scanner.`;
    }

    speakText(reportText);
  };

  // Query processing
  const handleQuery = (queryText: string) => {
    if (!queryText || !queryText.trim()) return;
    handleStopSpeaking();

    const userMsg = {
      id: `u-${Date.now()}`,
      sender: 'user',
      text: queryText.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages(prev => [...prev, userMsg]);
    setTextInput('');
    setAssistantState('processing');

    try {
      const response = metrologyAdvisorEngine.processQuery(queryText, language, activeScan || undefined);
      const botMsg = {
        id: `b-${Date.now()}`,
        sender: 'bot',
        text: response.directAnswer,
        spokenText: response.spokenText,
        statutoryRule: response.statutoryRule,
        recommendation: response.recommendation,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages(prev => [...prev, botMsg]);
      speakText(response.spokenText);
    } catch {
      setAssistantState('idle');
    }
  };

  // STT Mic
  const handleMicToggle = () => {
    if (assistantState === 'listening') {
      if (recognitionRef.current) recognitionRef.current.stop();
      setAssistantState('idle');
      return;
    }

    handleStopSpeaking();
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) {
      alert('Speech recognition is not supported in this browser.');
      return;
    }

    try {
      const rec = new SpeechRec();
      rec.lang = currentLangObj.voiceLang;
      rec.continuous = false;
      rec.interimResults = false;

      rec.onstart = () => setAssistantState('listening');
      rec.onresult = (e: any) => {
        const text = e.results[0][0]?.transcript;
        if (text) handleQuery(text);
        else setAssistantState('idle');
      };
      rec.onerror = () => setAssistantState('idle');
      rec.onend = () => setAssistantState(prev => (prev === 'listening' ? 'idle' : prev));

      recognitionRef.current = rec;
      rec.start();
    } catch {
      setAssistantState('idle');
    }
  };

  return (
    <>
      {/* Invisible Screen Reader Status Announcer */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {assistantState === 'listening' ? t('voiceAI.statusListening') :
         assistantState === 'speaking' ? t('voiceAI.statusSpeaking') :
         assistantState === 'processing' ? t('voiceAI.statusProcessing') : t('voiceAI.statusIdle')}
      </div>

      {/* Persistent Left-Side Dock / Sidebar */}
      <aside
        aria-label="Voice AI Assistant Dock"
        role="region"
        className={`fixed left-0 top-16 bottom-0 z-40 transition-all duration-300 ease-in-out flex flex-col border-r border-[#2A3F55] bg-[#121D28] text-white shadow-2xl ${
          isExpanded ? 'w-80 sm:w-96' : 'w-14 sm:w-16'
        }`}
      >
        {/* Dock Header & Toggle Button */}
        <div className="p-3 border-b border-[#2A3F55] flex items-center justify-between bg-[#1C2B3A] shrink-0">
          {isExpanded ? (
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="p-1.5 rounded-none bg-[#2A3F55] border border-[#3E5671] text-emerald-300">
                <Sparkles className="w-4 h-4" />
              </div>
              <div className="truncate">
                <h3 className="font-serif font-bold text-xs text-white tracking-wide uppercase">{t('voiceAI.title')}</h3>
                <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1 font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  {currentLangObj.nativeName} ({currentLangObj.code.toUpperCase()})
                </span>
              </div>
            </div>
          ) : (
            <div className="mx-auto text-center" title={t('voiceAI.title')}>
              <Sparkles className="w-5 h-5 text-emerald-400" />
            </div>
          )}

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 rounded-none bg-[#2A3F55] hover:bg-[#3E5671] text-white transition"
            aria-label={isExpanded ? t('voiceAI.collapseDock') : t('voiceAI.expandDock')}
            title={isExpanded ? `${t('voiceAI.collapseDock')} (Alt+V)` : `${t('voiceAI.expandDock')} (Alt+V)`}
          >
            {isExpanded ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>

        {/* Compact Dock Actions (when collapsed) */}
        {!isExpanded && (
          <div className="flex-1 py-4 flex flex-col items-center justify-between gap-4">
            <div className="space-y-3 flex flex-col items-center">
              {/* Mic Trigger */}
              <button
                type="button"
                onClick={() => {
                  setIsExpanded(true);
                  handleMicToggle();
                }}
                className={`relative w-10 h-10 rounded-full flex items-center justify-center transition-all shadow-md ${
                  assistantState === 'listening'
                    ? 'bg-rose-600 text-white animate-pulse ring-4 ring-rose-500/30'
                    : 'bg-[#1C2B3A] hover:bg-[#2A3F55] text-white border border-[#3E5671]'
                }`}
                title={t('voiceAI.tapToSpeak')}
                aria-label={t('voiceAI.tapToSpeak')}
              >
                <Mic className="w-5 h-5 text-emerald-300" />
              </button>

              {/* Read Page Audio Trigger */}
              <button
                type="button"
                onClick={handleReadPageReport}
                className={`p-2.5 rounded-none border transition ${
                  assistantState === 'speaking'
                    ? 'bg-[#2A3F55] text-emerald-300 border-emerald-500'
                    : 'bg-[#1C2B3A] hover:bg-[#2A3F55] text-[#94A3B8] hover:text-white border-[#2A3F55]'
                }`}
                title={t('voiceAI.readPageReport')}
                aria-label={t('voiceAI.readPageReport')}
              >
                <Volume2 className="w-4 h-4" />
              </button>
            </div>

            {/* Vertical Language Indicator */}
            <button
              type="button"
              onClick={() => setIsExpanded(true)}
              className="px-1.5 py-2 rounded-none bg-[#1C2B3A] text-[10px] font-mono font-bold text-emerald-300 uppercase tracking-widest border border-[#2A3F55] hover:border-emerald-400 transition"
              title={`${t('common.activeLanguage')}: ${currentLangObj.name}`}
            >
              {currentLangObj.code}
            </button>
          </div>
        )}

        {/* Expanded Sidebar Body */}
        {isExpanded && (
          <div className="flex-1 flex flex-col overflow-hidden bg-[#121D28]">
            {/* Quick Page Audio Ribbon */}
            <div className="p-3 bg-[#16222F] border-b border-[#2A3F55] flex items-center justify-between gap-2">
              <button
                type="button"
                onClick={handleReadPageReport}
                className="flex-1 flex items-center justify-center gap-2 py-2 px-3 bg-[#1C2B3A] hover:bg-[#2A3F55] text-[#F1F5F9] border border-[#2A3F55] text-xs font-bold transition shadow-xs"
              >
                <Volume2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>{t('voiceAI.readPageReport')}</span>
              </button>

              {assistantState === 'speaking' && (
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={handleTogglePause}
                    className="p-2 bg-[#1C2B3A] hover:bg-[#2A3F55] text-[#F1F5F9] border border-[#2A3F55]"
                    title={isSpeechPaused ? t('common.resumeVoice') : t('common.pauseVoice')}
                  >
                    {isSpeechPaused ? <Play className="w-3.5 h-3.5 text-emerald-400" /> : <Pause className="w-3.5 h-3.5 text-amber-400" />}
                  </button>
                  <button
                    type="button"
                    onClick={handleStopSpeaking}
                    className="p-2 bg-rose-900/60 hover:bg-rose-900 text-rose-200 border border-rose-700"
                    title={t('common.stopVoice')}
                  >
                    <VolumeX className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>

            {/* Central Glowing Mic Orb */}
            <div className="p-4 bg-[#16222F] border-b border-[#2A3F55] flex flex-col items-center text-center">
              <button
                type="button"
                onClick={handleMicToggle}
                className={`relative w-16 h-16 rounded-full flex items-center justify-center shadow-md transition-all duration-300 transform active:scale-95 ${
                  assistantState === 'listening'
                    ? 'bg-rose-600 text-white ring-8 ring-rose-500/30 scale-105'
                    : assistantState === 'speaking'
                    ? 'bg-emerald-600 text-white ring-8 ring-emerald-500/30'
                    : 'bg-[#1C2B3A] hover:bg-[#2A3F55] text-white border border-[#3E5671] ring-4 ring-[#2A3F55]/30'
                }`}
                aria-label={assistantState === 'listening' ? t('voiceAI.stopListening') : t('voiceAI.tapToSpeak')}
              >
                {assistantState === 'listening' ? <MicOff className="w-6 h-6 text-rose-300" /> : <Mic className="w-6 h-6 text-emerald-300" />}
              </button>

              <p className="text-xs font-bold text-white mt-2.5">
                {assistantState === 'listening' ? t('voiceAI.statusListening') :
                 assistantState === 'speaking' ? t('voiceAI.statusSpeaking') :
                 assistantState === 'processing' ? t('voiceAI.statusProcessing') :
                 `${t('voiceAI.tapToSpeak')} (${currentLangObj.name})`}
              </p>
            </div>

            {/* Conversational Stream */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-[#121D28]">
              {messages.map(msg => (
                <div
                  key={msg.id}
                  className={`p-3 text-xs leading-relaxed border ${
                    msg.sender === 'user'
                      ? 'bg-[#2A3F55] text-white ml-4 border-[#3E5671]'
                      : 'bg-[#1C2B3A] border-[#2A3F55] text-[#F1F5F9] mr-2'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                  {msg.statutoryRule && (
                    <div className="mt-2 pt-1.5 border-t border-[#2A3F55] text-[10px] text-emerald-300 font-mono flex items-center gap-1 font-bold">
                      <Scale className="w-3 h-3 shrink-0" />
                      <span className="truncate">{msg.statutoryRule}</span>
                    </div>
                  )}
                  {msg.sender === 'bot' && msg.spokenText && (
                    <button
                      type="button"
                      onClick={() => speakText(msg.spokenText)}
                      className="mt-2 inline-flex items-center gap-1 text-[10px] text-emerald-400 hover:text-emerald-300 font-bold"
                      title="Replay Voice Audio"
                    >
                      <Volume2 className="w-3 h-3" />
                      <span>Replay Audio</span>
                    </button>
                  )}
                </div>
              ))}
              <div ref={chatBottomRef} />
            </div>

            {/* Input Bar */}
            <div className="p-3 bg-[#16222F] border-t border-[#2A3F55] flex items-center gap-2">
              <input
                type="text"
                value={textInput}
                onChange={e => setTextInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleQuery(textInput)}
                placeholder={t('voiceAI.askPlaceholder')}
                className="flex-1 bg-[#1C2B3A] border border-[#2A3F55] px-3 py-2 text-xs text-white placeholder:text-[#64748B] focus:outline-none focus:border-emerald-500"
              />
              <button
                type="button"
                onClick={() => handleQuery(textInput)}
                disabled={!textInput.trim()}
                className="p-2 bg-[#2A3F55] hover:bg-[#3E5671] disabled:opacity-40 text-white font-bold transition border border-[#3E5671]"
              >
                <Send className="w-3.5 h-3.5 text-emerald-300" />
              </button>
            </div>

            {/* Accessibility Footer */}
            <div className="px-3 py-1.5 bg-[#1C2B3A] text-[10px] text-[#94A3B8] font-mono border-t border-[#2A3F55] flex items-center justify-between">
              <span className="flex items-center gap-1">
                <Keyboard className="w-3 h-3" />
                <span>Alt+V to toggle</span>
              </span>
              <span>WCAG 2.1 AA</span>
            </div>
          </div>
        )}
      </aside>
    </>
  );
};
