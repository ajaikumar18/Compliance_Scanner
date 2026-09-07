import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, Mic, MicOff, Volume2, VolumeX, Send, X, Globe, Sparkles, 
  User, RefreshCw, Copy, Check 
} from 'lucide-react';
import { sendChatMessage } from '../services/api';
import type { ScanResult } from '../types';
import { useLanguage } from '../i18n/i18nContext';
import { speechService } from '../services/speechService';

interface Message {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
}

interface AIChatbotModalProps {
  isOpen: boolean;
  onClose: () => void;
  scan?: ScanResult;
}

const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English', speechCode: 'en-IN' },
  { code: 'hi', name: 'हिन्दी (Hindi)', speechCode: 'hi-IN' },
  { code: 'ta', name: 'தமிழ் (Tamil)', speechCode: 'ta-IN' },
  { code: 'te', name: 'తెలుగు (Telugu)', speechCode: 'te-IN' },
  { code: 'kn', name: 'ಕನ್ನಡ (Kannada)', speechCode: 'kn-IN' },
  { code: 'ml', name: 'മലയാളം (Malayalam)', speechCode: 'ml-IN' },
];

export const AIChatbotModal: React.FC<AIChatbotModalProps> = ({
  isOpen,
  onClose,
  scan,
}) => {
  const { language: globalLang, setLanguage: setGlobalLang } = useLanguage();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [selectedLang, setSelectedLang] = useState(globalLang || 'en');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    if (globalLang && globalLang !== selectedLang) {
      setSelectedLang(globalLang);
    }
  }, [globalLang]);

  const recognitionRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string>(`sess_${Date.now()}`);

  // Initial welcome message
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      const prodName = scan?.fields?.brand_name?.extracted_value || scan?.fields?.product_name?.extracted_value || scan?.product_name || 'this packaged product';
      const welcomeText = `Hello! I am your Legal Metrology & AI Product Assistant. I can answer questions about mandatory declarations, shelf-life, package integrity, and PCR 2011 compliance for ${prodName}. You can also ask in हिन्दी, தமிழ், తెలుగు, ಕನ್ನಡ, or മലയാളം!`;
      setMessages([
        {
          id: 'welcome',
          sender: 'bot',
          text: welcomeText,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }
  }, [isOpen, scan]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Listen to speechService state changes
  useEffect(() => {
    const unsubscribe = speechService.addListener((state) => {
      setIsSpeaking(state === 'speaking');
    });
    return () => unsubscribe();
  }, []);

  // Stop speech and mic when closed
  useEffect(() => {
    if (!isOpen) {
      speechService.stop();
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {}
      }
      setIsSpeaking(false);
      setIsListening(false);
    }
  }, [isOpen]);

  // Handle keyboard Escape to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        speechService.stop();
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Cleanup speech recognition and synthesis on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {}
      }
      speechService.stop();
    };
  }, []);

  if (!isOpen) return null;

  const currentLangObj = SUPPORTED_LANGUAGES.find(l => l.code === selectedLang) || SUPPORTED_LANGUAGES[0];

  const handleSendMessage = async (customText?: string) => {
    const text = (customText || inputText).trim();
    if (!text || loading) return;

    const userMsg: Message = {
      id: `user_${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setLoading(true);

    try {
      const scanId = scan?.scan_uid || (scan?.scan_id ? String(scan.scan_id) : undefined);
      const res = await sendChatMessage(
        text,
        scanId,
        selectedLang,
        sessionIdRef.current
      );

      const botMsg: Message = {
        id: `bot_${Date.now()}`,
        sender: 'bot',
        text: res.response,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages(prev => [...prev, botMsg]);

      // Auto TTS if voice was active
      if (isListening) {
        speakResponse(res.response);
      }
    } catch (err: any) {
      const errorMsg: Message = {
        id: `err_${Date.now()}`,
        sender: 'bot',
        text: `Sorry, I encountered an issue: ${err.message || 'Unable to connect to assistant'}. Please try again.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const toggleListening = () => {
    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) {
      alert('Speech recognition is not supported in this browser. Please use Chrome or Edge.');
      return;
    }

    try {
      const recognition = new SpeechRec();
      recognition.lang = currentLangObj.speechCode;
      recognition.continuous = false;
      recognition.interimResults = false;

      recognition.onstart = () => setIsListening(true);
      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0]?.transcript;
        if (transcript) {
          setInputText(transcript);
          handleSendMessage(transcript);
        }
        setIsListening(false);
      };
      recognition.onerror = () => setIsListening(false);
      recognition.onend = () => setIsListening(false);

      recognitionRef.current = recognition;
      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  const speakResponse = (text: string) => {
    speechService.speak(text, currentLangObj.code, {
      onStart: () => setIsSpeaking(true),
      onEnd: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  const stopSpeaking = () => {
    speechService.stop();
    setIsSpeaking(false);
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const quickPrompts = [
    'Is this product compliant with PCR 2011?',
    'What is the declared MRP and unit sale price?',
    'How many days remaining before expiry?',
    'Check package damage and seal integrity',
    'Who is the statutory manufacturer?',
  ];

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-3 sm:p-4 animate-in fade-in duration-200 font-sans cursor-pointer"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          stopSpeaking();
          onClose();
        }
      }}
    >
      <div 
        className="relative w-full max-w-2xl h-[90vh] max-h-[750px] bg-[#121D28] border border-[#2A3F55] rounded-none shadow-2xl overflow-hidden flex flex-col text-white cursor-default"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#2A3F55] bg-[#1C2B3A]">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 bg-[#2A3F55] border border-[#3E5671] flex items-center justify-center text-emerald-300 font-bold shadow-xs">
                <Bot className="w-6 h-6" />
              </div>
              <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-500 border-2 border-[#1C2B3A] rounded-full" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-serif font-bold text-white text-sm sm:text-base">AI Metrology Assistant</h3>
                <span className="text-[10px] bg-[#2A3F55] text-emerald-300 border border-[#3E5671] px-2 py-0.5 font-mono font-bold">
                  Voice Enabled
                </span>
              </div>
              <p className="text-xs text-[#94A3B8] truncate max-w-xs sm:max-w-sm">
                Ask anything regarding Legal Metrology compliance & product details
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Language Selector */}
            <div className="relative flex items-center bg-[#121D28] border border-[#2A3F55] px-2 py-1 text-xs">
              <Globe className="w-3.5 h-3.5 text-emerald-400 mr-1.5 shrink-0" />
              <select
                value={selectedLang}
                onChange={e => {
                  setSelectedLang(e.target.value);
                  setGlobalLang(e.target.value as any);
                }}
                className="bg-[#121D28] text-white text-xs font-bold focus:outline-none cursor-pointer pr-1"
              >
                {SUPPORTED_LANGUAGES.map(lang => (
                  <option key={lang.code} value={lang.code} className="bg-[#121D28] text-white">
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Prominent High-Contrast Close Button */}
            <button
              type="button"
              onClick={() => {
                stopSpeaking();
                onClose();
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2A3F55] hover:bg-rose-600 text-white text-xs font-bold transition border border-[#3E5671] hover:border-rose-500 shadow-sm cursor-pointer shrink-0"
              title="Close Assistant (Esc)"
              aria-label="Close Assistant"
            >
              <X className="w-4 h-4 text-rose-300" />
              <span>Close</span>
            </button>
          </div>
        </div>

        {/* Messages Stream */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4 bg-[#121D28]">
          {messages.map(msg => (
            <div
              key={msg.id}
              className={`flex items-start gap-3 ${msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
            >
              <div className={`w-8 h-8 flex items-center justify-center text-xs shrink-0 ${
                msg.sender === 'user'
                  ? 'bg-[#2A3F55] text-white font-bold'
                  : 'bg-[#1C2B3A] text-emerald-300 border border-[#2A3F55]'
              }`}>
                {msg.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div className={`group relative max-w-[82%] sm:max-w-[75%] px-4 py-3 text-xs sm:text-sm leading-relaxed border ${
                msg.sender === 'user'
                  ? 'bg-[#2A3F55] text-white border-[#3E5671]'
                  : 'bg-[#1C2B3A] border-[#2A3F55] text-[#F1F5F9]'
              }`}>
                <p className="whitespace-pre-wrap">{msg.text}</p>
                <div className="flex items-center justify-between mt-2 pt-1 border-t border-[#2A3F55] text-[10px] text-[#94A3B8]">
                  <span>{msg.timestamp}</span>
                  {msg.sender === 'bot' && (
                    <div className="flex items-center gap-1.5 ml-2">
                      <button
                        onClick={() => copyToClipboard(msg.text, msg.id)}
                        className="hover:text-white p-0.5 transition"
                        title="Copy message"
                      >
                        {copiedId === msg.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      </button>
                      <button
                        onClick={() => isSpeaking ? stopSpeaking() : speakResponse(msg.text)}
                        className="hover:text-emerald-300 p-0.5 transition text-emerald-400"
                        title={isSpeaking ? 'Stop speaking' : 'Read aloud'}
                      >
                        {isSpeaking ? <VolumeX className="w-3 h-3 text-rose-400" /> : <Volume2 className="w-3 h-3" />}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-[#1C2B3A] text-emerald-400 border border-[#2A3F55] flex items-center justify-center">
                <Bot className="w-4 h-4" />
              </div>
              <div className="bg-[#1C2B3A] border border-[#2A3F55] px-4 py-3 flex items-center gap-2 text-xs text-[#94A3B8]">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                <span>Analyzing compliance records...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Prompts Carousel */}
        <div className="px-4 py-2 bg-[#16222F] border-t border-[#2A3F55] overflow-x-auto flex gap-2">
          {quickPrompts.map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(prompt)}
              className="text-xs font-medium text-[#F1F5F9] hover:text-white bg-[#1C2B3A] hover:bg-[#2A3F55] px-3 py-1.5 border border-[#2A3F55] hover:border-[#3E5671] whitespace-nowrap transition shrink-0 flex items-center gap-1"
            >
              <Sparkles className="w-3 h-3 text-emerald-400" />
              {prompt}
            </button>
          ))}
        </div>

        {/* Input Bar with Voice Controls */}
        <div className="p-3 sm:p-4 bg-[#16222F] border-t border-[#2A3F55] flex items-center gap-2">
          {/* Speech Mic Button */}
          <button
            type="button"
            onClick={toggleListening}
            className={`p-2.5 border transition flex items-center justify-center shrink-0 ${
              isListening
                ? 'bg-rose-900/60 border-rose-500 text-rose-200 animate-pulse'
                : 'bg-[#1C2B3A] hover:bg-[#2A3F55] text-[#94A3B8] hover:text-white border-[#2A3F55]'
            }`}
            title={isListening ? 'Stop listening' : `Speak in ${currentLangObj.name}`}
          >
            {isListening ? <MicOff className="w-4 h-4 text-rose-300" /> : <Mic className="w-4 h-4 text-emerald-400" />}
          </button>

          {/* Text Input */}
          <div className="flex-1 relative">
            <input
              type="text"
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
              placeholder={isListening ? `Listening in ${currentLangObj.name}...` : `Ask in ${currentLangObj.name} or English...`}
              disabled={loading}
              className="w-full bg-[#1C2B3A] border border-[#2A3F55] px-4 py-2.5 text-xs sm:text-sm text-white placeholder:text-[#64748B] focus:outline-none focus:border-emerald-500 transition"
            />
          </div>

          {/* Send Button */}
          <button
            type="button"
            onClick={() => handleSendMessage()}
            disabled={!inputText.trim() || loading}
            className="p-2.5 bg-[#2A3F55] hover:bg-[#3E5671] disabled:opacity-40 text-white font-bold transition shrink-0 border border-[#3E5671] cursor-pointer"
            title="Send query"
          >
            <Send className="w-4 h-4 text-emerald-300" />
          </button>

          {/* Secondary Bottom Close Button */}
          <button
            type="button"
            onClick={() => {
              stopSpeaking();
              onClose();
            }}
            className="px-3 py-2.5 bg-[#1C2B3A] hover:bg-rose-900/60 text-[#94A3B8] hover:text-white border border-[#2A3F55] hover:border-rose-700 transition shrink-0 flex items-center gap-1.5 text-xs font-semibold cursor-pointer"
            title="Close Assistant (Esc)"
          >
            <X className="w-4 h-4 text-rose-300" />
            <span className="hidden sm:inline">Close</span>
          </button>
        </div>
      </div>
    </div>
  );
};
