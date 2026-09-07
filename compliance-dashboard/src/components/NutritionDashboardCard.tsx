import React, { useState } from 'react';
import { Activity, Apple, AlertCircle, FileText } from 'lucide-react';
import type { NutritionInfo } from '../types';
import { useLanguage } from '../i18n/i18nContext';
import { AudioButton } from './AudioButton';

interface NutritionDashboardCardProps {
  data?: NutritionInfo;
  lang?: string;
}

export const NutritionDashboardCard: React.FC<NutritionDashboardCardProps> = ({ data, lang }) => {
  const { t, language } = useLanguage();
  const activeLang = lang || language || 'en';
  const [viewMode, setViewMode] = useState<'both' | '100g' | 'serving'>('both');

  const getLocalizedNutrientName = (name: string): string => {
    const norm = name.toLowerCase().trim();
    const direct = t(`nutrition.${norm}`);
    if (direct && direct !== `nutrition.${norm}`) return direct;
    return name;
  };

  if (!data || !data.available || !data.nutrients || data.nutrients.length === 0) {
    return (
      <div className="bg-white border border-[#D8D2C6] p-5 space-y-3">
        <div className="flex items-center gap-2.5 border-b border-[#E2DDD5] pb-3">
          <div className="p-2 bg-[#F7F5F0] border border-[#D8D2C6] text-[#1C2B3A]">
            <Apple className="w-4 h-4 text-[#1C2B3A]" />
          </div>
          <div>
            <h3 className="text-sm font-serif font-bold text-[#1C2B3A]">{t('nutrition.title')}</h3>
            <p className="text-[11px] text-[#5A6E82]">{t('nutrition.subtitle')}</p>
          </div>
        </div>

        <div className="bg-[#FAF3E6] border border-[#DFBF82] p-4 flex items-start gap-3 text-xs text-[#B8862B]">
          <AlertCircle className="w-4 h-4 text-[#B8862B] shrink-0 mt-0.5" />
          <div>
            <span className="font-bold text-[#1C2B3A] block mb-1">
              {t('nutrition.noNutritionDetected')}
            </span>
            <p className="leading-relaxed text-[#5A6E82]">
              {data?.status_message || t('nutrition.noNutritionSub')}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const { serving_size, nutrients, ingredients } = data;

  const getAudioText = () => {
    const nutDesc = nutrients.map(n => `${n.name} ${n.per_serving}`).join(', ');
    if (activeLang === 'ta') {
      return `ஊட்டச்சத்து உண்மைகள். பரிமாறும் அளவு ${serving_size}. முக்கிய ஊட்டச்சத்துக்கள்: ${nutDesc}.`;
    }
    if (activeLang === 'hi') {
      return `पोषण संबंधी जानकारी। प्रति सर्विंग आकार ${serving_size}। प्रमुख पोषक तत्व: ${nutDesc}।`;
    }
    if (activeLang === 'te') {
      return `పోషకాహార వాస్తవాలు. సర్వింగ్ పరిమాణం ${serving_size}. పోషకాలు: ${nutDesc}.`;
    }
    if (activeLang === 'kn') {
      return `ಪೌಷ್ಠಿಕಾಂಶದ ಮಾಹಿತಿ. ಸರ್ವಿಂಗ್ ಗಾತ್ರ ${serving_size}. ಪೋಷಕಾಂಶಗಳು: ${nutDesc}.`;
    }
    return `Nutritional facts per serving ${serving_size}. ${nutrients.map(n => `${n.name} is ${n.per_serving}`).join('. ')}. Declared ingredients are ${ingredients || 'listed on packaging'}.`;
  };

  return (
    <div className="bg-white border border-[#D8D2C6] p-5 space-y-4 shadow-none rounded-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E2DDD5] pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-[#F7F5F0] border border-[#D8D2C6] text-[#1C2B3A]">
            <Activity className="w-4 h-4 text-[#1C2B3A]" />
          </div>
          <div>
            <h3 className="text-sm font-serif font-bold text-[#1C2B3A]">{t('nutrition.title')}</h3>
            <p className="text-[11px] text-[#5A6E82]">
              Per Serving ({serving_size}) vs Per 100g
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <AudioButton text={getAudioText()} lang={activeLang} size="sm" title="Listen to Nutritional Facts" />

          {/* View mode toggle */}
          <div className="flex items-center bg-[#F7F5F0] border border-[#D8D2C6] p-0.5 text-[11px]">
            <button
              onClick={() => setViewMode('both')}
              className={`px-2.5 py-1 transition ${viewMode === 'both' ? 'bg-[#1C2B3A] text-white font-bold' : 'text-[#5A6E82] hover:text-[#1C2B3A]'}`}
            >
              All
            </button>
            <button
              onClick={() => setViewMode('serving')}
              className={`px-2.5 py-1 transition ${viewMode === 'serving' ? 'bg-[#1C2B3A] text-white font-bold' : 'text-[#5A6E82] hover:text-[#1C2B3A]'}`}
            >
              Serving
            </button>
            <button
              onClick={() => setViewMode('100g')}
              className={`px-2.5 py-1 transition ${viewMode === '100g' ? 'bg-[#1C2B3A] text-white font-bold' : 'text-[#5A6E82] hover:text-[#1C2B3A]'}`}
            >
              100g
            </button>
          </div>
        </div>
      </div>

      {/* Nutrients Table */}
      <div className="overflow-x-auto border border-[#E2DDD5]">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-[#D8D2C6] text-[#1C2B3A] font-mono text-[11px] bg-[#F7F5F0] font-bold">
              <th className="py-2.5 px-4 font-bold">Nutrient</th>
              {(viewMode === 'both' || viewMode === 'serving') && (
                <th className="py-2.5 px-3 font-bold text-right">Per Serving</th>
              )}
              {(viewMode === 'both' || viewMode === '100g') && (
                <th className="py-2.5 px-3 font-bold text-right">Per 100g</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2DDD5]">
            {nutrients.map((item, idx) => (
              <tr key={idx} className="hover:bg-[#FAF8F5] transition">
                <td className="py-2 px-4 font-medium text-[#1C2B3A] capitalize">
                  {getLocalizedNutrientName(item.name)}
                </td>
                {(viewMode === 'both' || viewMode === 'serving') && (
                  <td className="py-2 px-3 text-right font-mono font-bold text-[#1C2B3A]">
                    {item.per_serving}
                  </td>
                )}
                {(viewMode === 'both' || viewMode === '100g') && (
                  <td className="py-2 px-3 text-right font-mono text-[#5A6E82]">
                    {item.per_100g}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Ingredients Box */}
      {ingredients && (
        <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-3 text-xs text-[#1C2B3A]">
          <span className="text-[#5A6E82] font-bold flex items-center gap-1.5 mb-1">
            <FileText className="w-3.5 h-3.5 text-[#5A6E82]" />
            Declared Ingredients:
          </span>
          <p className="leading-relaxed">{ingredients}</p>
        </div>
      )}
    </div>
  );
};
