import React, { useState } from 'react';
import { Globe, Check, ChevronDown } from 'lucide-react';
import { useLanguage, SUPPORTED_LANGUAGES } from '../i18n/i18nContext';

interface LanguageSelectorProps {
  variant?: 'prominent' | 'compact';
  className?: string;
}

export const LanguageSelector: React.FC<LanguageSelectorProps> = ({
  variant = 'compact',
  className = '',
}) => {
  const { language, setLanguage, t, currentLangObj } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);

  if (variant === 'prominent') {
    return (
      <section
        className={`glass-card border border-slate-800 rounded-2xl p-5 sm:p-6 shadow-sm relative overflow-hidden ${className}`}
        aria-labelledby="lang-selector-heading"
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-slate-800/60 border border-slate-800 flex items-center justify-center text-slate-100">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <h2 id="lang-selector-heading" className="text-sm sm:text-base font-bold text-white flex items-center gap-2">
                <span>{t('home.languageSectionTitle')}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-950/40 text-indigo-300 border border-indigo-500/30 font-bold">
                  6 Indian Languages
                </span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                {t('home.languageSectionSubtitle')}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span>{t('common.activeLanguage')}:</span>
            <span className="px-2.5 py-1 rounded-lg bg-indigo-950/40 text-indigo-300 font-bold border border-indigo-500/30">
              {currentLangObj.nativeName} ({currentLangObj.name})
            </span>
          </div>
        </div>

        {/* 6-Card Language Selection Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5" role="radiogroup" aria-label="Select platform language">
          {SUPPORTED_LANGUAGES.map((item) => {
            const isSelected = language === item.code;
            return (
              <button
                key={item.code}
                type="button"
                role="radio"
                aria-checked={isSelected}
                onClick={() => setLanguage(item.code)}
                className={`p-3 rounded-xl border text-left transition-all duration-200 flex flex-col justify-between relative group ${
                  isSelected
                    ? 'bg-indigo-600 text-white border-indigo-500 shadow-md ring-2 ring-indigo-500/30 scale-[1.02]'
                    : 'bg-slate-900/80 hover:glass-card text-slate-100 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-start justify-between">
                  <span className="text-lg leading-none select-none">{item.flag}</span>
                  {isSelected && (
                    <span className="p-0.5 rounded-full glass-card text-indigo-400">
                      <Check className="w-3 h-3 stroke-[3]" />
                    </span>
                  )}
                </div>
                <div className="mt-2.5">
                  <div className={`font-bold text-sm leading-tight ${isSelected ? 'text-white' : 'text-white group-hover:text-indigo-400'}`}>
                    {item.nativeName}
                  </div>
                  <div className={`text-[11px] font-medium mt-0.5 ${isSelected ? 'text-indigo-400' : 'text-slate-400'}`}>
                    {item.name}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </section>
    );
  }

  // Compact Header / Nav Dropdown Variant
  return (
    <div className={`relative inline-block ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-xl glass-card hover:bg-slate-900/80 text-slate-100 border border-slate-800 text-xs font-semibold transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={t('common.changeLanguage')}
      >
        <Globe className="w-3.5 h-3.5 text-indigo-400" />
        <span>{currentLangObj.nativeName}</span>
        <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div
            className="absolute right-0 mt-2 w-48 rounded-xl glass-card border border-slate-800 shadow-xl p-1.5 z-50 animate-in fade-in zoom-in-95 duration-150"
            role="listbox"
          >
            <div className="px-2.5 py-1.5 text-[10px] font-mono text-slate-400 uppercase tracking-wider border-b border-slate-800/80 mb-1">
              {t('common.selectLanguage')}
            </div>
            {SUPPORTED_LANGUAGES.map((item) => {
              const isSelected = language === item.code;
              return (
                <button
                  key={item.code}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => {
                    setLanguage(item.code);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium transition ${
                    isSelected
                      ? 'bg-indigo-950/40 text-indigo-300 font-bold'
                      : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span>{item.flag}</span>
                    <span>{item.nativeName}</span>
                    <span className="text-[10px] text-slate-400 font-normal">({item.name})</span>
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-indigo-400" />}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};
