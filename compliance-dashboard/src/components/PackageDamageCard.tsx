import React, { useState } from 'react';
import { ShieldAlert, AlertCircle, UploadCloud, CheckCircle2 } from 'lucide-react';
import type { PackageDamageAnalysis } from '../types';
import { checkPackageDamage } from '../services/api';
import { useLanguage } from '../i18n/i18nContext';
import { AudioButton } from './AudioButton';

interface PackageDamageCardProps {
  data?: PackageDamageAnalysis;
  onAnalysisUpdated?: (updated: PackageDamageAnalysis) => void;
  lang?: string;
}

export const PackageDamageCard: React.FC<PackageDamageCardProps> = ({
  data,
  onAnalysisUpdated,
  lang,
}) => {
  const { t, language } = useLanguage();
  const activeLang = lang || language || 'en';
  const [analyzing, setAnalyzing] = useState(false);
  const [currentData, setCurrentData] = useState<PackageDamageAnalysis | undefined>(data);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setAnalyzing(true);
      const res = await checkPackageDamage(file);
      setCurrentData(res);
      if (onAnalysisUpdated) {
        onAnalysisUpdated(res);
      }
    } catch (err) {
      console.error('Package damage check failed:', err);
      alert('Failed to analyze package damage. Please try again.');
    } finally {
      setAnalyzing(false);
    }
  };

  const active = currentData || data;

  if (!active) {
    return (
      <div className="bg-white border border-[#D8D2C6] p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-[#E2DDD5] pb-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-[#1C2B3A]" />
            <h3 className="text-sm font-serif font-bold text-[#1C2B3A]">{t('damage.title')}</h3>
          </div>
        </div>
        <p className="text-xs text-[#5A6E82]">{t('damage.subtitle')}</p>
        <label className="cursor-pointer inline-flex items-center gap-2 px-3.5 py-2 bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] text-xs font-semibold border border-[#D8D2C6] transition">
          <UploadCloud className="w-3.5 h-3.5 text-[#1C2B3A]" />
          <span>{t('damage.uploadDamage')}</span>
          <input type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />
        </label>
      </div>
    );
  }

  const { condition, condition_score, damage_detected, detected_issues, recommendation, disclaimer } = active;

  const getConditionBadge = () => {
    switch (condition) {
      case 'GOOD':
        return { bg: 'bg-[#EAF4EE]', border: 'border-[#9BC6AE]', text: 'text-[#2F6F4E]', label: t('damage.packageIntact') };
      case 'MINOR DAMAGE':
        return { bg: 'bg-[#FAF3E6]', border: 'border-[#DFBF82]', text: 'text-[#B8862B]', label: t('damage.damaged') };
      case 'SIGNIFICANT DAMAGE':
      case 'SEVERE DAMAGE':
      default:
        return { bg: 'bg-[#F9EBE9]', border: 'border-[#E09891]', text: 'text-[#A8342A]', label: t('damage.damaged') };
    }
  };

  const badge = getConditionBadge();

  // Multilingual voice text
  const getAudioText = () => {
    const issuesDesc = detected_issues && detected_issues.length > 0
      ? detected_issues.map(i => i.description).join('. ')
      : 'No physical tears, punctures, or crushed panels detected.';

    if (activeLang === 'ta') {
      return `பேக்கேஜிங் ஒருமைப்பாடு ஆய்வு. மேற்பரப்பு ஒருமைப்பாடு மதிப்பீடு நூற்றுக்கு ${condition_score}. நிலை: ${condition}. ${recommendation}`;
    }
    if (activeLang === 'hi') {
      return `पैकेज अखंडता निरीक्षण। सतह अखंडता स्कोर 100 में से ${condition_score}। स्थिति: ${condition}। ${recommendation}`;
    }
    if (activeLang === 'te') {
      return `ప్యాకేజీ సమగ్రత తనిఖీ. ఉపరితల స్కోరు 100 కి ${condition_score}. పరిస్థితి: ${condition}. ${recommendation}`;
    }
    if (activeLang === 'kn') {
      return `ಪ್ಯಾಕೇಜ್ ಸಮಗ್ರತೆ ಪರಿಶೀಲನೆ. ಮೇಲ್ಮೈ ಸ್ಕೋರ್ 100 ರಲ್ಲಿ ${condition_score}. ಸ್ಥಿತಿ: ${condition}. ${recommendation}`;
    }
    return `Package integrity check. Surface integrity score is ${condition_score} out of 100. Condition is assessed as ${condition}. ${issuesDesc} ${recommendation}`;
  };

  return (
    <div className="bg-white border border-[#D8D2C6] p-5 space-y-4 shadow-none rounded-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E2DDD5] pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-[#F7F5F0] border border-[#D8D2C6] text-[#1C2B3A]">
            <ShieldAlert className="w-4 h-4 text-[#1C2B3A]" />
          </div>
          <div>
            <h3 className="text-sm font-serif font-bold text-[#1C2B3A]">{t('damage.title')}</h3>
            <p className="text-[11px] text-[#5A6E82]">{t('damage.subtitle')}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <AudioButton text={getAudioText()} lang={activeLang} size="sm" title="Listen to Package Damage Assessment" />
          <span className={`px-2.5 py-1 text-xs font-mono font-bold border ${badge.bg} ${badge.border} ${badge.text}`}>
            {badge.label}
          </span>
        </div>
      </div>

      {/* Integrity Score Bar */}
      <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-4 flex items-center justify-between">
        <div>
          <span className="text-xs text-[#5A6E82] font-medium">{t('damage.surfaceScore')}</span>
          <p className="text-xl font-mono font-bold text-[#1C2B3A] mt-0.5">
            {condition_score}<span className="text-xs font-normal text-[#5A6E82]"> / 100</span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="cursor-pointer inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-[#EBE7DF] text-[#1C2B3A] text-xs font-semibold border border-[#D8D2C6] transition">
            <UploadCloud className="w-3.5 h-3.5 text-[#1C2B3A]" />
            <span>{analyzing ? 'Inspecting...' : t('damage.recheckAngle')}</span>
            <input type="file" accept="image/*" onChange={handleFileUpload} disabled={analyzing} className="hidden" />
          </label>
        </div>
      </div>

      {/* Detected Issues */}
      {damage_detected && detected_issues.length > 0 ? (
        <div className="space-y-2">
          <span className="text-xs font-bold text-[#1C2B3A] uppercase tracking-wider">Detected Physical Defects</span>
          <div className="space-y-1.5">
            {detected_issues.map((issue, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 text-xs bg-[#F7F5F0] border border-[#E2DDD5] p-2.5 text-[#1C2B3A]"
              >
                <AlertCircle className="w-3.5 h-3.5 text-[#A8342A] mt-0.5 shrink-0" />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-[#1C2B3A] capitalize">{issue.type.replace(/_/g, ' ')}</span>
                    <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 bg-white border border-[#D8D2C6] text-[#A8342A] font-bold">
                      {issue.severity} severity
                    </span>
                  </div>
                  <p className="text-[#5A6E82] text-[11px] mt-0.5">{issue.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-2 p-3 bg-[#EAF4EE] border border-[#9BC6AE] text-xs text-[#2F6F4E]">
          <CheckCircle2 className="w-4 h-4 text-[#2F6F4E] shrink-0" />
          <span className="font-medium">{t('damage.cleanDetected')}</span>
        </div>
      )}

      {/* Recommendation */}
      <div className="p-3 bg-[#F7F5F0] border border-[#E2DDD5] text-xs text-[#1C2B3A] leading-relaxed">
        <span className="font-bold text-[#1C2B3A] block mb-0.5">{t('damage.recommendation')}</span>
        <p>{recommendation}</p>
      </div>

      {disclaimer && (
        <p className="text-[10px] text-[#5A6E82] italic leading-relaxed">
          * {disclaimer}
        </p>
      )}
    </div>
  );
};
