import React from 'react';
import { Target, AlertTriangle } from 'lucide-react';
import type { AudienceSuitability } from '../types';
import { useLanguage } from '../i18n/i18nContext';
import { AudioButton } from './AudioButton';

interface AudienceSuitabilityCardProps {
  data?: AudienceSuitability;
  lang?: string;
}

export const AudienceSuitabilityCard: React.FC<AudienceSuitabilityCardProps> = ({ data, lang }) => {
  const { t, language } = useLanguage();
  const activeLang = lang || language || 'en';

  const getLocalizedAudience = (name: string): string => {
    const norm = name.toLowerCase();
    if (norm.includes('general')) return t('audience.generalConsumers');
    if (norm.includes('children') || norm.includes('youth')) return t('audience.childrenYouth');
    if (norm.includes('sugar') || norm.includes('diabetic')) return t('audience.sugarConscious');
    if (norm.includes('elder') || norm.includes('senior')) return t('audience.elderlyConsumers');
    return name;
  };

  const getLocalizedSuitability = (suitability: string): string => {
    const norm = suitability.toUpperCase();
    if (norm === 'SUITABLE') return t('audience.suitable');
    if (norm === 'MODERATE') return t('audience.moderate');
    if (norm.includes('NOT')) return t('audience.notAdvisable');
    return suitability;
  };

  if (!data || !data.profiles || data.profiles.length === 0) {
    return (
      <div className="bg-white border border-[#D8D2C6] p-5 text-center text-[#5A6E82] text-xs">
        <Target className="w-6 h-6 mx-auto mb-2 opacity-40 text-[#5A6E82]" />
        <p>No audience suitability profile available for this commodity category.</p>
      </div>
    );
  }

  const { profiles, allergen_notice, disclaimer } = data;

  const getBadgeStyle = (color: string) => {
    switch (color) {
      case 'emerald':
        return 'bg-[#EAF4EE] text-[#2F6F4E] border-[#9BC6AE]';
      case 'blue':
        return 'bg-[#EBF3FB] text-[#2B6CB0] border-[#90CDF4]';
      case 'amber':
        return 'bg-[#FAF3E6] text-[#B8862B] border-[#DFBF82]';
      case 'rose':
      default:
        return 'bg-[#F9EBE9] text-[#A8342A] border-[#E09891]';
    }
  };

  const getAudioText = () => {
    const profDesc = profiles.map(p => `${p.audience} suitability is ${p.suitability}`).join('. ');
    if (activeLang === 'ta') {
      return `இலக்கு நுகர்வோர் பொருத்தம் பகுப்பாய்வு. ${profiles.map(p => `${p.audience}: ${p.suitability}`).join(', ')}. ${allergen_notice ? `ஒவ்வாமை தகவல்: ${allergen_notice}` : ''}`;
    }
    if (activeLang === 'hi') {
      return `लक्षित उपभोक्ता उपयुक्तता मूल्यांकन। ${profiles.map(p => `${p.audience}: ${p.suitability}`).join(', ')}। ${allergen_notice ? `एलर्जी संबंधी सूचना: ${allergen_notice}` : ''}`;
    }
    if (activeLang === 'te') {
      return `లక్ష్య వినియోగదారుల అనుకూలత. ${profiles.map(p => `${p.audience}: ${p.suitability}`).join(', ')}.`;
    }
    if (activeLang === 'kn') {
      return `ಗುರಿ ಗ್ರಾಹಕರ ಸೂಕ್ತತೆ ಮೌಲ್ಯಮಾಪನ. ${profiles.map(p => `${p.audience}: ${p.suitability}`).join(', ')}.`;
    }
    return `Target audience suitability evaluation. ${profDesc}. ${allergen_notice ? `Declared allergen notice: ${allergen_notice}` : ''}`;
  };

  return (
    <div className="bg-white border border-[#D8D2C6] p-5 space-y-4 shadow-none rounded-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E2DDD5] pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-[#F7F5F0] border border-[#D8D2C6] text-[#1C2B3A]">
            <Target className="w-4 h-4 text-[#1C2B3A]" />
          </div>
          <div>
            <h3 className="text-sm font-serif font-bold text-[#1C2B3A]">{t('audience.title')}</h3>
            <p className="text-[11px] text-[#5A6E82]">{t('audience.subtitle')}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <AudioButton text={getAudioText()} lang={activeLang} size="sm" title="Listen to Target Audience Profile" />
          <span className="text-[11px] font-mono text-[#1C2B3A] bg-[#F7F5F0] px-2.5 py-1 border border-[#D8D2C6] font-bold">
            {t('audience.transparencyPortfolio')}
          </span>
        </div>
      </div>

      {/* Profiles Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {profiles.map((prof, idx) => (
          <div
            key={idx}
            className="bg-[#F7F5F0] border border-[#E2DDD5] p-3.5 space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="font-bold text-[#1C2B3A] text-xs">{getLocalizedAudience(prof.audience)}</span>
              <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 border ${getBadgeStyle(prof.badge_color)}`}>
                {getLocalizedSuitability(prof.suitability)}
              </span>
            </div>
            <p className="text-[11px] text-[#5A6E82] leading-relaxed">
              {prof.observation}
            </p>
          </div>
        ))}
      </div>

      {/* Allergen Notice Banner */}
      {allergen_notice && (
        <div className="flex items-start gap-2.5 p-3 bg-[#FAF3E6] border border-[#DFBF82] text-xs text-[#B8862B]">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-[#B8862B]" />
          <div>
            <span className="font-bold block text-[#1C2B3A]">{t('audience.allergens')}:</span>
            <p className="text-[11px] text-[#5A6E82] mt-0.5">{allergen_notice}</p>
          </div>
        </div>
      )}

      {/* Non-medical Disclaimer */}
      <div className="p-2.5 bg-[#F7F5F0] border border-[#E2DDD5] text-[10px] text-[#5A6E82] italic leading-relaxed">
        * {disclaimer}
      </div>
    </div>
  );
};
