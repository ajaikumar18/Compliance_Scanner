import { useState, useEffect } from 'react';
import {
  Download,
  AlertTriangle,
  CheckCircle,
  HelpCircle,
  FileText,
  ArrowLeft,
  ShieldAlert,
  Check,
  X,
  QrCode,
  Bot,
  Sparkles,
  Layers,
  Image as ImageIcon
} from 'lucide-react';
import { BoundingBoxCanvas } from '../components/BoundingBoxCanvas';
import { QRVerificationModal } from '../components/QRVerificationModal';
import { AIVoiceAssistantModal } from '../components/AIVoiceAssistantModal';
import { AudioSpeaker } from '../components/AudioSpeaker';
import { ExpiryIntelligenceCard } from '../components/ExpiryIntelligenceCard';
import { PackageDamageCard } from '../components/PackageDamageCard';
import { ConsumptionPredictorCard } from '../components/ConsumptionPredictorCard';
import { NutritionDashboardCard } from '../components/NutritionDashboardCard';
import { AudienceSuitabilityCard } from '../components/AudienceSuitabilityCard';
import { getReportDownloadUrl } from '../services/api';
import { useLanguage } from '../i18n/i18nContext';
import { metrologyAdvisorEngine } from '../services/metrologyAdvisorEngine';
import type { ScanResult, PackageDamageAnalysis } from '../types';

interface ScanResultPageProps {
  scan: ScanResult;
  onBackToHistory: () => void;
}



