import React, { useState } from 'react';
import { QrCode, Copy, Check, Download, ExternalLink, X, ShieldCheck } from 'lucide-react';
import type { QRCodeData, ScanResult } from '../types';

interface QRVerificationModalProps {
  isOpen: boolean;
  onClose: () => void;
  qrData?: QRCodeData;
  scan: ScanResult;
}

export const QRVerificationModal: React.FC<QRVerificationModalProps> = ({
  isOpen,
  onClose,
  qrData,
  scan,
}) => {
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const rawId = scan.scan_uid || (scan.scan_id ? String(scan.scan_id) : '001');
  const verificationId = qrData?.verification_id || scan.verification_id || `LM-VERIFY-${rawId.slice(0, 8).toUpperCase()}`;
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:5173';
  const verifyUrl = `${origin}/?verify=${verificationId}`;
  const qrImage = qrData?.qr_code_data_url;

  const handleCopy = () => {
    navigator.clipboard.writeText(verifyUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleDownload = () => {
    if (!qrImage) return;
    const link = document.createElement('a');
    link.href = qrImage;
    link.download = `${verificationId}-official-badge.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const isCompliant = scan.compliance_status === 'compliant' || scan.compliant !== false;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-200 font-sans">
      <div className="relative w-full max-w-lg bg-white border border-[#D8D2C6] rounded-none shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2A3F55] bg-[#1C2B3A] text-white">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-[#2A3F55] border border-[#3E5671] text-emerald-300">
              <QrCode className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-serif font-bold text-white text-base">Digital Product Verification Profile</h3>
              <p className="text-xs text-[#94A3B8]">Rule 6(1) Citizen Verification Protocol</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-[#94A3B8] hover:text-white p-1.5 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-5 overflow-y-auto max-h-[80vh] text-[#1C2B3A]">
          {/* QR & Badge Card */}
          <div className="bg-[#F7F5F0] border border-[#D8D2C6] p-6 text-center flex flex-col items-center">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-mono font-bold uppercase tracking-wider mb-4 border bg-[#EAF4EE] text-[#2F6F4E] border-[#9BC6AE]">
              <ShieldCheck className="w-3.5 h-3.5" />
              Verified Legal Metrology Certificate
            </div>

            {qrImage ? (
              <div className="bg-white p-3.5 shadow-xs inline-block my-2 border border-[#D8D2C6]">
                <img src={qrImage} alt="Verification QR Code" className="w-44 h-44 object-contain" />
              </div>
            ) : (
              <div className="w-44 h-44 bg-[#EBE7DF] border-2 border-dashed border-[#D8D2C6] flex items-center justify-center text-[#5A6E82] text-sm font-mono">
                QR Not Generated
              </div>
            )}

            <div className="mt-3">
              <p className="text-xs font-mono text-[#5A6E82] uppercase tracking-wider">Verification Reference</p>
              <p className="text-lg font-mono font-bold text-[#1C2B3A] mt-0.5 tracking-wide">{verificationId}</p>
            </div>

            {/* Product Quick Info */}
            <div className="w-full mt-4 pt-4 border-t border-[#D8D2C6] grid grid-cols-2 gap-2 text-left text-xs">
              <div>
                <span className="text-[#5A6E82] font-medium">Product / Brand:</span>
                <p className="font-bold text-[#1C2B3A] truncate">
                  {scan.fields?.brand_name?.extracted_value || scan.product_name || 'Packaged Commodity'}
                </p>
              </div>
              <div>
                <span className="text-[#5A6E82] font-medium">Declared MRP:</span>
                <p className="font-bold text-[#1C2B3A]">
                  {scan.fields?.mrp?.extracted_value || 'Declared on Pack'}
                </p>
              </div>
              <div>
                <span className="text-[#5A6E82] font-medium">Status:</span>
                <p className={`font-bold ${isCompliant ? 'text-[#2F6F4E]' : 'text-[#A8342A]'}`}>
                  {isCompliant ? 'COMPLIANT' : 'NON-COMPLIANT'}
                </p>
              </div>
              <div>
                <span className="text-[#5A6E82] font-medium">Jurisdiction:</span>
                <p className="font-semibold text-[#1C2B3A]">PCR 2011 (Govt of India)</p>
              </div>
            </div>
          </div>

          {/* Verification Link Input */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-[#1C2B3A]">Public Consumer Verification Link</label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={verifyUrl}
                className="flex-1 bg-[#F7F5F0] border border-[#D8D2C6] px-3 py-2 text-xs font-mono text-[#1C2B3A] focus:outline-none focus:border-[#1C2B3A]"
              />
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3.5 py-2 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white text-xs font-bold transition shadow-xs"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <p className="text-[11px] text-[#5A6E82]">
              Any consumer or inspector can scan or open this link to inspect statutory declarations without login.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-3 pt-2">
            {qrImage && (
              <button
                onClick={handleDownload}
                className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] text-xs font-bold border border-[#D8D2C6] transition"
              >
                <Download className="w-3.5 h-3.5 text-[#5A6E82]" />
                <span>Download QR Badge</span>
              </button>
            )}

            <a
              href={verifyUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white text-xs font-bold transition shadow-xs"
            >
              <span>Open Public Dossier</span>
              <ExternalLink className="w-3.5 h-3.5 text-emerald-400" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
