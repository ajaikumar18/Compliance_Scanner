import React, { useState } from 'react';
import { UploadCloud, FolderUp, Globe, FileImage, CheckCircle, Loader2, Play } from 'lucide-react';
import { queueEcommerceCategoryScan, uploadBatchFiles, uploadSingleScan } from '../services/api';
import type { ScanResult } from '../types';

interface UploadPageProps {
  onScanCompleted: (result: ScanResult) => void;
  onBatchQueued: (batchId: string) => void;
}

export const UploadPage = ({ onScanCompleted, onBatchQueued }: UploadPageProps) => {
  const [activeTab, setActiveTab] = useState<'single' | 'batch' | 'ecommerce'>('single');

  // Single Upload State
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [singlePreview, setSinglePreview] = useState<string | null>(null);
  const [category, setCategory] = useState('Packaged Foods');
  const [packageWidthMm, setPackageWidthMm] = useState<string>('');
  const [netQuantityG, setNetQuantityG] = useState<string>('');
  const [loadingSingle, setLoadingSingle] = useState(false);

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
      setSingleFile(file);
      setSinglePreview(URL.createObjectURL(file));
    }
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
      });
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
        onScanCompleted(results[0]);
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
    <div className="max-w-4xl mx-auto py-8 px-4">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-white tracking-tight">Product Label Compliance Scanner</h1>
        <p className="text-slate-400 mt-2 text-sm max-w-xl mx-auto">
          Upload product images or scrape e-commerce categories to perform instant Legal Metrology & FSSAI compliance verification.
        </p>
      </div>

      {/* Mode Navigation Tabs */}
      <div className="flex justify-center mb-8">
        <div className="inline-flex p-1.5 glass-panel rounded-2xl border border-slate-800">
          <button
            onClick={() => setActiveTab('single')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
              activeTab === 'single'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <UploadCloud className="w-4 h-4" />
            Single Label Scan
          </button>

          <button
            onClick={() => setActiveTab('batch')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
              activeTab === 'batch'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <FolderUp className="w-4 h-4" />
            Batch Folder Upload
          </button>

          <button
            onClick={() => setActiveTab('ecommerce')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
              activeTab === 'ecommerce'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Globe className="w-4 h-4" />
            E-Commerce Scan
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm text-center">
          {error}
        </div>
      )}

      {successMsg && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm text-center flex items-center justify-center gap-2">
          <CheckCircle className="w-5 h-5 text-emerald-400" />
          {successMsg}
        </div>
      )}

      {/* Tab 1: Single Image Scan */}
      {activeTab === 'single' && (
        <form onSubmit={handleSingleSubmit} className="glass-panel p-8 rounded-2xl shadow-2xl space-y-6">
          <div className="border-2 border-dashed border-slate-700 hover:border-indigo-500 rounded-2xl p-8 text-center transition-colors relative cursor-pointer group bg-slate-950/40">
            <input
              type="file"
              accept="image/*"
              onChange={handleSingleFileChange}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-10"
            />
            {singlePreview ? (
              <div className="space-y-4">
                <img src={singlePreview} alt="Preview" className="max-h-64 mx-auto rounded-xl shadow-lg border border-slate-800 object-contain" />
                <p className="text-xs text-indigo-300 font-mono">Selected: {singleFile?.name}</p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mx-auto group-hover:scale-110 transition-transform">
                  <FileImage className="w-7 h-7" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-200">Drag & drop product label image here</p>
                  <p className="text-xs text-slate-400 mt-1">Supports PNG, JPG, JPEG, WEBP up to 20MB</p>
                </div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Category</label>
              <input
                type="text"
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl glass-input text-sm"
                placeholder="e.g. Beverages"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Package Width (mm)</label>
              <input
                type="number"
                value={packageWidthMm}
                onChange={e => setPackageWidthMm(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl glass-input text-sm"
                placeholder="e.g. 150 (Optional scale calibration)"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Net Quantity (g / ml)</label>
              <input
                type="number"
                value={netQuantityG}
                onChange={e => setNetQuantityG(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl glass-input text-sm"
                placeholder="e.g. 500 (For font rules)"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={!singleFile || loadingSingle}
            className="w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loadingSingle ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5 fill-current" />}
            {loadingSingle ? 'Analyzing Product Label...' : 'Run Compliance Scan'}
          </button>
        </form>
      )}

      {/* Tab 2: Batch Folder Upload */}
      {activeTab === 'batch' && (
        <form onSubmit={handleBatchSubmit} className="glass-panel p-8 rounded-2xl shadow-2xl space-y-6">
          <div className="border-2 border-dashed border-slate-700 hover:border-indigo-500 rounded-2xl p-8 text-center transition-colors relative cursor-pointer bg-slate-950/40">
            <input
              type="file"
              multiple
              accept="image/*"
              onChange={handleBatchFileChange}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-10"
            />
            <div className="space-y-3">
              <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mx-auto">
                <FolderUp className="w-7 h-7" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-200">Select multiple product label images</p>
                <p className="text-xs text-slate-400 mt-1">Select a folder or batch of image files</p>
              </div>
              {batchFiles.length > 0 && (
                <div className="mt-4 p-3 bg-indigo-500/10 rounded-xl border border-indigo-500/30 text-indigo-300 text-sm font-medium">
                  📁 {batchFiles.length} files selected for batch analysis
                </div>
              )}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Batch Category</label>
            <input
              type="text"
              value={batchCategory}
              onChange={e => setBatchCategory(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl glass-input text-sm"
              placeholder="e.g. FMCG Grocery"
            />
          </div>

          <button
            type="submit"
            disabled={batchFiles.length === 0 || loadingBatch}
            className="w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loadingBatch ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5 fill-current" />}
            {loadingBatch ? `Processing ${batchFiles.length} Scans...` : `Process Batch (${batchFiles.length} Images)`}
          </button>
        </form>
      )}

      {/* Tab 3: E-Commerce Category Scan */}
      {activeTab === 'ecommerce' && (
        <form onSubmit={handleEcomSubmit} className="glass-panel p-8 rounded-2xl shadow-2xl space-y-6">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              E-Commerce Category URL
            </label>
            <div className="relative">
              <Globe className="w-5 h-5 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="url"
                required
                value={categoryUrl}
                onChange={e => setCategoryUrl(e.target.value)}
                placeholder="https://www.amazon.in/s?k=packaged+biscuits"
                className="w-full pl-11 pr-4 py-3 rounded-xl glass-input text-sm"
              />
            </div>
            <p className="text-xs text-slate-400 mt-2">
              Supports Amazon, Flipkart, BigBasket, and general e-commerce listing pages.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Max Pages to Scrape
              </label>
              <select
                value={maxPages}
                onChange={e => setMaxPages(parseInt(e.target.value))}
                className="w-full px-4 py-2.5 rounded-xl glass-input text-sm"
              >
                <option value={1}>1 Page (~20 items)</option>
                <option value={2}>2 Pages (~40 items)</option>
                <option value={3}>3 Pages (~60 items)</option>
                <option value={5}>5 Pages (~100 items)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Background Engine
              </label>
              <div className="px-4 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800 text-xs font-mono text-indigo-300 flex items-center justify-between">
                <span>Scrapy + Celery Redis Task</span>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loadingEcom || !categoryUrl}
            className="w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loadingEcom ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5 fill-current" />}
            {loadingEcom ? 'Launching E-Commerce Scraper...' : 'Launch Scraper & Batch Scan'}
          </button>
        </form>
      )}
    </div>
  );
};