export const ScanResultPage = ({ scan, onBackToHistory }: ScanResultPageProps) => {
  const { language } = useLanguage();
  const [currentScan, setCurrentScan] = useState<ScanResult>(scan);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [showQRModal, setShowQRModal] = useState(false);
  const [showChatModal, setShowChatModal] = useState(false);
  const [selectedGalleryIdx, setSelectedGalleryIdx] = useState<number>(0);

  useEffect(() => {
    setCurrentScan(scan);
  }, [scan]);

  // The 6 Statutory Declarations under Legal Metrology (Packaged Commodities) Rules 2011 (+ Country of Origin)
  const statutoryDeclarations = [
    { key: 'net_quantity', label: '1. Net Quantity', rule: 'Rule 12 & Rule 6(1)(d)', minHeightDefault: '4.00' },
    { key: 'mrp', label: '2. Maximum Retail Price (MRP)', rule: 'Rule 6(1)(e)', minHeightDefault: '2.50' },
    { key: 'manufacture_date', label: '3. Date of Manufacture / PKD', rule: 'Rule 6(1)(f)', minHeightDefault: '1.80' },
    { key: 'expiry_date', label: '4. Date of Expiry / Best Before', rule: 'Rule 6(1)(f) & FSSAI', minHeightDefault: '1.80' },
    { key: 'manufacturer_name_address', label: '5. Manufacturer / Packer Address', rule: 'Rule 6(1)(a)', minHeightDefault: '1.50' },
    { key: 'consumer_care_details', label: '6. Consumer Care Contact Details', rule: 'Rule 6(1)(k)', minHeightDefault: '1.50' },
    { key: 'country_of_origin', label: '7. Country of Origin (Imported / Dual)', rule: 'Rule 6(10) & Rule 6(1)(b)', minHeightDefault: '1.50' },
  ];

  const displayedFields: Record<string, any> = { ...(currentScan.fields || {}) };
  statutoryDeclarations.forEach(({ key }) => {
    if (!displayedFields[key]) {
      const viol = (currentScan.violations || []).find((v) => v.field_name === key);
      displayedFields[key] = {
        field_name: key,
        extracted_value: null,
        extraction_method: viol ? 'not_found' : 'not_found',
        confidence: 0,
        bbox: null,
      };
    }
  });

  const getVerdictNotice = (status: string) => {
    switch (status) {
      case 'compliant':
        return {
          title: 'OFFICIAL DETERMINATION: FULLY COMPLIANT',
          subtitle: 'All 6 statutory packaging declarations conform with Legal Metrology (Packaged Commodities) Rules 2011.',
          border: 'border-[#2F6F4E]',
          bg: 'bg-[#EAF4EE]',
          text: 'text-[#2F6F4E]',
          stampClass: 'stamp-seal-rect text-[#2F6F4E]',
          stampText: 'VERIFIED COMPLIANT',
          icon: <CheckCircle className="w-6 h-6 text-[#2F6F4E] shrink-0" />,
        };
      case 'non_compliant':
        return {
          title: 'OFFICIAL DETERMINATION: NON-COMPLIANT (VIOLATIONS DETECTED)',
          subtitle: 'Statutory deficiencies detected under PCR 2011. Penal action or re-inspection notice recommended.',
          border: 'border-[#A8342A]',
          bg: 'bg-[#F9EBE9]',
          text: 'text-[#A8342A]',
          stampClass: 'stamp-seal-rect text-[#A8342A]',
          stampText: 'FLAGGED / NON-COMPLIANT',
          icon: <AlertTriangle className="w-6 h-6 text-[#A8342A] shrink-0" />,
        };
      default:
        return {
          title: 'OFFICIAL DETERMINATION: PROVISIONAL / PENDING REVIEW',
          subtitle: 'Discrepant or low-confidence optical readings detected. Manual inspector corroboration required.',
          border: 'border-[#B8862B]',
          bg: 'bg-[#FAF3E6]',
          text: 'text-[#B8862B]',
          stampClass: 'stamp-seal-rect text-[#B8862B]',
          stampText: 'PENDING REVIEW',
          icon: <HelpCircle className="w-6 h-6 text-[#B8862B] shrink-0" />,
        };
    }
  };

  const verdictNotice = getVerdictNotice(currentScan.compliance_status);

  // Active specimen image (from gallery if multi-panel, or main scanned_image_url)
  const activeImageUrl: string =
    (currentScan.gallery_images && currentScan.gallery_images.length > 0
      ? currentScan.gallery_images[selectedGalleryIdx]?.url
      : undefined) ||
    currentScan.scanned_image_url ||
    'https://images.unsplash.com/photo-1550583724-b2692b85b150?auto=format&fit=crop&w=600&q=80';

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 space-y-6">
      {/* Top Header & Docket Overview */}
      <div className="bg-white border border-[#D8D2C6] p-6 rounded-none">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <button
              onClick={onBackToHistory}
              className="p-2.5 rounded-none bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] border border-[#D8D2C6] transition-colors"
              title="Return to Inspection Register"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 bg-[#1C2B3A] text-[#F7F5F0] font-bold tracking-wider">
                  DOCKET #{currentScan?.scan_id || '001'}
                </span>
                <h1 className="text-xl md:text-2xl font-serif font-bold text-[#1C2B3A] tracking-tight">
                  {currentScan?.product_name || 'Packaging Inspection Dossier'}
                </h1>
                {currentScan?.gtin && (
                  <span className="text-xs px-2.5 py-0.5 rounded-none bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE] font-mono font-bold">
                    GTIN: {currentScan.gtin}
                  </span>
                )}
                {currentScan?.batch_code && (
                  <span className="text-xs px-2.5 py-0.5 rounded-none bg-[#FAF3E6] text-[#B8862B] border border-[#DFBF82] font-mono font-bold">
                    BATCH: {currentScan.batch_code}
                  </span>
                )}
              </div>
              <p className="text-xs text-[#5A6E82] mt-1.5 flex flex-wrap items-center gap-2">
                <span>Category: <strong className="text-[#1C2B3A]">{currentScan?.product_category || 'Packaged Commodities'}</strong></span>
                <span>•</span>
                <span>Mode: <strong className="text-[#1C2B3A]">{(currentScan?.scan_type || 'optical').toUpperCase()}</strong></span>
                <span>•</span>
                <span className="font-mono">
                  Recorded: {currentScan.created_at ? new Date(currentScan.created_at).toLocaleString() : 'Recent Audit'}
                </span>
                {currentScan?.barcodes && currentScan.barcodes.length > 0 && (
                  <>
                    <span>•</span>
                    <span className="text-[#1C2B3A] font-mono font-semibold">
                      {currentScan.barcodes.length} Barcode(s) Decoded ({currentScan.barcodes.map((b) => b.format).join(', ')})
                    </span>
                  </>
                )}
              </p>
            </div>
          </div>

          {/* Action Hub: QR Badge, AI Voice Assistant, Audio Readout & Download Reports */}
          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            {/* Digital QR Badge Button */}
            <button
              onClick={() => setShowQRModal(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-none bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] text-xs font-semibold tracking-wide border border-[#D8D2C6] transition-all"
              title="View Digital QR Code & Verification Profile"
            >
              <QrCode className="w-4 h-4 text-[#1C2B3A]" />
              Digital QR Badge
            </button>

            {/* AI Voice Metrology Assistant */}
            <button
              onClick={() => setShowChatModal(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-none bg-[#1C2B3A] hover:bg-[#2A3F55] text-white text-xs font-semibold tracking-wide border border-[#1C2B3A] transition-all"
              title="Launch Multilingual AI Metrology Voice Assistant"
            >
              <Bot className="w-4 h-4 text-emerald-300" />
              AI Assistant
            </button>

            {/* Multilingual Voice Speaker */}
            <AudioSpeaker
              text={metrologyAdvisorEngine.generateSpokenReport(currentScan, language)}
              lang={language}
              label="Audio Summary"
              className="px-3 py-2 bg-[#F7F5F0] border border-[#D8D2C6] text-[#1C2B3A] text-xs font-semibold hover:bg-[#EBE7DF]"
            />

            {/* Official Report Download Buttons */}
            <a
              href={getReportDownloadUrl(currentScan.scan_id, 'pdf')}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 rounded-none bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] text-xs font-semibold tracking-wide border border-[#D8D2C6] transition-all"
            >
              <Download className="w-3.5 h-3.5 text-[#5A6E82]" />
              PDF
            </a>

            <a
              href={getReportDownloadUrl(currentScan.scan_id, 'docx')}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 rounded-none bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] text-xs font-semibold tracking-wide border border-[#D8D2C6] transition-all"
            >
              <FileText className="w-3.5 h-3.5 text-[#5A6E82]" />
              DOCX
            </a>
          </div>
        </div>
      </div>

      {/* Official Determination Banner with Stamp */}
      <div className={`p-5 rounded-none border-2 ${verdictNotice.border} ${verdictNotice.bg} flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4`}>
        <div className="flex items-center gap-4">
          {verdictNotice.icon}
          <div>
            <h3 className={`font-serif font-bold text-base tracking-wide ${verdictNotice.text}`}>
              {verdictNotice.title}
            </h3>
            <p className="text-xs text-[#1C2B3A] opacity-90 mt-0.5">
              {verdictNotice.subtitle}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          <div className="text-xs font-mono font-bold px-3 py-1.5 bg-white border border-[#D8D2C6] text-[#1C2B3A]">
            Violations: <span className={currentScan.violations_count > 0 ? 'text-[#A8342A]' : 'text-[#2F6F4E]'}>{currentScan.violations_count}</span>
          </div>
          <div className={`${verdictNotice.stampClass} text-xs font-mono font-bold tracking-widest px-3 py-1.5`}>
            {verdictNotice.stampText}
          </div>
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* VISUAL HERO: Bounding-Box Product Image with Ruler Tick Marks */}
      {/* ───────────────────────────────────────────────────────────── */}
      <div className="bg-white border border-[#D8D2C6] p-6 rounded-none space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2DDD5] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 bg-[#1C2B3A] text-[#F7F5F0] text-[10px] font-mono font-bold tracking-widest uppercase">
                EXHIBIT A-1
              </span>
              <h2 className="text-base font-serif font-bold text-[#1C2B3A]">
                Forensic Specimen Bounding-Box Map & Measurement Board
              </h2>
            </div>
            <p className="text-xs text-[#5A6E82] mt-1">
              Photographic specimen registered with calibrated horizontal (top) and vertical (left) millimeter rulers.
            </p>
          </div>

          {/* Scale Calibration Specimen Tier Badge */}
          {currentScan.scale_calibration && (
            <div className="flex items-center gap-2 text-xs bg-[#F7F5F0] border border-[#D8D2C6] px-3 py-1.5 font-mono">
              <span className="text-[#5A6E82]">Scale Ratio:</span>
              <strong className="text-[#1C2B3A]">{currentScan.scale_calibration.pixels_per_mm.toFixed(2)} px/mm</strong>
              <span className="text-[#5A6E82]">•</span>
              <span
                className={`font-bold ${
                  currentScan.scale_calibration.calibration_tier === 'ar_verified'
                    ? 'text-purple-700'
                    : currentScan.scale_calibration.calibration_tier === 'reference_object'
                    ? 'text-[#2F6F4E]'
                    : currentScan.scale_calibration.calibration_tier === 'package_dimension'
                    ? 'text-[#B8862B]'
                    : 'text-[#5A6E82]'
                }`}
              >
                {currentScan.scale_calibration.calibration_tier?.toUpperCase() || 'CALIBRATED'}
              </span>
            </div>
          )}
        </div>

        {/* Multi-Panel Image Gallery Selector if present */}
        {currentScan.gallery_images && currentScan.gallery_images.length > 1 && (
          <div className="flex items-center gap-2 p-2 bg-[#F7F5F0] border border-[#D8D2C6] overflow-x-auto">
            <span className="text-[11px] font-mono text-[#5A6E82] uppercase px-2 font-bold flex items-center gap-1">
              <Layers className="w-3.5 h-3.5" /> Panels:
            </span>
            {currentScan.gallery_images.map((imgItem, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedGalleryIdx(idx)}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-mono border transition-all ${
                  selectedGalleryIdx === idx
                    ? 'bg-[#1C2B3A] text-white border-[#1C2B3A] font-bold'
                    : 'bg-white text-[#1C2B3A] border-[#D8D2C6] hover:bg-[#EBE7DF]'
                }`}
              >
                <ImageIcon className="w-3 h-3" />
                {imgItem.label || `Panel ${idx + 1}`}
              </button>
            ))}
          </div>
        )}

        {/* Hero Specimen Board */}
        <div className="w-full flex justify-center bg-[#F7F5F0] border border-[#D8D2C6] p-3 md:p-6 overflow-hidden">
          <div className="w-full max-w-4xl">
            <BoundingBoxCanvas
              imageUrl={activeImageUrl}
              fields={currentScan.fields || {}}
              selectedField={selectedField}
              onSelectField={setSelectedField}
            />
          </div>
        </div>

        {/* Calibration Legend & Tolerances */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-2 text-xs border-t border-[#E2DDD5]">
          <div className="flex items-center gap-4 flex-wrap text-[11px] font-mono">
            <span className="text-[#5A6E82] uppercase tracking-wider font-semibold">Inspection Key:</span>
            <span className="flex items-center gap-1.5 text-[#2F6F4E] font-medium">
              <span className="w-2.5 h-2.5 bg-[#2F6F4E]" /> Compliant Declaration
            </span>
            <span className="flex items-center gap-1.5 text-[#A8342A] font-medium">
              <span className="w-2.5 h-2.5 bg-[#A8342A]" /> Statutory Violation
            </span>
            <span className="flex items-center gap-1.5 text-[#B8862B] font-medium">
              <span className="w-2.5 h-2.5 bg-[#B8862B]" /> AI / Provisional OCR
            </span>
            <span className="flex items-center gap-1.5 text-[#1C2B3A] font-medium">
              <span className="w-2.5 h-2.5 bg-[#1C2B3A]" /> E-Commerce HTML Spec
            </span>
          </div>

          {currentScan.scale_calibration?.tolerance_note && (
            <div className="text-[11px] text-[#5A6E82] font-mono italic">
              {currentScan.scale_calibration.tolerance_note}
            </div>
          )}
        </div>
      </div>

      {/* Front-of-pack Warning Note if applicable */}
      {currentScan.violations_count >= 5 && (
        <div className="p-4 bg-[#FAF3E6] border-l-4 border-[#B8862B] border-y border-r border-[#DFBF82] text-xs flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-[#B8862B] shrink-0 mt-0.5" />
          <div>
            <p className="font-bold text-[#B8862B] uppercase tracking-wide">Notice: Front-Of-Pack Image Scanned</p>
            <p className="text-[#1C2B3A] mt-1 leading-relaxed">
              This specimen appears to be the promotional front face. Under Indian Legal Metrology Rules 2011, mandatory declarations (MRP, Mfg/Expiry Date, Packer Address, Customer Care) are customarily printed on the <strong>back or principal display panel</strong>. Ensure back-of-pack is submitted for complete audit certification.
            </p>
          </div>
        </div>
      )}

      {/* ───────────────────────────────────────────────────────────── */}
      {/* E-COMMERCE VS PACKAGING CROSS-VALIDATION TABLE (Rule 6(10))   */}
      {/* ───────────────────────────────────────────────────────────── */}
      {currentScan.cross_validation && currentScan.cross_validation.length > 0 && (
        <div className="bg-white border border-[#D8D2C6] p-6 rounded-none space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2DDD5] pb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 bg-[#1C2B3A] text-[#F7F5F0] text-[10px] font-mono font-bold tracking-widest uppercase">
                  RULE 6(10) E-COMMERCE AUDIT
                </span>
                <h2 className="text-base font-serif font-bold text-[#1C2B3A]">
                  E-Commerce Listing vs Packaging OCR Cross-Validation
                </h2>
              </div>
              <p className="text-xs text-[#5A6E82] mt-1">
                Validates digital catalog claims directly against statutory declarations extracted from physical packaging images.
              </p>
            </div>

            <span className="text-xs font-mono font-bold text-[#1C2B3A] bg-[#F7F5F0] px-3 py-1.5 border border-[#D8D2C6]">
              {currentScan.cross_validation.length} Attributes Checked
            </span>
          </div>

          <div className="overflow-x-auto border border-[#E2DDD5]">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[#E2DDD5] bg-[#F7F5F0] text-[#1C2B3A] font-mono uppercase tracking-wider text-[11px]">
                  <th className="py-2.5 px-4 font-bold">Attribute</th>
                  <th className="py-2.5 px-4 font-bold">E-Commerce Listing</th>
                  <th className="py-2.5 px-4 font-bold">Packaging OCR</th>
                  <th className="py-2.5 px-4 font-bold">Verdict</th>
                  <th className="py-2.5 px-4 font-bold">Audit Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2DDD5]">
                {currentScan.cross_validation.map((cv, idx) => {
                  let badge = 'bg-[#F7F5F0] text-[#5A6E82] border-[#D8D2C6]';
                  if (cv.status === 'MATCH') badge = 'bg-[#EAF4EE] text-[#2F6F4E] border-[#9BC6AE] font-bold';
                  if (cv.status === 'MISMATCH') badge = 'bg-[#F9EBE9] text-[#A8342A] border-[#E09891] font-bold';
                  if (cv.status === 'WARNING') badge = 'bg-[#FAF3E6] text-[#B8862B] border-[#DFBF82] font-bold';
                  if (cv.status === 'ONLINE_ONLY') badge = 'bg-[#EBF3FB] text-[#2A6EBB] border-[#94BFE6]';
                  if (cv.status === 'PACKAGING_ONLY') badge = 'bg-[#F4EEFB] text-[#7839EE] border-[#C8B0F4]';

                  return (
                    <tr key={idx} className="hover:bg-[#F9FAF8] transition-colors">
                      <td className="py-3 px-4 font-semibold text-[#1C2B3A] font-mono">
                        {cv.display_name || cv.field_name}
                      </td>
                      <td className="py-3 px-4 text-[#1C2B3A] font-mono">
                        {cv.ecommerce_value || <span className="text-[#5A6E82] italic">Not Disclosed</span>}
                      </td>
                      <td className="py-3 px-4 text-[#1C2B3A] font-mono">
                        {cv.packaging_value || <span className="text-[#5A6E82] italic">Not Disclosed</span>}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`inline-block px-2 py-0.5 text-[10px] font-mono border ${badge}`}>
                          {cv.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-[#5A6E82]">
                        {cv.details}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ───────────────────────────────────────────────────────────── */}
      {/* STATUTORY DECLARATIONS CHECKLIST: PASS / FAIL ROWS            */}
      {/* ───────────────────────────────────────────────────────────── */}
      <div className="bg-white border border-[#D8D2C6] p-6 rounded-none space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#E2DDD5] pb-4">
          <div>
            <span className="text-[10px] font-mono uppercase px-2 py-0.5 bg-[#1C2B3A] text-[#F7F5F0] font-bold tracking-wider">
              LEGAL METROLOGY ACT 2009 • PCR 2011
            </span>
            <h2 className="text-base font-serif font-bold text-[#1C2B3A] mt-1">
              Statutory Declarations Audit Checklist
            </h2>
            <p className="text-xs text-[#5A6E82]">
              Evaluated per mandatory declaration rules with optical character recognition & physical mm font height verification.
            </p>
          </div>

          <div className="text-xs font-mono font-bold text-[#1C2B3A] bg-[#F7F5F0] px-3 py-1.5 border border-[#D8D2C6]">
            Pass Rate:{' '}
            {
              statutoryDeclarations.filter((d) => {
                const f = displayedFields[d.key];
                const viol = (currentScan.violations || []).find((v) => v.field_name === d.key);
                return f && f.extracted_value && !viol;
              }).length
            }{' '}
            / {statutoryDeclarations.length} Required
          </div>
        </div>

        {/* Checklist Pass/Fail Ruled Rows */}
        <div className="divide-y divide-[#E2DDD5] border border-[#E2DDD5]">
          {statutoryDeclarations.map((decl) => {
            const fieldInfo = displayedFields[decl.key];
            const violation = (currentScan.violations || []).find((v) => v.field_name === decl.key);
            const isSelected = selectedField === decl.key;
            const hasPassed = fieldInfo && fieldInfo.extracted_value && !violation;

            const calibTier = fieldInfo?.calibration_tier || currentScan.scale_calibration?.calibration_tier || 'dpi_estimated';

            return (
              <div
                key={decl.key}
                onClick={() => setSelectedField(decl.key)}
                className={`p-4 transition-colors cursor-pointer ${
                  isSelected
                    ? 'bg-[#EAEFF5] border-l-4 border-l-[#1C2B3A]'
                    : hasPassed
                    ? 'hover:bg-[#F9FAF8]'
                    : 'bg-[#FDFAF9] hover:bg-[#F9EBE9]'
                }`}
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                  {/* Left: Pass/Fail Docket Indicator & Declaration Identity */}
                  <div className="flex items-start gap-3 min-w-[280px]">
                    <div className="mt-0.5">
                      {hasPassed ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-mono font-bold bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE]">
                          <Check className="w-3.5 h-3.5 stroke-[3]" />
                          PASS
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-mono font-bold bg-[#F9EBE9] text-[#A8342A] border border-[#E09891]">
                          <X className="w-3.5 h-3.5 stroke-[3]" />
                          FAIL
                        </span>
                      )}
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-serif font-bold text-[#1C2B3A]">
                          {decl.label}
                        </span>
                      </div>
                      <span className="text-[11px] font-mono text-[#5A6E82]">
                        Mandated by {decl.rule}
                      </span>
                    </div>
                  </div>

                  {/* Middle: Extracted Declaration Content */}
                  <div className="flex-1 min-w-[220px]">
                    <div className="text-xs text-[#1C2B3A]">
                      {fieldInfo?.extracted_value ? (
                        <span className="font-medium bg-[#F7F5F0] px-2.5 py-1 border border-[#D8D2C6] inline-block max-w-full truncate">
                          "{fieldInfo.extracted_value}"
                        </span>
                      ) : (
                        <span className="text-[#A8342A] font-mono text-[11px] font-bold">
                          [NOT DETECTED / MISSING FROM SPECIMEN]
                        </span>
                      )}
                    </div>
                    {violation && (
                      <div className="mt-1 text-[11px] text-[#A8342A] font-sans font-medium flex items-center gap-1">
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                        <span>{violation.details}</span>
                      </div>
                    )}
                  </div>

                  {/* Right: Millimeter Measurements & Calibration Tier */}
                  <div className="flex flex-col sm:items-end gap-1 shrink-0 font-mono text-xs">
                    {fieldInfo?.measured_mm ? (
                      <div className="flex items-center gap-2">
                        <span className="text-[#5A6E82] text-[11px]">Height:</span>
                        <strong
                          className={`font-bold ${
                            fieldInfo.font_compliant === false ? 'text-[#A8342A]' : 'text-[#2F6F4E]'
                          }`}
                        >
                          {fieldInfo.measured_mm.toFixed(2)}mm
                        </strong>
                        <span className="text-[#5A6E82] text-[11px]">
                          (req min {fieldInfo.required_mm || decl.minHeightDefault}mm)
                        </span>
                      </div>
                    ) : (
                      <div className="text-[11px] text-[#5A6E82]">
                        Font: <span className="italic">Unmeasured</span>
                      </div>
                    )}

                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-[#5A6E82] uppercase">Sensor Tier:</span>
                      <span
                        className={`text-[10px] px-2 py-0.5 font-bold ${
                          calibTier === 'ar_verified'
                            ? 'bg-purple-100 text-purple-800 border border-purple-300'
                            : calibTier === 'reference_object'
                            ? 'bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE]'
                            : calibTier === 'package_dimension'
                            ? 'bg-[#FAF3E6] text-[#B8862B] border border-[#DFBF82]'
                            : 'bg-[#F7F5F0] text-[#5A6E82] border border-[#D8D2C6]'
                        }`}
                      >
                        {calibTier}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* AI PRODUCT INTELLIGENCE & CONSUMER PROTECTION DOSSIER GRID    */}
      {/* ───────────────────────────────────────────────────────────── */}
      <div className="bg-white border border-[#D8D2C6] p-6 rounded-none space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2DDD5] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-[#B8862B]" />
              <h2 className="text-base font-serif font-bold text-[#1C2B3A]">
                AI Product Intelligence & Consumer Safety Dossier
              </h2>
            </div>
            <p className="text-xs text-[#5A6E82] mt-1">
              Autonomous multi-modal forensic evaluation covering shelf-life, package surface integrity, dietary profiling, and consumer safety.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowQRModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] text-xs font-semibold border border-[#D8D2C6] transition"
            >
              <QrCode className="w-3.5 h-3.5 text-[#1C2B3A]" />
              QR Profile
            </button>
            <button
              onClick={() => setShowChatModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white text-xs font-semibold border border-[#1C2B3A] transition"
            >
              <Bot className="w-3.5 h-3.5 text-emerald-300" />
              Voice Assistant
            </button>
          </div>
        </div>

        {/* 2-Column Grid for Intelligence Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Card 1: Expiry & Shelf-Life Intelligence */}
          <ExpiryIntelligenceCard data={currentScan.expiry_intelligence} lang={language} />

          {/* Card 2: Package Damage & Surface Integrity */}
          <PackageDamageCard
            data={currentScan.damage_analysis}
            lang={language}
            onAnalysisUpdated={(updated: PackageDamageAnalysis) => {
              setCurrentScan((prev) => ({ ...prev, damage_analysis: updated }));
            }}
          />

          {/* Card 3: Household Consumption Predictor */}
          <ConsumptionPredictorCard
            data={currentScan.consumption_prediction}
            lang={language}
            category={currentScan.product_category || 'Packaged Foods'}
            netQuantityRaw={currentScan.fields?.net_quantity?.extracted_value || undefined}
            expiryDateStr={
              currentScan.fields?.expiry_date?.extracted_value ||
              currentScan.fields?.manufacture_date?.extracted_value ||
              currentScan.expiry_intelligence?.expiry_date
            }
          />

          {/* Card 4: Nutritional Dashboard & Ingredients */}
          <NutritionDashboardCard data={currentScan.nutrition_info} lang={language} />

          {/* Card 5: Demographic Audience Suitability (Full Width) */}
          <div className="lg:col-span-2">
            <AudienceSuitabilityCard data={currentScan.audience_suitability} lang={language} />
          </div>
        </div>
      </div>

      {/* Violations Summary Docket (if any) */}
      {currentScan.violations && currentScan.violations.length > 0 && (
        <div className="bg-white border-2 border-[#A8342A] p-6 rounded-none space-y-4">
          <div className="flex items-center justify-between border-b border-[#F9EBE9] pb-3">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-[#A8342A]" />
              <h3 className="font-serif font-bold text-base text-[#A8342A]">
                Formal Statutory Violations Log ({currentScan.violations.length} Infraction
                {currentScan.violations.length > 1 ? 's' : ''})
              </h3>
            </div>
            <span className="text-[10px] font-mono uppercase bg-[#F9EBE9] text-[#A8342A] font-bold px-2.5 py-1 border border-[#E09891]">
              ACTION REQUIRED
            </span>
          </div>

          <div className="space-y-3">
            {currentScan.violations.map((v, idx) => (
              <div key={idx} className="p-4 bg-[#FDFAF9] border border-[#E2DDD5] space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-[#1C2B3A] uppercase">
                    Clause: {v.field_name.replace(/_/g, ' ')}
                  </span>
                  <span
                    className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 ${
                      v.severity === 'high'
                        ? 'bg-[#F9EBE9] text-[#A8342A] border border-[#E09891]'
                        : v.severity === 'medium'
                        ? 'bg-[#FAF3E6] text-[#B8862B] border border-[#DFBF82]'
                        : 'bg-[#F7F5F0] text-[#5A6E82] border border-[#D8D2C6]'
                    }`}
                  >
                    {v.severity} Priority
                  </span>
                </div>
                <p className="text-xs text-[#1C2B3A]">{v.details}</p>
                {v.rule_reference && (
                  <p className="text-[11px] text-[#5A6E82] font-mono italic">
                    Legal Reference: {v.rule_reference}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* QR Code Digital Profile Verification Modal */}
      <QRVerificationModal
        isOpen={showQRModal}
        onClose={() => setShowQRModal(false)}
        qrData={currentScan.qr_code}
        scan={currentScan}
      />

      {/* Multilingual AI Voice Metrology Assistant Modal */}
      <AIVoiceAssistantModal
        isOpen={showChatModal}
        onClose={() => setShowChatModal(false)}
        scan={currentScan}
      />
    </div>
  );
};
