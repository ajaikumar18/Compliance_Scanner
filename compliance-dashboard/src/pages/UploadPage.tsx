import React, { useState } from 'react';
import { UploadCloud, FolderUp, Globe, FileImage, CheckCircle, Loader2, Play, Smartphone, Sparkles } from 'lucide-react';
import { queueEcommerceCategoryScan, uploadBatchFiles, uploadSingleScan } from '../services/api';
import { ARMobileCaptureModal } from '../components/ARMobileCaptureModal';
import type { ScanResult } from '../types';

interface UploadPageProps {
  onScanCompleted: (result: ScanResult) => void;
  onBatchQueued: (batchId: string) => void;
  onBatchCompleted?: (results: ScanResult[]) => void;
}

export const UploadPage = ({ onScanCompleted, onBatchQueued, onBatchCompleted }: UploadPageProps) => {
  const [activeTab, setActiveTab] = useState<'single' | 'batch' | 'ecommerce'>('single');

  // Single Upload State
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [singlePreview, setSinglePreview] = useState<string | null>(null);
  const [category, setCategory] = useState('Packaged Foods');
  const [packageWidthMm, setPackageWidthMm] = useState<string>('');
  const [netQuantityG, setNetQuantityG] = useState<string>('');
  const [loadingSingle, setLoadingSingle] = useState(false);

  // AR Mobile Calibration State
  const [isARModalOpen, setIsARModalOpen] = useState(false);
  const [arPixelsPerMm, setArPixelsPerMm] = useState<number | undefined>(undefined);
  const [arCalibrationTier, setArCalibrationTier] = useState<string | undefined>(undefined);

  // Batch Upload State
  const [batchFiles, setBatchFiles] = useState<File[]>([]);
  const [loadingBatch, setLoadingBatch] = useState(false);
  const [batchCategory, setBatchCategory] = useState('General');

  // E-Commerce Scan State
  const [categoryUrl, setCategoryUrl] = useState('https://www.amazon.in/s?k=packaged+biscuits');
  const [maxPages, setMaxPages] = useState(1);
  const [loadingEcom, setLoadingEcom] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Handle single file drop
  const handleSingleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      // Clear stale state from previous upload
      setError(null);
      setSuccessMsg(null);
      // Revoke previous ObjectURL to prevent memory leaks
      if (singlePreview) {
        URL.revokeObjectURL(singlePreview);
      }
      setSingleFile(file);
      setSinglePreview(URL.createObjectURL(file));
    }
  };

  const handleARCapture = (file: File, calibratedPxPerMm: number, tier: string) => {
    if (singlePreview) {
      URL.revokeObjectURL(singlePreview);
    }
    setSingleFile(file);
    setSinglePreview(URL.createObjectURL(file));
    setArPixelsPerMm(calibratedPxPerMm);
    setArCalibrationTier(tier);
    setSuccessMsg(`AR Calibrated: ${calibratedPxPerMm.toFixed(2)} px/mm (${tier === 'ar_verified' ? 'WebXR AR' : 'Optical Caliper'})`);
  };

  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!singleFile) return;

    setLoadingSingle(true);
    setError(null);
    try {
      const res = await uploadSingleScan(singleFile, {
        category,
        packageWidthMm: packageWidthMm ? parseFloat(packageWidthMm) : undefined,
        netQuantityG: netQuantityG ? parseFloat(netQuantityG) : undefined,
        arPixelsPerMm: arPixelsPerMm,
      });
      if (singlePreview) {
        res.scanned_image_url = singlePreview;
      }
      onScanCompleted(res);
    } catch (err: any) {
      setError(err.message || 'Failed to scan image.');
    } finally {
      setLoadingSingle(false);
    }
  };

  // Handle batch file drop
  const handleBatchFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const filesArr = Array.from(e.target.files);
      setBatchFiles(filesArr);
    }
  };

  const handleBatchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (batchFiles.length === 0) return;

    setLoadingBatch(true);
    setError(null);
    try {
      const results = await uploadBatchFiles(batchFiles, batchCategory);
      if (results && results.length > 0) {
        setSuccessMsg(`Successfully processed ${results.length} product scans!`);
        if (onBatchCompleted) {
          onBatchCompleted(results);
        } else {
          onScanCompleted(results[0]);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Batch upload failed.');
    } finally {
      setLoadingBatch(false);
    }
  };

  // Handle e-commerce category scan
  const handleEcomSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!categoryUrl) return;

    setLoadingEcom(true);
    setError(null);
    try {
      const res = await queueEcommerceCategoryScan(categoryUrl, maxPages);
      setSuccessMsg(`E-Commerce scraper queued successfully! Batch ID: ${res.batch_id}`);
      onBatchQueued(res.batch_id);
    } catch (err: any) {
      setError(err.message || 'Failed to queue e-commerce scan task.');
    } finally {
      setLoadingEcom(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-6">
      <div className="text-center space-y-2">
        <span className="text-[10px] font-mono uppercase px-2.5 py-0.5 bg-[#1C2B3A] text-white font-bold tracking-widest">
          STATUTORY COMPLIANCE FILING SYSTEM
        </span>
        <h1 className="text-3xl font-serif font-bold text-[#1C2B3A] tracking-tight">
          Product Label Evidence Submission
        </h1>
        <p className="text-[#5A6E82] text-xs max-w-xl mx-auto leading-relaxed">
          Upload packaging specimens or scrape e-commerce catalogs for immediate Legal Metrology & FSSAI statutory declaration auditing.
        </p>
      </div>

      {/* Mode Navigation Tabs styled as dossier file tabs */}
      <div className="flex justify-center">
        <div className="inline-flex p-1 bg-white border border-[#D8D2C6]">
          <button
            onClick={() => setActiveTab('single')}
            className={`flex items-center gap-2 px-5 py-2 text-xs font-semibold tracking-wide transition-all ${
              activeTab === 'single'
                ? 'bg-[#1C2B3A] text-white'
                : 'text-[#5A6E82] hover:text-[#1C2B3A] hover:bg-[#F7F5F0]'
            }`}
          >
            <UploadCloud className="w-4 h-4" />
            Single Specimen Scan
          </button>

          <button
            onClick={() => setActiveTab('batch')}
            className={`flex items-center gap-2 px-5 py-2 text-xs font-semibold tracking-wide transition-all ${
              activeTab === 'batch'
                ? 'bg-[#1C2B3A] text-white'
                : 'text-[#5A6E82] hover:text-[#1C2B3A] hover:bg-[#F7F5F0]'
            }`}
          >
            <FolderUp className="w-4 h-4" />
            Batch Folder Filing
          </button>

          <button
            onClick={() => setActiveTab('ecommerce')}
            className={`flex items-center gap-2 px-5 py-2 text-xs font-semibold tracking-wide transition-all ${
              activeTab === 'ecommerce'
                ? 'bg-[#1C2B3A] text-white'
                : 'text-[#5A6E82] hover:text-[#1C2B3A] hover:bg-[#F7F5F0]'
            }`}
          >
            <Globe className="w-4 h-4" />
            E-Commerce Surveillance
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-[#F9EBE9] border border-[#E09891] text-[#A8342A] text-xs text-center font-mono">
          {error}
        </div>
      )}

      {successMsg && (
        <div className="p-4 bg-[#EAF4EE] border border-[#9BC6AE] text-[#2F6F4E] text-xs text-center flex items-center justify-center gap-2 font-mono">
          <CheckCircle className="w-4 h-4 text-[#2F6F4E]" />
          {successMsg}
        </div>
      )}

      {/* Tab 1: Single Image Scan */}
      {activeTab === 'single' && (
        <form onSubmit={handleSingleSubmit} className="bg-white border border-[#D8D2C6] p-6 sm:p-8 space-y-6">
          {/* On-Device AR Scale Calibration Action Banner */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 bg-[#FAF3E6] border border-[#DFBF82] gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-white border border-[#DFBF82] text-[#B8862B] shrink-0">
                <Smartphone className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-serif font-bold text-[#1C2B3A]">Live Mobile AR Scale Calibrator</h3>
                  <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase bg-white border border-[#DFBF82] text-[#B8862B]">
                    Tier 1 (±0.05mm)
                  </span>
                </div>
                <p className="text-xs text-[#5A6E82] mt-0.5">
                  Tap 2 points on live camera to calculate exact physical millimeters via WebXR depth API.
                </p>
                {arPixelsPerMm && (
                  <p className="text-xs font-mono text-[#2F6F4E] mt-1 font-bold">
                    ✓ Calibrated: {arPixelsPerMm.toFixed(2)} px/mm ({arCalibrationTier === 'ar_verified' ? 'WebXR AR Verified' : 'Optical Caliper'})
                  </p>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIsARModalOpen(true)}
              className="px-4 py-2.5 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white font-semibold text-xs border border-[#1C2B3A] transition flex items-center justify-center gap-2 cursor-pointer shrink-0"
            >
              <Sparkles className="w-4 h-4 text-[#DFBF82]" />
              Measure via AR Camera
            </button>
          </div>

          <div className="border-2 border-dashed border-[#D8D2C6] hover:border-[#1C2B3A] p-8 text-center transition-colors relative cursor-pointer group bg-[#F7F5F0]">
            <input
              type="file"
              accept="image/*"
              onChange={handleSingleFileChange}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-10"
            />
            {singlePreview ? (
              <div className="space-y-4">
                <img src={singlePreview} alt="Preview" className="max-h-64 mx-auto border border-[#D8D2C6] object-contain bg-white" />
                <p className="text-xs text-[#1C2B3A] font-mono">Exhibit: {singleFile?.name}</p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="w-12 h-12 bg-white border border-[#D8D2C6] text-[#1C2B3A] flex items-center justify-center mx-auto">
                  <FileImage className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm font-serif font-bold text-[#1C2B3A]">Drop Packaging Specimen Photo Here</p>
                  <p className="text-xs text-[#5A6E82] mt-1">Supports PNG, JPG, JPEG, WEBP up to 20MB</p>
                </div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-mono uppercase font-semibold text-[#1C2B3A] mb-2">Category</label>
              <input
                type="text"
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-white border border-[#D8D2C6] text-[#1C2B3A] text-sm focus:outline-none focus:border-[#1C2B3A]"
                placeholder="e.g. Beverages"
              />
            </div>
            <div>
              <label className="block text-xs font-mono uppercase font-semibold text-[#1C2B3A] mb-2">Package Width (mm)</label>
              <input
                type="number"
                value={packageWidthMm}
                onChange={e => setPackageWidthMm(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-white border border-[#D8D2C6] text-[#1C2B3A] text-sm font-mono focus:outline-none focus:border-[#1C2B3A]"
                placeholder="e.g. 150"
              />
            </div>
            <div>
              <label className="block text-xs font-mono uppercase font-semibold text-[#1C2B3A] mb-2">Net Quantity (g / ml)</label>
              <input
                type="number"
                value={netQuantityG}
                onChange={e => setNetQuantityG(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-white border border-[#D8D2C6] text-[#1C2B3A] text-sm font-mono focus:outline-none focus:border-[#1C2B3A]"
                placeholder="e.g. 500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={!singleFile || loadingSingle}
            className="w-full py-3.5 px-6 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white font-semibold text-sm border border-[#1C2B3A] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loadingSingle ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5 fill-current" />}
            {loadingSingle ? 'Executing Statutory OCR & Calibration Analysis...' : 'Submit Specimen for Compliance Audit'}
          </button>
        </form>
      )}

      {/* Tab 2: Batch Folder Upload */}
      {activeTab === 'batch' && (
        <form onSubmit={handleBatchSubmit} className="bg-white border border-[#D8D2C6] p-6 sm:p-8 space-y-6">
          <div className="border-2 border-dashed border-[#D8D2C6] hover:border-[#1C2B3A] p-8 text-center transition-colors relative cursor-pointer bg-[#F7F5F0]">
            <input
              type="file"
              multiple
              accept="image/*"
              onChange={handleBatchFileChange}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-10"
            />
            <div className="space-y-3">
              <div className="w-12 h-12 bg-white border border-[#D8D2C6] text-[#1C2B3A] flex items-center justify-center mx-auto">
                <FolderUp className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-serif font-bold text-[#1C2B3A]">Select Multiple Packaging Specimens</p>
                <p className="text-xs text-[#5A6E82] mt-1">Select a folder or batch of image files for parallel auditing</p>
              </div>
              {batchFiles.length > 0 && (
                <div className="mt-4 p-3 bg-white border border-[#D8D2C6] text-[#1C2B3A] text-xs font-mono font-bold">
                  📁 {batchFiles.length} specimen files queued for analysis
                </div>
              )}
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono uppercase font-semibold text-[#1C2B3A] mb-2">Batch Category</label>
            <input
              type="text"
              value={batchCategory}
              onChange={e => setBatchCategory(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-white border border-[#D8D2C6] text-[#1C2B3A] text-sm focus:outline-none focus:border-[#1C2B3A]"
              placeholder="e.g. FMCG Packaged Commodities"
            />
          </div>

          <button
            type="submit"
            disabled={batchFiles.length === 0 || loadingBatch}
            className="w-full py-3.5 px-6 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white font-semibold text-sm border border-[#1C2B3A] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loadingBatch ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5 fill-current" />}
            {loadingBatch ? `Auditing ${batchFiles.length} Files...` : `Process Batch Docket (${batchFiles.length} Images)`}
          </button>
        </form>
      )}

      {/* Tab 3: E-Commerce Category Scan */}
      {activeTab === 'ecommerce' && (
        <form onSubmit={handleEcomSubmit} className="bg-white border border-[#D8D2C6] p-6 sm:p-8 space-y-6">
          <div>
            <label className="block text-xs font-mono uppercase font-semibold text-[#1C2B3A] mb-2">
              E-Commerce Category Listing URL
            </label>
            <div className="relative">
              <Globe className="w-5 h-5 text-[#5A6E82] absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="url"
                required
                value={categoryUrl}
                onChange={e => setCategoryUrl(e.target.value)}
                placeholder="https://www.amazon.in/s?k=packaged+biscuits"
                className="w-full pl-11 pr-4 py-3 bg-white border border-[#D8D2C6] text-[#1C2B3A] text-sm font-mono focus:outline-none focus:border-[#1C2B3A]"
              />
            </div>
            <p className="text-xs text-[#5A6E82] mt-2">
              Audits Rule 6(10) mandatory declarations across Amazon, Flipkart, BigBasket, and Zepto.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-mono uppercase font-semibold text-[#1C2B3A] mb-2">
                Max Catalog Pages
              </label>
              <select
                value={maxPages}
                onChange={e => setMaxPages(parseInt(e.target.value))}
                className="w-full px-3.5 py-2.5 bg-white border border-[#D8D2C6] text-[#1C2B3A] text-sm focus:outline-none focus:border-[#1C2B3A]"
              >
                <option value={1}>1 Page (~20 items)</option>
                <option value={2}>2 Pages (~40 items)</option>
                <option value={3}>3 Pages (~60 items)</option>
                <option value={5}>5 Pages (~100 items)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-mono uppercase font-semibold text-[#1C2B3A] mb-2">
                Surveillance Worker
              </label>
              <div className="px-3.5 py-2.5 bg-[#F7F5F0] border border-[#D8D2C6] text-xs font-mono text-[#1C2B3A] flex items-center justify-between">
                <span>Scrapy + Celery Redis Worker</span>
                <span className="w-2 h-2 bg-[#2F6F4E] animate-pulse" />
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loadingEcom || !categoryUrl}
            className="w-full py-3.5 px-6 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white font-semibold text-sm border border-[#1C2B3A] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loadingEcom ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5 fill-current" />}
            {loadingEcom ? 'Scraping E-Commerce Catalog...' : 'Launch Automated Compliance Scraper'}
          </button>
        </form>
      )}

      {/* AR Mobile Capture Modal */}
      <ARMobileCaptureModal
        isOpen={isARModalOpen}
        onClose={() => setIsARModalOpen(false)}
        onCapture={handleARCapture}
      />
    </div>
  );
};
