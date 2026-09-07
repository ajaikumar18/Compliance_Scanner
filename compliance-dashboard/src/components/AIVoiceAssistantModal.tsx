import React, { useState, useEffect, useRef } from 'react';
import { 
  Mic, 
  MicOff, 
  Volume2, 
  VolumeX, 
  Play, 
  Pause, 
  Send, 
  Sparkles, 
  Scale, 
  X, 
  Globe, 
  Keyboard, 
  User, 
  Bot, 
  Info 
} from 'lucide-react';
import type { ScanResult } from '../types';
import { metrologyAdvisorEngine } from '../services/metrologyAdvisorEngine';
import { useLanguage } from '../i18n/i18nContext';
import { speechService } from '../services/speechService';

interface AIVoiceAssistantModalProps {
  isOpen: boolean;
  onClose: () => void;
  scan?: ScanResult;
}

const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English', voiceLang: 'en-IN' },
  { code: 'ta', name: 'தமிழ் (Tamil)', voiceLang: 'ta-IN' },
  { code: 'hi', name: 'हिन्दी (Hindi)', voiceLang: 'hi-IN' },
  { code: 'te', name: 'తెలుగు (Telugu)', voiceLang: 'te-IN' },
  { code: 'kn', name: 'ಕನ್ನಡ (Kannada)', voiceLang: 'kn-IN' },
  { code: 'ml', name: 'മലയാളം (Malayalam)', voiceLang: 'ml-IN' },
];

