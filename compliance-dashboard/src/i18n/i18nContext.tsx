import React, { createContext, useContext, useState, useEffect } from 'react';
import { en } from './strings/en';
import { ta } from './strings/ta';
import { hi } from './strings/hi';
import { te } from './strings/te';
import { kn } from './strings/kn';
import { ml } from './strings/ml';

export interface LanguageMeta {
  code: string;
  name: string;
  nativeName: string;
  voiceLang: string;
  flag: string;
}

export const SUPPORTED_LANGUAGES: LanguageMeta[] = [
  { code: 'en', name: 'English', nativeName: 'English', voiceLang: 'en-IN', flag: '🇬🇧' },
  { code: 'ta', name: 'Tamil', nativeName: 'தமிழ்', voiceLang: 'ta-IN', flag: '🇮🇳' },
  { code: 'hi', name: 'Hindi', nativeName: 'हिन्दी', voiceLang: 'hi-IN', flag: '🇮🇳' },
  { code: 'te', name: 'Telugu', nativeName: 'తెలుగు', voiceLang: 'te-IN', flag: '🇮🇳' },
  { code: 'kn', name: 'Kannada', nativeName: 'ಕನ್ನಡ', voiceLang: 'kn-IN', flag: '🇮🇳' },
  { code: 'ml', name: 'Malayalam', nativeName: 'മലയാളം', voiceLang: 'ml-IN', flag: '🇮🇳' },
];

const translations: Record<string, any> = { en, ta, hi, te, kn, ml };

interface LanguageContextType {
  language: string;
  setLanguage: (code: string) => void;
  t: (key: string) => string;
  languages: LanguageMeta[];
  currentLangObj: LanguageMeta;
}

const LanguageContext = createContext<LanguageContextType>({
  language: 'en',
  setLanguage: () => {},
  t: (key: string) => key,
  languages: SUPPORTED_LANGUAGES,
  currentLangObj: SUPPORTED_LANGUAGES[0],
});

const STORAGE_KEY = 'compliance_scanner_lang';
const LEGACY_STORAGE_KEY = 'lm_app_language';

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY);
      if (saved && SUPPORTED_LANGUAGES.some(l => l.code === saved)) {
        return saved;
      }
    }
    return 'en';
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, language);
      localStorage.setItem(LEGACY_STORAGE_KEY, language);
      document.documentElement.lang = language;
    }
  }, [language]);

  const setLanguage = (code: string) => {
    if (SUPPORTED_LANGUAGES.some(l => l.code === code)) {
      setLanguageState(code);
    }
  };

  const currentLangObj = SUPPORTED_LANGUAGES.find(l => l.code === language) || SUPPORTED_LANGUAGES[0];

  const t = (key: string): string => {
    const keys = key.split('.');
    let val = translations[language];
    let fallbackVal = translations['en'];

    for (const k of keys) {
      val = val ? val[k] : undefined;
      fallbackVal = fallbackVal ? fallbackVal[k] : undefined;
    }

    return (val || fallbackVal || key) as string;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, languages: SUPPORTED_LANGUAGES, currentLangObj }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => useContext(LanguageContext);
