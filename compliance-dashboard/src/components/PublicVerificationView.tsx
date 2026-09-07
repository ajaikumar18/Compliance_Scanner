import React, { useEffect, useState } from 'react';
import { 
  ShieldCheck, AlertTriangle, CheckCircle2, XCircle, ArrowLeft, 
  ExternalLink, Calendar, Package, DollarSign, Building2, PhoneCall, Globe,
  Leaf, Info, Award
} from 'lucide-react';
import { fetchPublicVerification } from '../services/api';

interface PublicVerificationViewProps {
  verificationId: string;
  onBack?: () => void;
}

export const PublicVerificationView: React.FC<PublicVerificationViewProps> = ({
  verificationId,
  onBack,
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<any>(null);

  useEffect(() => {
    async function loadProfile() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchPublicVerification(verificationId);
        setProfile(data);
      } catch (err: any) {
        setError(err.message || 'Unable to retrieve verification record.');
      } finally {
        setLoading(false);
      }
    }
    if (verificationId) {
      loadProfile();
    }
  }, [verificationId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F7F5F0] flex flex-col items-center justify-center p-6 text-[#1C2B3A] font-sans">
        <div className="w-12 h-12 border-4 border-[#1C2B3A]/20 border-t-[#1C2B3A] rounded-full animate-spin mb-4" />
        <p className="font-mono text-sm font-bold tracking-wide text-[#1C2B3A]">Verifying Legal Metrology Digital Certificate...</p>
        <p className="font-mono text-xs text-[#5A6E82] mt-1">{verificationId}</p>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="min-h-screen bg-[#F7F5F0] flex flex-col items-center justify-center p-6 font-sans">
        <div className="max-w-md w-full bg-white border border-[#D8D2C6] p-8 text-center shadow-md">
          <div className="w-14 h-14 bg-[#F9EBE9] border border-[#E09891] rounded-full flex items-center justify-center mx-auto mb-4 text-[#A8342A]">
            <AlertTriangle className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-serif font-bold text-[#1C2B3A]">Verification Record Not Found</h2>
          <p className="text-sm text-[#5A6E82] mt-2">
            The verification reference <span className="font-mono text-[#1C2B3A] font-bold">{verificationId}</span> could not be verified on the national Legal Metrology repository.
          </p>
          {onBack && (
            <button
              onClick={onBack}
              className="mt-6 inline-flex items-center gap-2 px-5 py-2.5 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white text-sm font-bold transition shadow-xs"
            >
              <ArrowLeft className="w-4 h-4" />
              Return to Platform
            </button>
          )}
        </div>
      </div>
    );
  }

  const isCompliant = profile.compliance_status === 'COMPLIANT';
  const dec = profile.declarations || {};

  return (
    <div className="min-h-screen bg-[#F7F5F0] text-[#1C2B3A] py-10 px-4 sm:px-6 flex flex-col items-center font-sans">
      {/* Top Banner */}
      <div className="w-full max-w-3xl flex items-center justify-between mb-6">
        {onBack ? (
          <button
            onClick={onBack}
            className="inline-flex items-center gap-2 text-sm font-bold text-[#5A6E82] hover:text-[#1C2B3A] transition"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </button>
        ) : (
          <a
            href="/"
            className="text-xs font-mono font-bold text-[#5A6E82] hover:text-[#1C2B3A] transition"
          >
            ← Home
          </a>
        )}

        <div className="text-right">
          <span className="text-[11px] font-mono text-[#5A6E82]">National Metrology Registry</span>
          <p className="text-xs font-mono text-[#1C2B3A] font-bold">{verificationId}</p>
        </div>
      </div>

      {/* Main Dossier Card */}
      <div className="w-full max-w-3xl bg-white border border-[#D8D2C6] shadow-md overflow-hidden">
        {/* Header Ribbon */}
        <div className="bg-[#1C2B3A] text-white px-6 sm:px-8 py-6 border-b border-[#2A3F55] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-[#2A3F55] border border-[#3E5671] flex items-center justify-center text-emerald-300 font-bold text-xl">
              <Award className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg sm:text-xl font-serif font-bold text-white">
                  {profile.brand_name || profile.product_name || 'Packaged Commodity'}
                </h1>
              </div>
              <p className="text-xs text-[#94A3B8] mt-0.5">
                Category: <span className="text-white font-bold capitalize">{profile.category || 'General Packaged Commodity'}</span> • Rule 6(1) Verification
              </p>
            </div>
          </div>

          {/* Compliance Status Badge */}
          <div className={`px-4 py-2 border flex items-center gap-2 self-start sm:self-auto ${
            isCompliant
              ? 'bg-[#EAF4EE] border-[#9BC6AE] text-[#2F6F4E]'
              : 'bg-[#F9EBE9] border-[#E09891] text-[#A8342A]'
          }`}>
            {isCompliant ? <CheckCircle2 className="w-5 h-5 text-[#2F6F4E]" /> : <XCircle className="w-5 h-5 text-[#A8342A]" />}
            <div>
              <div className="text-[10px] uppercase font-bold tracking-wider opacity-80">Metrology Status</div>
              <div className="text-sm font-mono font-bold tracking-wide">
                {isCompliant ? 'COMPLIANT' : 'NON-COMPLIANT'}
              </div>
            </div>
          </div>
        </div>

        {/* Declarations Body */}
        <div className="p-6 sm:p-8 space-y-6">
          <h2 className="text-sm font-bold text-[#1C2B3A] uppercase tracking-wider flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[#1C2B3A]" />
            Verified Mandatory Statutory Declarations
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* MRP */}
            <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-4">
              <div className="flex items-center gap-2 text-[#5A6E82] text-xs mb-1 font-bold">
                <DollarSign className="w-3.5 h-3.5 text-[#1C2B3A]" />
                <span>Maximum Retail Price (MRP)</span>
              </div>
              <p className="text-base font-bold text-[#1C2B3A]">
                {dec.mrp || 'Declared on Package'}
              </p>
              <p className="text-[11px] text-[#5A6E82] mt-1">Inclusive of all taxes under Rule 6(1)(e)</p>
            </div>

            {/* Net Quantity */}
            <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-4">
              <div className="flex items-center gap-2 text-[#5A6E82] text-xs mb-1 font-bold">
                <Package className="w-3.5 h-3.5 text-[#1C2B3A]" />
                <span>Net Quantity</span>
              </div>
              <p className="text-base font-bold text-[#1C2B3A]">
                {dec.net_quantity || 'Declared on Package'}
              </p>
              <p className="text-[11px] text-[#5A6E82] mt-1">Standard unit of weight/measure under Rule 12</p>
            </div>

            {/* Dates */}
            <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-4">
              <div className="flex items-center gap-2 text-[#5A6E82] text-xs mb-1 font-bold">
                <Calendar className="w-3.5 h-3.5 text-[#1C2B3A]" />
                <span>Date of Manufacture / Expiry</span>
              </div>
              <div className="space-y-0.5 text-xs text-[#1C2B3A]">
                <p><span className="text-[#5A6E82] font-medium">Mfg:</span> <span className="font-mono font-bold text-[#1C2B3A]">{dec.manufacturing_date || 'Declared'}</span></p>
                <p><span className="text-[#5A6E82] font-medium">Expiry / Best Before:</span> <span className="font-mono font-bold text-[#1C2B3A]">{dec.expiry_date || 'Declared'}</span></p>
              </div>
            </div>

            {/* Country of Origin */}
            <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-4">
              <div className="flex items-center gap-2 text-[#5A6E82] text-xs mb-1 font-bold">
                <Globe className="w-3.5 h-3.5 text-[#1C2B3A]" />
                <span>Country of Origin</span>
              </div>
              <p className="text-base font-bold text-[#1C2B3A]">
                {dec.country_of_origin || 'India'}
              </p>
              <p className="text-[11px] text-[#5A6E82] mt-1">Mandatory origin declaration under Rule 6(10)</p>
            </div>

            {/* Manufacturer Details */}
            <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-4 md:col-span-2">
              <div className="flex items-center gap-2 text-[#5A6E82] text-xs mb-1 font-bold">
                <Building2 className="w-3.5 h-3.5 text-[#5A6E82]" />
                <span>Manufacturer / Packer / Importer Name & Address</span>
              </div>
              <p className="text-sm text-[#1C2B3A] font-medium">
                {dec.manufacturer || 'Declared on package label'}
              </p>
            </div>

            {/* Consumer Care */}
            <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-4 md:col-span-2">
              <div className="flex items-center gap-2 text-[#5A6E82] text-xs mb-1 font-bold">
                <PhoneCall className="w-3.5 h-3.5 text-[#1C2B3A]" />
                <span>Consumer Care & Grievance Redressal</span>
              </div>
              <p className="text-sm text-[#1C2B3A] font-medium">
                {dec.consumer_care || 'Declared on package label'}
              </p>
            </div>
          </div>

          {/* Expiry Intelligence Overview if provided */}
          {profile.expiry_intelligence && (
            <div className="bg-[#F7F5F0] border border-[#E2DDD5] p-5 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Leaf className="w-4 h-4 text-[#2F6F4E]" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[#1C2B3A]">
                    Expiry & Consumption Guidance
                  </h3>
                </div>
                <span className={`px-2.5 py-0.5 text-xs font-mono font-bold border ${
                  profile.expiry_intelligence.status === 'SAFE'
                    ? 'bg-[#EAF4EE] text-[#2F6F4E] border-[#9BC6AE]'
                    : 'bg-[#F9EBE9] text-[#A8342A] border-[#E09891]'
                }`}>
                  {profile.expiry_intelligence.status}
                </span>
              </div>
              <p className="text-xs text-[#1C2B3A] leading-relaxed">
                {profile.expiry_intelligence.recommendation}
              </p>
              {profile.expiry_intelligence.food_waste_prevention_tip && (
                <div className="mt-2.5 pt-2.5 border-t border-[#E2DDD5] text-[11px] text-[#1C2B3A] flex items-start gap-1.5">
                  <Info className="w-3.5 h-3.5 mt-0.5 shrink-0 text-[#B8862B]" />
                  <span>{profile.expiry_intelligence.food_waste_prevention_tip}</span>
                </div>
              )}
            </div>
          )}

          {/* Consumer Grievance Portal Box */}
          <div className="bg-[#FAF3E6] border border-[#DFBF82] p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div>
              <h4 className="text-xs font-bold text-[#1C2B3A]">Consumer Rights & Overcharging Grievances</h4>
              <p className="text-[11px] text-[#5A6E82] mt-0.5">
                If statutory declarations are missing, altered, or if you were charged above declared MRP, file an official complaint.
              </p>
            </div>
            <a
              href="https://consumerhelpline.gov.in"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white border border-[#1C2B3A] text-xs font-bold transition shrink-0 shadow-xs"
            >
              <span>National Consumer Helpline (1915)</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-[#F7F5F0] border-t border-[#D8D2C6] text-center text-xs text-[#5A6E82] font-mono">
          Official Digital Metrology Profile • PCR 2011 Verified • Department of Consumer Affairs, Govt. of India
        </div>
      </div>
    </div>
  );
};
