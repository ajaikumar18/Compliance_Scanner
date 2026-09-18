import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  Clock,
  Search,
  Camera,
  CameraOff,
  Barcode,
  Layers,
  CheckCircle2,
  AlertCircle,
  ChevronRight,
  Sparkles,
  Calendar,
  Box,
  LogIn,
  Award,
} from 'lucide-react';

import { StatCard } from '../components/StatCard';
import { fetchLedgerByGtin } from '../services/api';
import type { ComplianceLedgerData } from '../types';

interface TrustLookupPageProps {
  onBackToLogin: () => void;
}

export const TrustLookupPage: React.FC<TrustLookupPageProps> = ({ onBackToLogin }) => {
  const [gtinInput, setGtinInput] = useState('');
  const [searchedGtin, setSearchedGtin] = useState<string | null>(null);
  const [ledgerData, setLedgerData] = useState<ComplianceLedgerData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  // Camera Barcode Scanning State
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Quick Demo GTINs for convenience
  const DEMO_GTINS = [
    { label: 'NutriChoice Biscuits', gtin: '8901030383456' },
    { label: 'Herbal Shampoo', gtin: '8901030383999' },
    { label: 'Imported Snack', gtin: '012345678905' },
  ];

  // ─────────────────────────────────────────────────────────────────────────
  // 1. Fetch Ledger Data for GTIN
  // ─────────────────────────────────────────────────────────────────────────
  const handleLookup = useCallback(async (gtinToQuery?: string) => {
    const targetGtin = (gtinToQuery || gtinInput).trim();
    if (!targetGtin) {
      setError('Please enter or scan a valid product barcode (GTIN).');
      return;
    }

    setLoading(true);
    setError(null);
    setNotFound(false);
    setSearchedGtin(targetGtin);

    try {
      const data = await fetchLedgerByGtin(targetGtin);
      setLedgerData(data);
    } catch (err: any) {
      if (err.message && (err.message.includes('404') || err.message.includes('No compliance ledger'))) {
        setNotFound(true);
        setLedgerData(null);
      } else {
        setError(err.message || 'Unable to retrieve trust record. Please check the GTIN and try again.');
        setLedgerData(null);
      }
    } finally {
      setLoading(false);
    }
  }, [gtinInput]);

  // ─────────────────────────────────────────────────────────────────────────
  // 2. Camera Barcode Detection Loop
  // ─────────────────────────────────────────────────────────────────────────
  const stopCamera = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraActive(false);
  }, []);

  const startCamera = async () => {
    setCameraError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setIsCameraActive(true);

      // Check for BarcodeDetector support
      if ('BarcodeDetector' in window) {
        const formats = ['ean_13', 'upc_a', 'ean_8', 'qr_code', 'code_128', 'data_matrix'];
        const detector = new (window as any).BarcodeDetector({ formats });

        const scanFrame = async () => {
          if (!videoRef.current || videoRef.current.readyState < 2) {
            animationFrameRef.current = requestAnimationFrame(scanFrame);
            return;
          }

          try {
            const barcodes = await detector.detect(videoRef.current);
            if (barcodes && barcodes.length > 0) {
              const detectedVal = barcodes[0].rawValue?.trim();
              if (detectedVal && detectedVal.length >= 8) {
                if ('vibrate' in navigator) {
                  navigator.vibrate(100);
                }
                setGtinInput(detectedVal);
                stopCamera();
                handleLookup(detectedVal);
                return;
              }
            }
          } catch (detErr) {
            // Ignore frame decode misses
          }
          animationFrameRef.current = requestAnimationFrame(scanFrame);
        };

        animationFrameRef.current = requestAnimationFrame(scanFrame);
      } else {
        setCameraError(
          'Live camera barcode scanning is not supported by your browser. You can manually enter the GTIN below.'
        );
      }
    } catch (err: any) {
      setCameraError(err.message || 'Camera access was denied or is unavailable.');
      stopCamera();
    }
  };

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  // ─────────────────────────────────────────────────────────────────────────
  // 3. Trust Badge Metadata Resolver - Stamp / Seal Shapes (NOT pill badges)
  // ─────────────────────────────────────────────────────────────────────────
  const getTrustBadge = (verdict?: string) => {
    switch (verdict?.toLowerCase()) {
      case 'compliant':
        return {
          title: 'VERIFIED COMPLIANT',
          status: 'compliant',
          stampStyle: 'stamp-seal-circle text-[#2F6F4E] border-[#2F6F4E] bg-[#EAF4EE]',
          cardBorder: 'border-[#2F6F4E]',
          headerText: 'text-[#2F6F4E]',
          sealText: 'LEGAL METROLOGY • ACT 2009',
          subLabel: 'OFFICIAL AUDIT SEAL',
          icon: <ShieldCheck className="w-8 h-8 text-[#2F6F4E]" />,
          description:
            'This product has passed multi-audit regulatory checks with valid Legal Metrology packaging declarations (MRP, Net Qty, Dates, Address).',
        };
      case 'non_compliant':
        return {
          title: 'FLAGGED / DEFICIENT',
          status: 'flagged',
          stampStyle: 'stamp-seal-rect text-[#A8342A] border-[#A8342A] bg-[#F9EBE9]',
          cardBorder: 'border-[#A8342A]',
          headerText: 'text-[#A8342A]',
          sealText: 'STATUTORY DEFICIENCY',
          subLabel: 'REJECTED SPECIMEN',
          icon: <AlertTriangle className="w-8 h-8 text-[#A8342A]" />,
          description:
            'One or more regulatory packaging non-compliances (missing mandatory declarations or undersized font) have been confirmed by laboratory measurement.',
        };
      case 'disputed':
      default:
        return {
          title: 'PENDING REVIEW',
          status: 'pending',
          stampStyle: 'stamp-seal-rect text-[#B8862B] border-[#B8862B] bg-[#FAF3E6] border-dashed',
          cardBorder: 'border-[#B8862B]',
          headerText: 'text-[#B8862B]',
          sealText: 'EVIDENCE DISCREPANCY',
          subLabel: 'PROVISIONAL DOCKET',
          icon: <Clock className="w-8 h-8 text-[#B8862B]" />,
          description:
            'Conflicting scan evidence or pending inspector verification. Multiple audits show differing compliance observations.',
        };
    }
  };

  const badgeInfo = getTrustBadge(ledgerData?.current_verdict);

  return (
    <div className="min-h-screen bg-[#F7F5F0] text-[#1C2B3A] flex flex-col font-sans">
      {/* ── Top Header & Public Navigation ─────────────────────────────────── */}
      <header className="sticky top-0 z-50 bg-[#1C2B3A] text-white border-b border-[#121B24] px-4 lg:px-8 py-3.5 shadow-none">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/10 border border-white/20">
              <Award className="w-6 h-6 text-[#DFBF82]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-serif font-bold text-white tracking-tight">
                  Public Compliance & Trust Ledger
                </span>
                <span className="text-[10px] uppercase font-bold px-2 py-0.5 bg-[#2F6F4E] text-white font-mono">
                  PUBLIC PORTAL
                </span>
              </div>
              <p className="text-[11px] text-[#A2B4C7] hidden sm:block">
                Statutory Packaging Verification per Legal Metrology (Packaged Commodities) Rules 2011
              </p>
            </div>
          </div>

          <button
            onClick={onBackToLogin}
            className="flex items-center gap-2 px-3.5 py-2 bg-white text-[#1C2B3A] text-xs font-semibold border border-white hover:bg-[#F7F5F0] transition-colors"
          >
            <LogIn className="w-4 h-4 text-[#1C2B3A]" />
            <span>Inspector Sign In</span>
          </button>
        </div>
      </header>

      {/* ── Main Container ─────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8 space-y-8">
        {/* Hero Search & Scanner Section */}
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-white border border-[#D8D2C6] text-[#1C2B3A] text-xs font-mono">
            <Sparkles className="w-3.5 h-3.5 text-[#B8862B]" />
            Official GTIN & Barcode Ledger Verification
          </div>
          <h1 className="text-3xl sm:text-4xl font-serif font-bold text-[#1C2B3A] tracking-tight">
            Verify Product Packaging Compliance
          </h1>
          <p className="text-sm text-[#5A6E82] leading-relaxed">
            Search any retail barcode (EAN-13, UPC-A, QR) or 13-digit GTIN to inspect its multi-audit
            statutory declaration compliance history, AR 3D millimeter measurement verification, and production batch verdicts.
          </p>
        </div>

        {/* Barcode Search Bar & Camera Button */}
        <div className="max-w-2xl mx-auto space-y-4">
          <div className="bg-white p-2 border border-[#D8D2C6] flex flex-col sm:flex-row items-center gap-2">
            <div className="relative flex-1 w-full">
              <Barcode className="w-5 h-5 text-[#5A6E82] absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={gtinInput}
                onChange={e => setGtinInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleLookup()}
                placeholder="Enter 13-digit Barcode / GTIN (e.g. 8901030383456)"
                className="w-full pl-11 pr-4 py-3 bg-transparent text-[#1C2B3A] placeholder-[#8A9AA8] text-sm focus:outline-none font-mono"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <button
                onClick={() => (isCameraActive ? stopCamera() : startCamera())}
                className={`p-3 border flex items-center justify-center transition-all ${
                  isCameraActive
                    ? 'bg-[#F9EBE9] text-[#A8342A] border-[#A8342A]'
                    : 'bg-[#F7F5F0] text-[#1C2B3A] border-[#D8D2C6] hover:bg-[#EBE7DF]'
                }`}
                title={isCameraActive ? 'Stop Camera' : 'Scan with Device Camera'}
              >
                {isCameraActive ? <CameraOff className="w-5 h-5" /> : <Camera className="w-5 h-5" />}
              </button>

              <button
                onClick={() => handleLookup()}
                disabled={loading || !gtinInput.trim()}
                className="flex-1 sm:flex-none px-6 py-3 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white font-semibold text-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2 border border-[#1C2B3A]"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Querying Ledger...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    <span>Check Trust Record</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Quick Demo GTIN Chips */}
          <div className="flex flex-wrap items-center justify-center gap-2 text-xs">
            <span className="text-[#5A6E82] font-medium">Quick Specimen:</span>
            {DEMO_GTINS.map(item => (
              <button
                key={item.gtin}
                onClick={() => {
                  setGtinInput(item.gtin);
                  handleLookup(item.gtin);
                }}
                className="px-2.5 py-1 bg-white hover:bg-[#EBE7DF] text-[#1C2B3A] border border-[#D8D2C6] font-mono transition-colors"
              >
                {item.label} ({item.gtin.slice(-4)})
              </button>
            ))}
          </div>

          {/* Live Camera Scanner Viewport */}
          {isCameraActive && (
            <div className="bg-white border border-[#1C2B3A] p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-[#E2DDD5] pb-2">
                <span className="text-xs font-mono font-bold text-[#1C2B3A] flex items-center gap-2">
                  <span className="w-2 h-2 bg-[#2F6F4E] animate-pulse" />
                  OPTICAL SENSOR ACTIVE: ALIGN GTIN IN RETICLE
                </span>
                <button
                  onClick={stopCamera}
                  className="text-xs text-[#A8342A] hover:underline font-mono font-bold"
                >
                  [STOP SCANNER]
                </button>
              </div>

              <div className="relative aspect-video sm:aspect-[16/9] bg-black overflow-hidden flex items-center justify-center">
                <video
                  ref={videoRef}
                  playsInline
                  muted
                  className="w-full h-full object-cover"
                />

                {/* Reticle Target Overlay */}
                <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                  <div className="w-64 h-36 border-2 border-dashed border-white/80 relative">
                    <div className="absolute -top-1 -left-1 w-4 h-4 border-t-2 border-l-2 border-white" />
                    <div className="absolute -top-1 -right-1 w-4 h-4 border-t-2 border-r-2 border-white" />
                    <div className="absolute -bottom-1 -left-1 w-4 h-4 border-b-2 border-l-2 border-white" />
                    <div className="absolute -bottom-1 -right-1 w-4 h-4 border-b-2 border-r-2 border-white" />
                    <div className="w-full h-0.5 bg-red-500 absolute top-1/2 -translate-y-1/2 animate-pulse" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {cameraError && (
            <div className="p-3.5 bg-[#FAF3E6] border border-[#DFBF82] text-[#B8862B] text-xs flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{cameraError}</span>
            </div>
          )}

          {error && (
            <div className="p-4 bg-[#F9EBE9] border border-[#E09891] text-[#A8342A] text-sm flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 shrink-0 text-[#A8342A]" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* ── 404 / Not Found State ────────────────────────────────────────── */}
        {notFound && searchedGtin && (
          <div className="max-w-2xl mx-auto bg-white p-8 border border-[#D8D2C6] text-center space-y-4">
            <div className="w-12 h-12 bg-[#F7F5F0] border border-[#D8D2C6] flex items-center justify-center mx-auto text-[#5A6E82]">
              <Barcode className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-serif font-bold text-[#1C2B3A]">No Registered Ledger Entry</h3>
              <p className="text-xs text-[#5A6E82] mt-1 font-mono">GTIN: {searchedGtin}</p>
            </div>
            <p className="text-xs text-[#5A6E82] max-w-md mx-auto leading-relaxed">
              This product barcode has not yet been audited or submitted to the Legal Metrology compliance ledger.
              Authorized inspectors can scan and register the product in the Inspector Portal.
            </p>
            <div className="pt-2">
              <button
                onClick={onBackToLogin}
                className="px-4 py-2 bg-[#1C2B3A] text-white text-xs font-semibold inline-flex items-center gap-1.5 transition-colors"
              >
                <span>Sign In as Inspector to Scan Product</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* ── Trust Ledger Result Showcase ──────────────────────────────────── */}
        {ledgerData && (
          <div className="space-y-6">
            {/* Primary Trust Badge Exhibit with Authentic Stamp / Seal */}
            <div className={`bg-white border-2 ${badgeInfo.cardBorder} p-6 sm:p-8 relative overflow-hidden`}>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
                <div className="flex items-start sm:items-center gap-4">
                  <div className="p-3.5 bg-[#F7F5F0] border border-[#D8D2C6] shrink-0">
                    {badgeInfo.icon}
                  </div>
                  <div>
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="text-xs font-mono font-bold px-2.5 py-0.5 bg-[#1C2B3A] text-white">
                        GTIN: {ledgerData.gtin}
                      </span>
                      {ledgerData.category && (
                        <span className="text-xs text-[#5A6E82] bg-[#F7F5F0] border border-[#D8D2C6] px-2 py-0.5">
                          {ledgerData.category}
                        </span>
                      )}
                    </div>
                    <h2 className="text-2xl sm:text-3xl font-serif font-bold tracking-tight text-[#1C2B3A] mt-1">
                      {ledgerData.product_name || `Product GTIN-${ledgerData.gtin}`}
                    </h2>
                    <p className="text-xs text-[#5A6E82] mt-1.5 max-w-xl leading-relaxed">
                      {badgeInfo.description}
                    </p>
                  </div>
                </div>

                {/* Stamp / Seal Shape Representation (NOT a pill badge!) */}
                <div className="flex flex-col sm:items-end gap-3 shrink-0">
                  <div className={`${badgeInfo.stampStyle} text-center p-3 select-none`}>
                    <div className="text-[9px] font-mono tracking-widest uppercase opacity-80">
                      ★ {badgeInfo.subLabel} ★
                    </div>
                    <div className="text-base font-serif font-bold tracking-wider uppercase mt-0.5">
                      {badgeInfo.title}
                    </div>
                    <div className="text-[8px] font-mono tracking-tight uppercase opacity-90 border-t border-current mt-1 pt-0.5">
                      {badgeInfo.sealText}
                    </div>
                  </div>

                  <div className="text-xs text-[#5A6E82] flex items-center gap-2 font-mono">
                    <span>Rolling Confidence:</span>
                    <strong className="text-[#1C2B3A] text-sm font-bold">
                      {Math.round(ledgerData.rolling_confidence * 100)}%
                    </strong>
                  </div>
                </div>
              </div>
            </div>

            {/* Reusable StatCards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                title="Total Audits"
                value={ledgerData.total_scans}
                subtitle="Independent scans recorded"
                icon={<Layers className="w-6 h-6" />}
                color="indigo"
              />

              <StatCard
                title="Verified Compliant"
                value={ledgerData.compliant_scans}
                subtitle="Passed mandatory declarations"
                icon={<CheckCircle2 className="w-6 h-6" />}
                color="emerald"
                badge={`${Math.round((ledgerData.compliant_scans / Math.max(ledgerData.total_scans, 1)) * 100)}% Clean`}
              />

              <StatCard
                title="Flagged Non-Compliant"
                value={ledgerData.non_compliant_scans}
                subtitle="Missing or undersized labels"
                icon={<AlertTriangle className="w-6 h-6" />}
                color="rose"
              />

              <StatCard
                title="AR 3D Depth Verified"
                value={ledgerData.calibration_breakdown.ar_verified}
                subtitle="High-precision sensor hit-test"
                icon={<Box className="w-6 h-6" />}
                color="cyan"
                badge="2.0x weight"
              />
            </div>

            {/* Sensor Reliability & Batch Breakdown Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Sensor Calibration Tier Breakdown */}
              <div className="lg:col-span-5 bg-white border border-[#D8D2C6] p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-[#E2DDD5] pb-3">
                  <h3 className="text-sm font-serif font-bold text-[#1C2B3A] flex items-center gap-2">
                    <Box className="w-4 h-4 text-[#1C2B3A]" />
                    Measurement Calibration Tiers
                  </h3>
                  <span className="text-[11px] text-[#5A6E82] font-mono">Weight Matrix</span>
                </div>

                <p className="text-xs text-[#5A6E82]">
                  Rolling confidence weights high-precision depth hardware over uncalibrated fallback estimates.
                </p>

                <div className="space-y-2.5 pt-1">
                  <div className="flex items-center justify-between p-3 bg-[#F7F5F0] border border-[#D8D2C6]">
                    <div>
                      <div className="text-xs font-bold text-[#1C2B3A]">On-Device AR Hit-Test</div>
                      <div className="text-[11px] text-purple-700 font-mono">Tier 1 • 2.0x weight • ±0.05mm</div>
                    </div>
                    <span className="text-base font-bold text-[#1C2B3A] font-mono">
                      {ledgerData.calibration_breakdown.ar_verified}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-[#F7F5F0] border border-[#D8D2C6]">
                    <div>
                      <div className="text-xs font-bold text-[#1C2B3A]">Reference Coin / Card Detection</div>
                      <div className="text-[11px] text-[#2F6F4E] font-mono">Tier 2 • 1.4x weight • ±0.20mm</div>
                    </div>
                    <span className="text-base font-bold text-[#1C2B3A] font-mono">
                      {ledgerData.calibration_breakdown.reference_object}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-[#F7F5F0] border border-[#D8D2C6]">
                    <div>
                      <div className="text-xs font-bold text-[#1C2B3A]">Manual Package Width</div>
                      <div className="text-[11px] text-[#B8862B] font-mono">Tier 3 • 1.1x weight • ±0.30mm</div>
                    </div>
                    <span className="text-base font-bold text-[#1C2B3A] font-mono">
                      {ledgerData.calibration_breakdown.package_dimension}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-[#F7F5F0] border border-[#D8D2C6]">
                    <div>
                      <div className="text-xs font-bold text-[#1C2B3A]">Default 300 DPI Fallback</div>
                      <div className="text-[11px] text-[#5A6E82] font-mono">Tier 4 • 0.7x weight • ±0.50mm</div>
                    </div>
                    <span className="text-base font-bold text-[#1C2B3A] font-mono">
                      {ledgerData.calibration_breakdown.dpi_estimated}
                    </span>
                  </div>
                </div>
              </div>

              {/* Batch Code Breakdown */}
              <div className="lg:col-span-7 bg-white border border-[#D8D2C6] p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-[#E2DDD5] pb-3">
                  <h3 className="text-sm font-serif font-bold text-[#1C2B3A] flex items-center gap-2">
                    <Layers className="w-4 h-4 text-[#1C2B3A]" />
                    Batch & Lot Number Audit Breakdown
                  </h3>
                  <span className="text-xs text-[#5A6E82] font-mono">
                    {Object.keys(ledgerData.batch_breakdown || {}).length} Production Run(s)
                  </span>
                </div>

                <p className="text-xs text-[#5A6E82]">
                  Compliance tracked across verified batch declarations extracted from packaging evidence.
                </p>

                <div className="space-y-2.5 pt-1 max-h-[300px] overflow-y-auto pr-1">
                  {Object.entries(ledgerData.batch_breakdown || {}).length > 0 ? (
                    Object.entries(ledgerData.batch_breakdown).map(([batchKey, bInfo]) => (
                      <div
                        key={batchKey}
                        className="p-3 bg-[#F7F5F0] border border-[#D8D2C6] flex items-center justify-between gap-4"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-bold text-[#1C2B3A]">
                              LOT: {batchKey}
                            </span>
                            <span
                              className={`text-[10px] px-2 py-0.5 font-bold uppercase font-mono ${
                                bInfo.current_verdict === 'compliant'
                                  ? 'bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE]'
                                  : bInfo.current_verdict === 'non_compliant'
                                  ? 'bg-[#F9EBE9] text-[#A8342A] border border-[#E09891]'
                                  : 'bg-[#FAF3E6] text-[#B8862B] border border-[#DFBF82]'
                              }`}
                            >
                              {bInfo.current_verdict}
                            </span>
                          </div>
                          <div className="text-[11px] text-[#5A6E82] mt-1 font-mono">
                            {bInfo.total_scans} scan(s) • {bInfo.compliant_scans} compliant •{' '}
                            {bInfo.non_compliant_scans} non-compliant
                          </div>
                        </div>

                        {bInfo.last_scanned_at && (
                          <div className="text-[11px] text-[#5A6E82] font-mono shrink-0">
                            {new Date(bInfo.last_scanned_at).toLocaleDateString()}
                          </div>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="p-6 text-center text-xs text-[#5A6E82] font-mono">
                      No distinct batch code declarations detected yet.
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Scan History Log */}
            {ledgerData.scan_history && ledgerData.scan_history.length > 0 && (
              <div className="bg-white border border-[#D8D2C6] p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-[#E2DDD5] pb-3">
                  <h3 className="text-sm font-serif font-bold text-[#1C2B3A] flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-[#1C2B3A]" />
                    Audit Register Timeline ({ledgerData.scan_history.length} Entries)
                  </h3>
                  <span className="text-[11px] font-mono text-[#5A6E82]">Chronological Order</span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="text-[#5A6E82] border-b border-[#E2DDD5] font-semibold uppercase font-mono">
                        <th className="py-2.5 px-3">Docket ID</th>
                        <th className="py-2.5 px-3">Date</th>
                        <th className="py-2.5 px-3">Batch</th>
                        <th className="py-2.5 px-3">Sensor Tier</th>
                        <th className="py-2.5 px-3">Verdict</th>
                        <th className="py-2.5 px-3">Violations</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E2DDD5] font-mono">
                      {ledgerData.scan_history.map(s => (
                        <tr key={s.scan_id} className="hover:bg-[#F7F5F0] transition-colors">
                          <td className="py-3 px-3 text-[#1C2B3A] font-bold">#{s.scan_id}</td>
                          <td className="py-3 px-3 text-[#5A6E82]">
                            {s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}
                          </td>
                          <td className="py-3 px-3 text-[#1C2B3A]">{s.batch_code || 'Unspecified'}</td>
                          <td className="py-3 px-3 text-[#5A6E82] uppercase text-[11px]">
                            {s.calibration_tier.replace(/_/g, ' ')}
                          </td>
                          <td className="py-3 px-3">
                            <span
                              className={`px-2 py-0.5 text-[11px] font-bold uppercase ${
                                s.compliance_status === 'compliant'
                                  ? 'bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE]'
                                  : 'bg-[#F9EBE9] text-[#A8342A] border border-[#E09891]'
                              }`}
                            >
                              {s.compliance_status}
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            {s.violations_count > 0 ? (
                              <span className="text-[#A8342A] font-bold">{s.violations_count} detected</span>
                            ) : (
                              <span className="text-[#2F6F4E] font-bold">None (Clean)</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="border-t border-[#D8D2C6] bg-white py-5 px-6 text-center text-xs text-[#5A6E82] font-mono space-y-1">
        <div>Legal Metrology (Packaged Commodities) Rules 2011 & Consumer Protection Regulatory Engine</div>
        <div className="text-[11px] text-[#8A9AA8]">
          InnoveXguard AI • Hardware-calibrated depth & statutory rule auditing
        </div>
      </footer>
    </div>
  );
};

