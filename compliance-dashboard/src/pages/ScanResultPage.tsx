import { useState } from 'react';
import { Download, AlertTriangle, CheckCircle, HelpCircle, FileText, ArrowLeft, ShieldAlert, Cpu } from 'lucide-react';
import { BoundingBoxCanvas } from '../components/BoundingBoxCanvas';
import { getReportDownloadUrl } from '../services/api';
import type { ScanResult } from '../types';

interface ScanResultPageProps {
  scan: ScanResult;
  onBackToHistory: () => void;
}

export const ScanResultPage = ({ scan, onBackToHistory }: ScanResultPageProps) => {
  const [selectedField, setSelectedField] = useState<string | null>(null);

  const getVerdictBadge = (status: string) => {
    switch (status) {
      case 'compliant':
        return {
          label: 'FULLY COMPLIANT',
          bg: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
          icon: <CheckCircle className="w-5 h-5 text-emerald-400" />,
        };
      case 'non_compliant':
        return {
          label: 'NON-COMPLIANT (VIOLATIONS DETECTED)',
          bg: 'bg-rose-500/10 border-rose-500/30 text-rose-400',
          icon: <AlertTriangle className="w-5 h-5 text-rose-400" />,
        };
      default:
        return {
          label: 'PARTIAL REVIEW NEEDED (GENAI / LOW CONFIDENCE)',
          bg: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
          icon: <HelpCircle className="w-5 h-5 text-amber-400" />,
        };
    }
  };

  const verdict = getVerdictBadge(scan.compliance_status);

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 space-y-6">
      {/* Top Header & Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-panel p-6 rounded-2xl">
        <div className="flex items-center gap-4">
          <button
            onClick={onBackToHistory}
            className="p-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 transition-colors"
            title="Back to History"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-white tracking-tight">{scan?.product_name || 'Product Label Scan'}</h1>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                Scan #{scan?.scan_id || '001'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Category: {scan?.product_category || 'Packaged Foods'} • Scan Mode: {(scan?.scan_type || 'manual').toUpperCase()}
            </p>
          </div>
        </div>

        {/* Report Download Buttons */}
        <div className="flex items-center gap-3">
          <a
            href={getReportDownloadUrl(scan.scan_id, 'pdf')}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all"
          >
            <Download className="w-4 h-4" />
            Download PDF
          </a>

          <a
            href={getReportDownloadUrl(scan.scan_id, 'docx')}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all"
          >
            <FileText className="w-4 h-4 text-blue-400" />
            Download Word (.docx)
          </a>
        </div>
      </div>

      {/* Overall Compliance Verdict Banner */}
      <div className={`p-4 rounded-2xl border flex items-center justify-between gap-4 ${verdict.bg}`}>
        <div className="flex items-center gap-3">
          {verdict.icon}
          <div>
            <h3 className="font-bold text-sm tracking-wide">{verdict.label}</h3>
            <p className="text-xs opacity-80 mt-0.5">
              Evaluated against Indian Legal Metrology (Packaged Commodities) Rules 2011 & FSSAI Guidelines.
            </p>
          </div>
        </div>
        <div className="text-xs font-mono font-bold px-3 py-1.5 rounded-lg bg-slate-950/40 border border-current">
          Violations: {scan.violations_count}
        </div>
      </div>

      {/* Main Split Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Pane: Interactive Label Image with Bounding Box Overlay */}
        <div className="lg:col-span-5 space-y-4">
          <div className="glass-panel p-4 rounded-2xl">
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-400" />
              Scanned Label Bounding Box Map
            </h3>
            <BoundingBoxCanvas
              imageUrl={scan.scanned_image_url || 'https://images.unsplash.com/photo-1550583724-b2692b85b150?auto=format&fit=crop&w=600&q=80'}
              fields={scan.fields || {}}
              selectedField={selectedField}
              onSelectField={setSelectedField}
            />
            <div className="mt-3 flex items-center justify-center gap-4 text-xs font-medium text-slate-400">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Compliant
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> GenAI / Fallback
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500" /> Violation
              </span>
            </div>
          </div>
        </div>

        {/* Right Pane: Extracted Fields & Violations Detail */}
        <div className="lg:col-span-7 space-y-6">
          {/* Violations Detail Section */}
          {scan.violations && scan.violations.length > 0 && (
            <div className="glass-panel p-6 rounded-2xl border-rose-500/30">
              <h3 className="text-sm font-bold text-rose-300 uppercase tracking-wider mb-4 flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-rose-400" />
                Detected Compliance Violations ({scan.violations.length})
              </h3>
              <div className="space-y-3">
                {scan.violations.map((v, idx) => {
                  let sevBg = 'bg-rose-500/20 text-rose-300 border-rose-500/40';
                  if (v.severity === 'medium') sevBg = 'bg-amber-500/20 text-amber-300 border-amber-500/40';
                  if (v.severity === 'low') sevBg = 'bg-blue-500/20 text-blue-300 border-blue-500/40';

                  return (
                    <div key={idx} className="p-4 rounded-xl glass-card border border-rose-500/20 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-white uppercase font-mono">{v.field_name}</span>
                        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${sevBg}`}>
                          {v.severity} Severity
                        </span>
                      </div>
                      <p className="text-xs text-slate-300">{v.details}</p>
                      {v.rule_reference && (
                        <p className="text-[11px] text-slate-400 font-mono italic">Ref: {v.rule_reference}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Extracted Fields Table */}
          <div className="glass-panel p-6 rounded-2xl space-y-4">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Mandatory Label Declarations</h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-xs uppercase tracking-wider">
                    <th className="pb-3 font-semibold">Field Name</th>
                    <th className="pb-3 font-semibold">Extracted Text</th>
                    <th className="pb-3 font-semibold">Method</th>
                    <th className="pb-3 font-semibold">Font Height</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-xs">
                  {Object.entries(scan.fields || {}).map(([fName, info]) => {
                    const isSelected = selectedField === fName;
                    let methodBadge = 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30';
                    if (info.extraction_method === 'genai_fallback') methodBadge = 'bg-purple-500/20 text-purple-300 border-purple-500/30';
                    if (info.extraction_method === 'not_found') methodBadge = 'bg-rose-500/20 text-rose-300 border-rose-500/30';

                    return (
                      <tr
                        key={fName}
                        onClick={() => setSelectedField(fName)}
                        className={`cursor-pointer transition-colors ${
                          isSelected ? 'bg-indigo-500/10' : 'hover:bg-slate-800/40'
                        }`}
                      >
                        <td className="py-3 font-bold text-slate-200 capitalize">{fName.replace(/_/g, ' ')}</td>
                        <td className="py-3 text-slate-300 max-w-[200px] truncate">
                          {info.extracted_value || <span className="text-rose-400 italic">NOT FOUND</span>}
                        </td>
                        <td className="py-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${methodBadge}`}>
                            {info.extraction_method}
                          </span>
                        </td>
                        <td className="py-3">
                          {info.measured_mm ? (
                            <span className={info.font_compliant === false ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                              {info.measured_mm}mm (req {info.required_mm}mm)
                            </span>
                          ) : (
                            <span className="text-slate-500">N/A</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
