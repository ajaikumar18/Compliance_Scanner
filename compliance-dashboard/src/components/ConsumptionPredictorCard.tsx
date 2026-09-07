import React, { useState } from 'react';
import { Users, TrendingUp, AlertTriangle, CheckCircle2 } from 'lucide-react';
import type { ConsumptionPrediction } from '../types';
import { predictConsumption } from '../services/api';
import { useLanguage } from '../i18n/i18nContext';
import { AudioButton } from './AudioButton';

interface ConsumptionPredictorCardProps {
  data?: ConsumptionPrediction;
  category?: string;
  netQuantityRaw?: string;
  expiryDateStr?: string;
  lang?: string;
}

export const ConsumptionPredictorCard: React.FC<ConsumptionPredictorCardProps> = ({
  data,
  category = 'food',
  netQuantityRaw,
  expiryDateStr,
  lang,
}) => {
  const { t, language } = useLanguage();
  const activeLang = lang || language || 'en';
  const [householdSize, setHouseholdSize] = useState<number>(data?.household_size || 2);
  const [prediction, setPrediction] = useState<ConsumptionPrediction | undefined>(data);
  const [loading, setLoading] = useState(false);

  const handleHouseholdChange = async (size: number) => {
    setHouseholdSize(size);
    try {
      setLoading(true);
      const res = await predictConsumption(
        category,
        netQuantityRaw,
        size,
        expiryDateStr
      );
      setPrediction(res);
    } catch (err) {
      console.error('Consumption prediction calculation failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const active = prediction || data;

  if (!active) {
    return (
      <div className="bg-white border border-[#D8D2C6] p-5 text-center text-[#5A6E82] text-xs">
        <Users className="w-6 h-6 mx-auto mb-2 opacity-40 text-[#5A6E82]" />
        <p>No net quantity declaration available to model consumption schedule.</p>
      </div>
    );
  }

  const {
    net_quantity_g,
    daily_consumption_rate_g,
    estimated_duration_days,
    expected_depletion_date,
    waste_risk_detected,
    warning_message,
    summary,
    disclaimer,
  } = active;

  const getAudioText = () => {
    if (activeLang === 'ta') {
      return `வீட்டு உபயோக நுகர்வு கணிப்பு. ${householdSize} நபர் கொண்ட குடும்பத்திற்கு தோராயமாக ${estimated_duration_days} நாட்கள் நீடிக்கும். தினசரி நுகர்வு ${daily_consumption_rate_g} கிராம். எதிர்பார்க்கப்படும் தீர்ந்துபோகும் தேதி ${expected_depletion_date}.`;
    }
    if (activeLang === 'hi') {
      return `घरेलू खपत पूर्वानुमान। ${householdSize} सदस्यों के परिवार के लिए अनुमानित ${estimated_duration_days} दिन। दैनिक खपत ${daily_consumption_rate_g} ग्राम। अनुमानित समाप्ति तारीख ${expected_depletion_date}।`;
    }
    if (activeLang === 'te') {
      return `గృహ వినియోగ అంచనా. ${householdSize} వ్యక్తుల కుటుంబానికి సుమారు ${estimated_duration_days} రోజులు. రోజువారీ వాడకం ${daily_consumption_rate_g} గ్రాములు.`;
    }
    if (activeLang === 'kn') {
      return `ಮನೆಯ ಬಳಕೆಯ ಮುನ್ಸೂಚನೆ. ${householdSize} ವ್ಯಕ್ತಿಗಳ ಕುಟುಂಬಕ್ಕೆ ಅಂದಾಜು ${estimated_duration_days} ದಿನಗಳು. ದೈನಂದಿನ ಬಳಕೆ ${daily_consumption_rate_g} ಗ್ರಾಂ.`;
    }
    return `Household consumption prediction. Estimated duration is ${estimated_duration_days} days for a household of ${householdSize} people. Daily usage rate is ${daily_consumption_rate_g} grams. Expected finish date is ${expected_depletion_date}. ${waste_risk_detected && warning_message ? `Warning: ${warning_message}` : 'Optimal consumption: Pack will finish before expiry.'}`;
  };

  return (
    <div className="bg-white border border-[#D8D2C6] p-5 space-y-4 shadow-none rounded-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E2DDD5] pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-[#F7F5F0] border border-[#D8D2C6] text-[#1C2B3A]">
            <TrendingUp className="w-4 h-4 text-[#1C2B3A]" />
          </div>
          <div>
            <h3 className="text-sm font-serif font-bold text-[#1C2B3A]">{t('consumption.title')}</h3>
            <p className="text-[11px] text-[#5A6E82]">{t('consumption.subtitle')}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <AudioButton text={getAudioText()} lang={activeLang} size="sm" title="Listen to Consumption Forecast" />
          <span className="text-xs font-mono font-bold text-[#1C2B3A] bg-[#F7F5F0] border border-[#D8D2C6] px-2.5 py-1">
            Net: {net_quantity_g}g
          </span>
        </div>
      </div>

      {/* Household Size Selector */}
      <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-4 space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold text-[#1C2B3A] flex items-center gap-2">
            <Users className="w-4 h-4 text-[#1C2B3A]" />
            <span>{t('consumption.householdSize')}:</span>
          </label>
          <span className="text-sm font-bold text-[#1C2B3A] font-mono">
            {householdSize} {t('consumption.persons')}
          </span>
        </div>

        <input
          type="range"
          min="1"
          max="6"
          step="1"
          value={householdSize}
          onChange={e => handleHouseholdChange(parseInt(e.target.value, 10))}
          className="w-full accent-[#1C2B3A] bg-[#D8D2C6] h-2 cursor-pointer"
        />

        <div className="flex justify-between text-[10px] text-[#5A6E82] font-mono px-1">
          <span>1</span>
          <span>2</span>
          <span>3</span>
          <span>4</span>
          <span>5</span>
          <span>6+</span>
        </div>
      </div>

      {/* Output Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
        <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-3">
          <span className="text-[#5A6E82] font-medium block mb-1">{t('consumption.estDuration')}</span>
          <span className="text-base font-bold text-[#1C2B3A] font-mono">
            {loading ? '...' : `${estimated_duration_days} ${t('consumption.days')}`}
          </span>
        </div>

        <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-3">
          <span className="text-[#5A6E82] font-medium block mb-1">{t('consumption.dailyUsage')}</span>
          <span className="text-base font-bold text-[#1C2B3A] font-mono">
            {daily_consumption_rate_g}g <span className="text-xs font-normal text-[#5A6E82]">/ day</span>
          </span>
        </div>

        <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-3 col-span-2 sm:col-span-1">
          <span className="text-[#5A6E82] font-medium block mb-1">{t('consumption.runOutDate')}</span>
          <span className="text-sm font-bold text-[#1C2B3A] font-mono">
            {expected_depletion_date || 'N/A'}
          </span>
        </div>
      </div>

      {/* Warning or Optimal State Banner */}
      {waste_risk_detected ? (
        <div className="p-3 bg-[#FAF3E6] border border-[#DFBF82] text-xs text-[#B8862B] flex items-start gap-2.5">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-[#B8862B]" />
          <div>
            <span className="font-bold block text-[#B8862B]">{t('consumption.foodWasteWarning')}</span>
            <p className="mt-0.5 text-[#1C2B3A] leading-relaxed">{warning_message}</p>
          </div>
        </div>
      ) : (
        <div className="p-3 bg-[#EAF4EE] border border-[#9BC6AE] text-xs text-[#2F6F4E] flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-[#2F6F4E]" />
          <span className="font-medium">
            Optimal Consumption Rate: Commodity will be fully utilized prior to statutory expiry date.
          </span>
        </div>
      )}

      {/* Summary */}
      <p className="text-xs text-[#1C2B3A] bg-[#F7F5F0] border border-[#E2DDD5] p-3 leading-relaxed">
        {summary}
      </p>

      {disclaimer && (
        <p className="text-[10px] text-[#5A6E82] italic leading-relaxed">
          * {disclaimer}
        </p>
      )}
    </div>
  );
};