export const AIVoiceAssistantModal: React.FC<AIVoiceAssistantModalProps> = ({
  isOpen,
  onClose,
  scan,
}) => {
  const { language: globalLang, setLanguage: setGlobalLang } = useLanguage();
  const [mode, setMode] = useState<'voice' | 'text'>('voice');
  const [assistantState, setAssistantState] = useState<'idle' | 'listening' | 'processing' | 'speaking'>('idle');
  const [lang, setLang] = useState(globalLang || 'en');
  const [textInput, setTextInput] = useState('');
  const [isSpeechPaused, setIsSpeechPaused] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('all');

  useEffect(() => {
    if (globalLang && globalLang !== lang) {
      setLang(globalLang);
    }
  }, [globalLang]);

  const chatBottomRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const currentLangObj = SUPPORTED_LANGUAGES.find(l => l.code === lang) || SUPPORTED_LANGUAGES[0];

  const getGreeting = (l: string) => {
    const rawName = scan?.fields?.brand_name?.extracted_value || scan?.product_name;
    const defaultName =
      l === 'ta' ? 'இந்த பொட்டலப் பொருள்' :
      l === 'hi' ? 'इस डिब्बाबंद वस्तु' :
      l === 'te' ? 'ఈ ప్యాక్ చేయబడిన వస్తువు' :
      l === 'kn' ? 'ಈ ಪ್ಯಾಕ್ ಮಾಡಿದ ಸರಕು' :
      l === 'ml' ? 'ഈ പാക്കേജ് ചെയ്ത ഉൽപ്പന്നം' :
      'this packaged commodity';
    const prodName = rawName || defaultName;
    if (l === 'ta') {
      return `வணக்கம்! நான் உங்கள் சட்ட அளவியல் AI குரல் வழிகாட்டி. ${prodName} தொடர்பான விதிமுறைகள், MRP விலை, காலாவதி தேதி, தயாரிப்பாளர் விவரங்கள் அல்லது நுகர்வோர் உரிமை குறித்து எதையும் கேட்கலாம்.`;
    }
    if (l === 'hi') {
      return `नमस्ते! मैं आपका विधिक मापविज्ञान AI वॉइस असिस्टेंट हूँ। ${prodName} के विधिक नियमों, MRP, निर्माण/एक्सपायरी तारीख, या उपभोक्ता अधिकारों के बारे में कुछ भी पूछें।`;
    }
    if (l === 'te') {
      return `నమస్కారం! నేను మీ లీగల్ మెట్రాలజీ AI వాయిస్ అసిస్టెంట్‌ని. ${prodName} నిబంధనలు, MRP ధర, గడువు తేదీ లేదా తయారీదారు వివరాల గురించి ఏదైనా అడగండి.`;
    }
    if (l === 'kn') {
      return `ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ ಕಾನೂನು ಮಾಪನಶಾಸ್ತ್ರ AI ಧ್ವನಿ ಸಹಾಯಕ. ${prodName} ನಿಯಮಗಳು, MRP ಬೆಲೆ, ಮುಕ್ತಾಯ ದಿನಾಂಕ ಅಥವಾ ತಯಾರಕರ ವಿವರಗಳ ಬಗ್ಗೆ ಏನನ್ನಾದರೂ ಕೇಳಿ.`;
    }
    if (l === 'ml') {
      return `നമസ്കാരം! ഞാൻ നിങ്ങളുടെ ലീഗൽ മെട്രോളജി AI വോയ്സ് അസിസ്റ്റന്റാണ്. ${prodName} സംബന്ധിച്ച നിയമങ്ങൾ, MRP വില, കാലാവധി തീയതി അല്ലെങ്കിൽ നിർമ്മാതാവിന്റെ വിവരങ്ങൾ എന്നിവയെക്കുറിച്ച് ചോദിക്കാം.`;
    }
    return `Hello! I am your Legal Metrology AI Voice Assistant. Ask me anything about statutory rules, declared MRP, expiry intelligence, packaging damage, or consumer rights for ${prodName}.`;
  };

  const [messages, setMessages] = useState<any[]>([
    {
      id: 'm-0',
      sender: 'bot',
      directAnswer: getGreeting('en'),
      spokenText: getGreeting('en'),
      statutoryRule: 'Legal Metrology (Packaged Commodities) Rules, 2011',
      recommendation: 'Ask any question or tap a suggested topic below.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  // Update greeting when language changes
  useEffect(() => {
    if (messages.length === 1 && messages[0].id === 'm-0') {
      const greeting = getGreeting(lang);
      setMessages([
        {
          id: 'm-0',
          sender: 'bot',
          directAnswer: greeting,
          spokenText: greeting,
          statutoryRule: 'Legal Metrology (Packaged Commodities) Rules, 2011',
          recommendation: 'Ask any question or tap a suggested topic below.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }
  }, [lang, scan]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, assistantState]);

  // Listen to speechService states
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

  // Stop speaking and recognition when modal is closed
  useEffect(() => {
    if (!isOpen) {
      speechService.stop();
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {}
      }
      setAssistantState('idle');
      setIsSpeechPaused(false);
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

  // Clean speech synthesis on unmount
  useEffect(() => {
    return () => {
      speechService.stop();
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {}
      }
    };
  }, []);

  if (!isOpen) return null;

  // Speech Synthesis
  const speakText = (text: string) => {
    const clean = text.replace(/[*#_`]/g, '').trim();
    if (!clean) return;

    setAssistantState('speaking');
    setIsSpeechPaused(false);

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

  // Process User Query
  const handleQuery = async (queryText: string) => {
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
      const localResponse = metrologyAdvisorEngine.processQuery(queryText, lang, scan);
      const finalSpoken = localResponse.spokenText;
      const finalAnswer = localResponse.directAnswer;
      const statutory = localResponse.statutoryRule;
      const rec = localResponse.recommendation;

      const botMsg = {
        id: `b-${Date.now()}`,
        sender: 'bot',
        directAnswer: finalAnswer,
        spokenText: finalSpoken,
        statutoryRule: statutory,
        recommendation: rec,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages(prev => [...prev, botMsg]);
      speakText(finalSpoken);
    } catch {
      const errorMsg = {
        id: `b-err-${Date.now()}`,
        sender: 'bot',
        directAnswer: 'Sorry, I encountered an issue accessing metrology rules. Please try asking again.',
        spokenText: 'Sorry, I could not process your question. Please try again.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, errorMsg]);
      setAssistantState('idle');
    }
  };

  // Speech-to-Text Recognition
  const handleMicClick = () => {
    if (assistantState === 'listening') {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setAssistantState('idle');
      return;
    }

    handleStopSpeaking();

    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) {
      alert('Speech recognition is not supported in this browser. Please use Chrome, Safari, or Edge.');
      return;
    }

    try {
      const recognition = new SpeechRec();
      recognition.lang = currentLangObj.voiceLang;
      recognition.continuous = false;
      recognition.interimResults = false;

      recognition.onstart = () => {
        setAssistantState('listening');
      };

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0]?.transcript;
        if (transcript) {
          handleQuery(transcript);
        } else {
          setAssistantState('idle');
        }
      };

      recognition.onerror = () => {
        setAssistantState('idle');
      };

      recognition.onend = () => {
        setAssistantState(prev => (prev === 'listening' ? 'idle' : prev));
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch {
      setAssistantState('idle');
    }
  };

  // Categorized Prompt Chips
  const categorizedQuestions: Record<string, Array<{ cat: string; icon: string; q: string }>> = {
    ta: [
      { cat: 'compliance', icon: '⚖️', q: 'இந்த தயாரிப்பு சட்டப்படி சரியானதா?' },
      { cat: 'pricing', icon: '💰', q: 'MRP விலை மற்றும் வரி விவரங்கள் என்ன?' },
      { cat: 'expiry', icon: '⏳', q: 'காலாவதி தேதி மற்றும் மீதமுள்ள நாட்கள்?' },
      { cat: 'quantity', icon: '📦', q: 'நிகர எடை விதிமுறைகளின்படி உள்ளதா?' },
      { cat: 'damage', icon: '🛡️', q: 'பேக்கேஜிங் சேதம் அல்லது கிழிசல் உள்ளதா?' },
      { cat: 'grievance', icon: '🏛️', q: 'நுகர்வோர் குறைதீர்க்கும் 1915 விவரங்கள்?' },
    ],
    hi: [
      { cat: 'compliance', icon: '⚖️', q: 'क्या यह उत्पाद विधिक मापविज्ञान नियमों के तहत वैध है?' },
      { cat: 'pricing', icon: '💰', q: 'घोषित MRP और टैक्स विवरण क्या हैं?' },
      { cat: 'expiry', icon: '⏳', q: 'एक्सपायरी तारीख और उपयोग की अवधि?' },
      { cat: 'quantity', icon: '📦', q: 'क्या शुद्ध वजन नियम 12 के अनुरूप है?' },
      { cat: 'damage', icon: '🛡️', q: 'पैकेज की सतह और सील की स्थिति?' },
      { cat: 'grievance', icon: '🏛️', q: 'राष्ट्रीय उपभोक्ता हेल्पलाइन 1915 पर शिकायत?' },
    ],
    te: [
      { cat: 'compliance', icon: '⚖️', q: 'ఈ ఉత్పత్తి నిబంధనల ప్రకారం చెల్లుబాటు అవుతుందా?' },
      { cat: 'pricing', icon: '💰', q: 'ప్రకటించిన MRP మరియు పన్ను వివరాలు ఏమిటి?' },
      { cat: 'expiry', icon: '⏳', q: 'గడువు తేదీ మరియు మిగిలిన రోజుల వివరాలు?' },
      { cat: 'quantity', icon: '📦', q: 'నికర పరిమాణం రూల్ 12 ప్రకారం ఉందా?' },
    ],
    kn: [
      { cat: 'compliance', icon: '⚖️', q: 'ಈ ಉತ್ಪನ್ನವು ಕಾನೂನು ಮಾಪನಶಾಸ್ತ್ರ ನಿಯಮಗಳ ಪ್ರಕಾರ ಮಾನ್ಯವಾಗಿದೆಯೇ?' },
      { cat: 'pricing', icon: '💰', q: 'ಘೋಷಿತ MRP ಮತ್ತು ತೆರಿಗೆ ವಿವರಗಳೇನು?' },
      { cat: 'expiry', icon: '⏳', q: 'ಮುಕ್ತಾಯ ದಿನಾಂಕ ಮತ್ತು ಉಳಿದ ದಿನಗಳು ಎಷ್ಟು?' },
    ],
    ml: [
      { cat: 'compliance', icon: '⚖️', q: 'ഈ ഉൽപ്പന്നം പിസിആർ 2011 നിയമങ്ങൾക്ക് അനുസൃതമാണോ?' },
      { cat: 'pricing', icon: '💰', q: 'പ്രഖ്യാപിച്ച എംആർപിയും നികുതി വിവരങ്ങളും എന്താണ്?' },
      { cat: 'expiry', icon: '⏳', q: 'കാലാവധി തീയതിയും ശേഷിക്കുന്ന ദിവസങ്ങളും എത്രയാണ്?' },
      { cat: 'quantity', icon: '📦', q: 'അളവ് നിയമം 12 അനുസരിച്ചാണോ?' },
      { cat: 'damage', icon: '🛡️', q: 'പാക്കേജ് കേടുപാടുകളും സീലും പരിശോധിക്കുക' },
    ],
    en: [
      { cat: 'compliance', icon: '⚖️', q: 'Is this product compliant with PCR 2011?' },
      { cat: 'pricing', icon: '💰', q: 'What is the declared MRP & unit sale price?' },
      { cat: 'expiry', icon: '⏳', q: 'How many shelf-life days remaining before expiry?' },
      { cat: 'quantity', icon: '📦', q: 'Does declared net quantity meet Rule 12 standard?' },
      { cat: 'damage', icon: '🛡️', q: 'Check package damage, punctures and seal integrity' },
      { cat: 'grievance', icon: '🏛️', q: 'How do I report overcharging to National Consumer Helpline 1915?' },
    ],
  };

  const activeQuestions = categorizedQuestions[lang] || categorizedQuestions['en'];
  const filteredQuestions = selectedCategory === 'all' 
    ? activeQuestions 
    : activeQuestions.filter(item => item.cat === selectedCategory);

  const categoryLabels: Record<string, string> = {
    all: 'All Questions',
    compliance: 'Compliance Rules',
    pricing: 'MRP & Pricing',
    expiry: 'Expiry & Shelf-life',
    quantity: 'Net Quantity',
    damage: 'Damage & Integrity',
    grievance: 'Consumer 1915',
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-3 sm:p-4 animate-in fade-in duration-200 font-sans cursor-pointer"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          handleStopSpeaking();
          onClose();
        }
      }}
    >
      <div 
        className="relative w-full max-w-2xl h-[92vh] max-h-[780px] bg-[#121D28] border border-[#2A3F55] rounded-none shadow-2xl overflow-hidden flex flex-col text-white cursor-default"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Official Banner */}
        <div className="px-5 sm:px-6 py-4 border-b border-[#2A3F55] bg-[#1C2B3A] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-none bg-[#2A3F55] border border-[#3E5671] flex items-center justify-center text-emerald-300 font-bold shadow-xs">
                <Sparkles className="w-5 h-5" />
              </div>
              <span className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#1C2B3A] ${
                assistantState === 'listening' ? 'bg-rose-500 animate-ping' :
                assistantState === 'speaking' ? 'bg-emerald-400 animate-pulse' :
                assistantState === 'processing' ? 'bg-amber-400 animate-spin' : 'bg-emerald-500'
              }`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-serif font-bold text-white text-sm sm:text-base">AI Metrology Voice Assistant</h3>
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 bg-[#2A3F55] text-emerald-300 border border-[#3E5671]">
                  {assistantState === 'listening' ? 'LISTENING...' :
                   assistantState === 'speaking' ? 'SPEAKING...' :
                   assistantState === 'processing' ? 'ANALYZING...' : 'ONLINE'}
                </span>
              </div>
              <p className="text-xs text-[#94A3B8] truncate max-w-xs sm:max-w-md">
                Interactive Multilingual Advisory • Legal Metrology (Packaged Commodities) Rules, 2011
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Language Selector */}
            <div className="flex items-center bg-[#121D28] border border-[#2A3F55] px-2.5 py-1.5 text-xs">
              <Globe className="w-3.5 h-3.5 text-emerald-400 mr-1.5 shrink-0" />
              <select
                value={lang}
                onChange={e => {
                  setLang(e.target.value);
                  setGlobalLang(e.target.value);
                }}
                className="bg-[#121D28] text-white text-xs font-bold focus:outline-none cursor-pointer pr-1"
              >
                {SUPPORTED_LANGUAGES.map(l => (
                  <option key={l.code} value={l.code} className="bg-[#121D28] text-white">
                    {l.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Prominent High-Contrast Close Button */}
            <button
              type="button"
              onClick={() => {
                handleStopSpeaking();
                onClose();
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2A3F55] hover:bg-rose-600 text-white text-xs font-bold transition border border-[#3E5671] hover:border-rose-500 shadow-sm cursor-pointer shrink-0"
              title="Close Voice Assistant (Esc)"
              aria-label="Close Voice Assistant"
            >
              <X className="w-4 h-4 text-rose-300" />
              <span>Close</span>
            </button>
          </div>
        </div>

        {/* Mode Switcher Tabs (Voice Mode vs Text Mode) */}
        <div className="px-6 py-2.5 bg-[#16222F] border-b border-[#2A3F55] flex items-center justify-between">
          <div className="flex items-center bg-[#121D28] p-1 border border-[#2A3F55] text-xs">
            <button
              onClick={() => setMode('voice')}
              className={`flex items-center gap-1.5 px-3 py-1.5 font-bold transition ${
                mode === 'voice' ? 'bg-[#2A3F55] text-white' : 'text-[#94A3B8] hover:text-white'
              }`}
            >
              <Mic className="w-3.5 h-3.5" />
              Voice Orb Mode
            </button>
            <button
              onClick={() => setMode('text')}
              className={`flex items-center gap-1.5 px-3 py-1.5 font-bold transition ${
                mode === 'text' ? 'bg-[#2A3F55] text-white' : 'text-[#94A3B8] hover:text-white'
              }`}
            >
              <Keyboard className="w-3.5 h-3.5" />
              Conversational Chat
            </button>
          </div>

          {assistantState === 'speaking' && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleTogglePause}
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white text-xs font-bold border border-[#2A3F55]"
              >
                {isSpeechPaused ? <Play className="w-3 h-3 text-emerald-400" /> : <Pause className="w-3 h-3 text-amber-400" />}
                <span>{isSpeechPaused ? 'Resume' : 'Pause'}</span>
              </button>
              <button
                onClick={handleStopSpeaking}
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-rose-900/60 hover:bg-rose-900 text-rose-200 text-xs font-bold border border-rose-700"
              >
                <VolumeX className="w-3 h-3" />
                <span>Stop</span>
              </button>
            </div>
          )}
        </div>

        {/* Central Voice Orb (Active in Voice Mode) */}
        {mode === 'voice' && (
          <div className="px-6 py-6 bg-[#16222F] border-b border-[#2A3F55] flex flex-col items-center justify-center text-center">
            {/* Pulsing Orb */}
            <div className="relative my-2 flex items-center justify-center">
              {assistantState === 'listening' && (
                <>
                  <div className="absolute w-28 h-28 rounded-full bg-rose-500/20 animate-ping pointer-events-none" />
                  <div className="absolute w-36 h-36 rounded-full bg-rose-500/10 animate-pulse pointer-events-none" />
                </>
              )}
              {assistantState === 'speaking' && (
                <>
                  <div className="absolute w-28 h-28 rounded-full bg-emerald-500/25 animate-ping pointer-events-none" />
                  <div className="absolute w-36 h-36 rounded-full bg-emerald-500/15 animate-pulse pointer-events-none" />
                </>
              )}

              {/* Main Glowing Mic Orb Button */}
              <button
                type="button"
                onClick={handleMicClick}
                className={`relative z-10 w-20 h-20 rounded-full flex items-center justify-center shadow-xl transition-all duration-300 transform active:scale-95 ${
                  assistantState === 'listening'
                    ? 'bg-rose-600 text-white ring-8 ring-rose-500/30 scale-105'
                    : assistantState === 'speaking'
                    ? 'bg-emerald-600 text-white ring-8 ring-emerald-500/30'
                    : 'bg-[#1C2B3A] hover:bg-[#2A3F55] text-white border-2 border-[#3E5671] ring-4 ring-[#2A3F55]/40 hover:scale-105'
                }`}
                title={assistantState === 'listening' ? 'Tap to stop listening' : 'Tap to speak'}
              >
                {assistantState === 'listening' ? (
                  <MicOff className="w-8 h-8" />
                ) : (
                  <Mic className="w-8 h-8 text-emerald-300" />
                )}
              </button>
            </div>

            {/* Orb Status Label */}
            <div className="mt-3">
              <p className="text-sm font-bold text-white tracking-wide">
                {assistantState === 'listening' ? `Listening in ${currentLangObj.name}...` :
                 assistantState === 'speaking' ? 'Speaking Legal Metrology Advisory...' :
                 assistantState === 'processing' ? 'Consulting Legal Metrology Rules...' :
                 `Tap Microphone to Speak in ${currentLangObj.name}`}
              </p>
              <p className="text-xs text-[#94A3B8] mt-0.5">
                {assistantState === 'listening' ? 'Speak clearly into your microphone' : 'Or select any question chip below'}
              </p>
            </div>
          </div>
        )}

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-[#121D28]">
          {messages.map(msg => (
            <div
              key={msg.id}
              className={`flex items-start gap-3 ${msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
            >
              <div className={`w-8 h-8 rounded-none flex items-center justify-center text-xs shrink-0 ${
                msg.sender === 'user'
                  ? 'bg-[#2A3F55] text-white font-bold'
                  : 'bg-[#1C2B3A] text-emerald-300 border border-[#2A3F55]'
              }`}>
                {msg.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div className={`relative max-w-[85%] rounded-none p-4 text-xs sm:text-sm leading-relaxed border ${
                msg.sender === 'user'
                  ? 'bg-[#2A3F55] text-white border-[#3E5671]'
                  : 'bg-[#1C2B3A] border-[#2A3F55] text-[#F1F5F9]'
              }`}>
                {/* Spoken Answer */}
                <p className="whitespace-pre-wrap text-[#F1F5F9]">{msg.directAnswer || msg.text}</p>

                {/* Statutory Rule Citation Tag */}
                {msg.statutoryRule && (
                  <div className="mt-2.5 pt-2 border-t border-[#2A3F55] flex items-center gap-1.5 text-[11px] text-emerald-300 font-mono font-bold">
                    <Scale className="w-3.5 h-3.5 shrink-0" />
                    <span>{msg.statutoryRule}</span>
                  </div>
                )}

                {/* Actionable Recommendation Tag */}
                {msg.recommendation && (
                  <div className="mt-1.5 flex items-start gap-1.5 text-[11px] text-[#94A3B8]">
                    <Info className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                    <span>{msg.recommendation}</span>
                  </div>
                )}

                {/* Audio Controls Footer on Bot Message */}
                {msg.sender === 'bot' && (
                  <div className="flex items-center justify-between mt-3 pt-2 border-t border-[#2A3F55] text-[10px] text-[#94A3B8]">
                    <span>{msg.timestamp}</span>
                    <button
                      onClick={() => speakText(msg.spokenText || msg.directAnswer)}
                      className="inline-flex items-center gap-1 text-xs font-bold text-emerald-400 hover:text-emerald-300 transition"
                      title="Listen aloud again"
                    >
                      <Volume2 className="w-3.5 h-3.5" />
                      <span>Listen Aloud</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {assistantState === 'processing' && (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-none bg-[#1C2B3A] text-emerald-400 border border-[#2A3F55] flex items-center justify-center">
                <Bot className="w-4 h-4" />
              </div>
              <div className="bg-[#1C2B3A] border border-[#2A3F55] px-4 py-3 text-xs text-[#94A3B8] flex items-center gap-2">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400 animate-spin" />
                <span>Evaluating Legal Metrology Act & Rules 2011...</span>
              </div>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        {/* Category Selector Tabs */}
        <div className="px-4 py-2 bg-[#16222F] border-t border-[#2A3F55] flex items-center gap-1.5 overflow-x-auto text-[11px]">
          {['all', 'compliance', 'pricing', 'expiry', 'quantity', 'damage', 'grievance'].map((catKey) => (
            <button
              key={catKey}
              onClick={() => setSelectedCategory(catKey)}
              className={`px-2.5 py-1 whitespace-nowrap transition font-bold ${
                selectedCategory === catKey
                  ? 'bg-[#2A3F55] text-white border border-[#3E5671]'
                  : 'text-[#94A3B8] hover:text-white'
              }`}
            >
              {categoryLabels[catKey]}
            </button>
          ))}
        </div>

        {/* Categorized Question Chips */}
        <div className="px-4 py-2.5 bg-[#121D28] border-t border-[#2A3F55] overflow-x-auto flex gap-2">
          {filteredQuestions.map((item, idx) => (
            <button
              key={idx}
              onClick={() => handleQuery(item.q)}
              className="text-xs font-medium text-[#F1F5F9] hover:text-white bg-[#1C2B3A] hover:bg-[#2A3F55] px-3 py-1.5 border border-[#2A3F55] hover:border-[#3E5671] whitespace-nowrap transition shrink-0 flex items-center gap-1.5"
            >
              <span>{item.icon}</span>
              <span>{item.q}</span>
            </button>
          ))}
        </div>

        {/* Input Bar (Voice Mic + Text + Close) */}
        <div className="p-3 sm:p-4 bg-[#16222F] border-t border-[#2A3F55] flex items-center gap-2">
          <button
            type="button"
            onClick={handleMicClick}
            className={`p-2.5 border transition flex items-center justify-center shrink-0 cursor-pointer ${
              assistantState === 'listening'
                ? 'bg-rose-900/60 border-rose-500 text-rose-200 animate-pulse'
                : 'bg-[#1C2B3A] hover:bg-[#2A3F55] text-[#94A3B8] hover:text-white border-[#2A3F55]'
            }`}
            title={assistantState === 'listening' ? 'Stop listening' : `Speak in ${currentLangObj.name}`}
          >
            {assistantState === 'listening' ? <MicOff className="w-4 h-4 text-rose-300" /> : <Mic className="w-4 h-4 text-emerald-400" />}
          </button>

          <input
            type="text"
            value={textInput}
            onChange={e => setTextInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleQuery(textInput)}
            placeholder={assistantState === 'listening' ? `Listening in ${currentLangObj.name}...` : `Type or speak in ${currentLangObj.name}...`}
            className="flex-1 bg-[#1C2B3A] border border-[#2A3F55] px-4 py-2.5 text-xs sm:text-sm text-white placeholder:text-[#64748B] focus:outline-none focus:border-emerald-500 transition"
          />

          <button
            type="button"
            onClick={() => handleQuery(textInput)}
            disabled={!textInput.trim() || assistantState === 'processing'}
            className="p-2.5 bg-[#2A3F55] hover:bg-[#3E5671] disabled:opacity-40 text-white font-bold transition shrink-0 border border-[#3E5671] cursor-pointer"
            title="Send query"
          >
            <Send className="w-4 h-4 text-emerald-300" />
          </button>

          {/* Secondary Bottom Close Button */}
          <button
            type="button"
            onClick={() => {
              handleStopSpeaking();
              onClose();
            }}
            className="px-3 py-2.5 bg-[#1C2B3A] hover:bg-rose-900/60 text-[#94A3B8] hover:text-white border border-[#2A3F55] hover:border-rose-700 transition shrink-0 flex items-center gap-1.5 text-xs font-semibold cursor-pointer"
            title="Close Voice Assistant (Esc)"
          >
            <X className="w-4 h-4 text-rose-300" />
            <span className="hidden sm:inline">Close</span>
          </button>
        </div>
      </div>
    </div>
  );
};
