import React from 'react';
import { Calendar, Clock, Leaf, Info } from 'lucide-react';
import type { ExpiryIntelligence } from '../types';
import { useLanguage } from '../i18n/i18nContext';
import { AudioButton } from './AudioButton';

interface ExpiryIntelligenceCardProps {
  data?: ExpiryIntelligence;
  lang?: string;
}

export const ExpiryIntelligenceCard: React.FC<ExpiryIntelligenceCardProps> = ({ data, lang }) => {
  const { t, language } = useLanguage();
  const activeLang = lang || language || 'en';

  if (!data) {
    return (
      <div className="bg-white border border-[#D8D2C6] p-5 text-center text-[#5A6E82] text-xs">
        <Clock className="w-6 h-6 mx-auto mb-2 opacity-40 text-[#5A6E82]" />
        <p>{t('expiry.noData')}</p>
      </div>
    );
  }

  const {
    manufacturing_date,
    expiry_date,
    days_remaining,
    is_expired,
    shelf_life_percent,
    status,
    badge_color,
    recommendation,
    food_waste_prevention_tip,
  } = data;

  const getStatusColor = () => {
    switch (badge_color) {
      case 'emerald':
        return { bg: 'bg-[#EAF4EE]', border: 'border-[#9BC6AE]', text: 'text-[#2F6F4E]', progress: 'bg-[#2F6F4E]' };
      case 'amber':
        return { bg: 'bg-[#FAF3E6]', border: 'border-[#DFBF82]', text: 'text-[#B8862B]', progress: 'bg-[#B8862B]' };
      case 'orange':
        return { bg: 'bg-[#FFF2E6]', border: 'border-[#F5B977]', text: 'text-[#C05621]', progress: 'bg-[#DD6B20]' };
      case 'rose':
      default:
        return { bg: 'bg-[#F9EBE9]', border: 'border-[#E09891]', text: 'text-[#A8342A]', progress: 'bg-[#A8342A]' };
    }
  };

  const style = getStatusColor();

  // Localized audio text for voice synthesis
  const getAudioText = () => {
    const mfg = manufacturing_date || 'declared on pack';
    const exp = expiry_date || 'declared on pack';
    if (activeLang === 'ta') {
      return `காலாவதி மற்றும் அடுக்கு வாழ்க்கை நுண்ணறிவு. தயாரிப்பு தேதி: ${mfg}. காலாவதி தேதி: ${exp}. நிலை: ${status}. ${recommendation} ${food_waste_prevention_tip || ''}`;
    }
    if (activeLang === 'hi') {
      return `एक्सपायरी एवं शेल्फ-लाइफ इंटेलिजेंस। विनिर्माण तारीख: ${mfg}। समाप्ति तारीख: ${exp}। स्थिति: ${status}। ${recommendation} ${food_waste_prevention_tip || ''}`;
    }
    if (activeLang === 'te') {
      return `గడువు మరియు షెల్ఫ్-లైఫ్ విశ్లేషణ. తయారీ తేదీ: ${mfg}. గడువు తేదీ: ${exp}. స్థితి: ${status}. ${recommendation}`;
    }
    if (activeLang === 'kn') {
      return `ಮುಕ್ತಾಯ ಮತ್ತು ಶೆಲ್ಫ್-ಲೈಫ್ ವರದಿ. ಉತ್ಪಾದನಾ ದಿನಾಂಕ: ${mfg}. ಮುಕ್ತಾಯ ದಿನಾಂಕ: ${exp}. ಸ್ಥಿತಿ: ${status}. ${recommendation}`;
    }
    return `Expiry intelligence summary. Manufacture date is ${mfg}. Expiry date is ${exp}. Shelf life status is ${status}. ${recommendation} ${food_waste_prevention_tip || ''}`;
  };

  return (
    <div className="bg-white border border-[#D8D2C6] p-5 space-y-4 shadow-none rounded-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E2DDD5] pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-[#F7F5F0] border border-[#D8D2C6] text-[#1C2B3A]">
            <Leaf className="w-4 h-4 text-[#2F6F4E]" />
          </div>
          <div>
            <h3 className="text-sm font-serif font-bold text-[#1C2B3A]">{t('expiry.title')}</h3>
            <p className="text-[11px] text-[#5A6E82]">{t('expiry.subtitle')}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <AudioButton text={getAudioText()} lang={activeLang} size="sm" title="Listen to Expiry Intelligence Advisory" />
          <span className={`px-2.5 py-1 text-xs font-mono font-bold border ${style.bg} ${style.border} ${style.text}`}>
            {status}
          </span>
        </div>
      </div>

      {/* Dates Grid */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-3">
          <span className="text-[#5A6E82] flex items-center gap-1.5 mb-1 font-medium">
            <Calendar className="w-3.5 h-3.5 text-[#5A6E82]" />
            {t('expiry.mfgDate')}:
          </span>
          <span className="font-mono font-bold text-[#1C2B3A] text-sm">
            {manufacturing_date || 'Declared on pack'}
          </span>
        </div>

        <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-3">
          <span className="text-[#5A6E82] flex items-center gap-1.5 mb-1 font-medium">
            <Clock className="w-3.5 h-3.5 text-[#1C2B3A]" />
            {t('expiry.expDate')}:
          </span>
          <span className="font-mono font-bold text-[#1C2B3A] text-sm">
            {expiry_date || 'Declared on pack'}
          </span>
        </div>
      </div>

      {/* Shelf Life Progress Bar */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs">
          <span className="text-[#5A6E82] font-medium">{t('expiry.shelfLifeRemaining')}</span>
          <span className="font-mono font-bold text-[#1C2B3A]">
            {is_expired ? '0%' : `${shelf_life_percent}%`}
            {days_remaining >= 0 && (
              <span className="text-[#5A6E82] ml-1.5 font-normal">
                ({days_remaining} {t('consumption.days')})
              </span>
            )}
          </span>
        </div>
        <div className="w-full h-2.5 bg-[#E8E4DC] overflow-hidden border border-[#D8D2C6]">
          <div
            className={`h-full transition-all duration-500 ${style.progress}`}
            style={{ width: `${Math.max(0, Math.min(100, shelf_life_percent))}%` }}
          />
        </div>
      </div>

      {/* Guidance Message */}
      <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-3 text-xs text-[#1C2B3A] leading-relaxed">
        <p className="font-medium">{recommendation}</p>
      </div>

      {/* Food Waste Prevention Tip */}
      {food_waste_prevention_tip && (
        <div className="flex items-start gap-2 text-[11px] text-[#1C2B3A] bg-[#FAF3E6] border border-[#DFBF82] p-2.5">
          <Info className="w-4 h-4 shrink-0 mt-0.5 text-[#B8862B]" />
          <span>{food_waste_prevention_tip}</span>
        </div>
      )}
    </div>
  );
};
