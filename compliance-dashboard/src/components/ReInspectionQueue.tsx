import { useState, useEffect } from 'react';
import {
  AlertOctagon,
  ArrowRight,
  CheckCircle2,
  Clock,
  ExternalLink,
  Flame,
  RefreshCw,
  Search,
  ShieldAlert,
  UserCheck,
} from 'lucide-react';
import {
  fetchReInspectionTickets,
  fetchTicketSummaryStats,
  updateTicketStatus,
} from '../services/api';
import type { ReInspectionTicket, TicketSummaryStats } from '../types';

interface ReInspectionQueueProps {
  onSelectScan?: (scanId: number) => void;
  onViewGtinTrust?: (gtin: string) => void;
}

export const ReInspectionQueue = ({ onSelectScan }: ReInspectionQueueProps) => {
  const [tickets, setTickets] = useState<ReInspectionTicket[]>([]);
  const [stats, setStats] = useState<TicketSummaryStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('active');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [searchGtin, setSearchGtin] = useState<string>('');
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [resolutionInputId, setResolutionInputId] = useState<number | null>(null);
  const [resolutionNote, setResolutionNote] = useState<string>('');

  const loadTicketsAndStats = async () => {
    setIsLoading(true);
    try {
      const [ticketData, statsData] = await Promise.all([
        fetchReInspectionTickets(statusFilter === 'active' ? undefined : statusFilter, priorityFilter),
        fetchTicketSummaryStats(),
      ]);
      setTickets(ticketData);
      setStats(statsData);
    } catch (err) {
      console.error('Failed to load tickets:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTicketsAndStats();
  }, [statusFilter, priorityFilter]);

  const handleStatusChange = async (ticketId: number, newStatus: string, notes?: string) => {
    setUpdatingId(ticketId);
    try {
      await updateTicketStatus(ticketId, {
        status: newStatus,
        assigned_to: newStatus === 'investigating' ? 'Field Inspector' : undefined,
        resolution_notes: notes || undefined,
      });

      setTickets(prev =>
        prev.map(t =>
          t.id === ticketId
            ? {
                ...t,
                status: newStatus as any,
                resolution_notes: notes || t.resolution_notes,
                assigned_to: newStatus === 'investigating' ? 'Field Inspector' : t.assigned_to,
              }
            : t
        )
      );

      const newStats = await fetchTicketSummaryStats();
      setStats(newStats);
      setResolutionInputId(null);
      setResolutionNote('');
    } catch (err) {
      console.error('Failed to update ticket status:', err);
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredTickets = tickets.filter(t => {
    if (statusFilter === 'active' && (t.status === 'resolved' || t.status === 'dismissed')) {
      return false;
    }
    if (statusFilter !== 'active' && statusFilter !== 'all' && t.status !== statusFilter) {
      return false;
    }
    if (priorityFilter !== 'all' && t.priority !== priorityFilter) {
      return false;
    }
    if (searchGtin.trim()) {
      const q = searchGtin.trim().toLowerCase();
      const matchesGtin = t.gtin.toLowerCase().includes(q);
      const matchesProduct = (t.product_name || '').toLowerCase().includes(q);
      const matchesTicketNum = t.ticket_number.toLowerCase().includes(q);
      if (!matchesGtin && !matchesProduct && !matchesTicketNum) return false;
    }
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Header & Quick Action Row */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#D8D2C6] pb-3">
        <div className="flex items-center gap-2.5">
          <span className="p-1.5 bg-[#F9EBE9] text-[#A8342A] border border-[#E09891]">
            <ShieldAlert className="w-5 h-5" />
          </span>
          <div>
            <h2 className="text-lg font-bold font-serif text-[#1C2B3A] tracking-tight flex items-center gap-2">
              Enforcement Discrepancy Queue
              {stats && stats.critical_tickets > 0 && (
                <span className="px-2 py-0.5 text-[10px] font-bold font-mono bg-[#F9EBE9] text-[#A8342A] border border-[#A8342A]">
                  {stats.critical_tickets} CRITICAL DOCKETS
                </span>
              )}
            </h2>
            <p className="text-xs text-[#5E6E80] font-sans">
              Automated re-inspection alerts generated when high-precision AR or crowd audits contradict established consensus.
            </p>
          </div>
        </div>

        <button
          onClick={loadTicketsAndStats}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-[#1C2B3A] bg-white hover:bg-[#EFECE6] border border-[#D8D2C6] transition-all self-start md:self-auto rounded-none"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-[#1C2B3A]' : ''}`} />
          Refresh Dockets
        </button>
      </div>

      {/* KPI Counters Bar - Ruled Docket Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-[#D8D2C6] bg-white border border-[#D8D2C6]">
        <div className="p-3.5 space-y-1 bg-[#F9EBE9]/30">
          <p className="text-[10px] font-semibold text-[#A8342A] uppercase tracking-wider font-sans">Critical Escalations</p>
          <p className="text-xl font-bold font-serif text-[#A8342A]">{stats?.critical_tickets ?? 0}</p>
        </div>

        <div className="p-3.5 space-y-1 bg-[#FAF3E6]/30">
          <p className="text-[10px] font-semibold text-[#B8862B] uppercase tracking-wider font-sans">High Priority Flips</p>
          <p className="text-xl font-bold font-serif text-[#B8862B]">{stats?.high_tickets ?? 0}</p>
        </div>

        <div className="p-3.5 space-y-1">
          <p className="text-[10px] font-semibold text-[#1C2B3A] uppercase tracking-wider font-sans">Open for Inspection</p>
          <p className="text-xl font-bold font-serif text-[#1C2B3A]">{stats?.open_tickets ?? 0}</p>
        </div>

        <div className="p-3.5 space-y-1 bg-[#EAF4EE]/30">
          <p className="text-[10px] font-semibold text-[#2F6F4E] uppercase tracking-wider font-sans">Resolved Dockets</p>
          <p className="text-xl font-bold font-serif text-[#2F6F4E]">{stats?.resolved_tickets ?? 0}</p>
        </div>
      </div>

      {/* Filter and Search Controls */}
      <div className="bg-[#FAF8F5] border border-[#D8D2C6] p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[#5E6E80] font-semibold mr-1 font-sans">Status:</span>
          {[
            { id: 'active', label: 'Active Alerts' },
            { id: 'open', label: 'Open' },
            { id: 'investigating', label: 'Investigating' },
            { id: 'resolved', label: 'Resolved' },
            { id: 'all', label: 'All Records' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3 py-1 rounded-none text-xs font-medium transition-all ${
                statusFilter === tab.id
                  ? 'bg-[#1C2B3A] text-white'
                  : 'bg-white text-[#1C2B3A] hover:bg-[#EFECE6] border border-[#D8D2C6]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2.5 w-full sm:w-auto">
          <select
            value={priorityFilter}
            onChange={e => setPriorityFilter(e.target.value)}
            className="px-2.5 py-1 bg-white border border-[#C4BCAC] text-xs text-[#1C2B3A] rounded-none focus:outline-none focus:border-[#1C2B3A]"
          >
            <option value="all">All Priorities</option>
            <option value="critical">Critical Only</option>
            <option value="high">High Only</option>
            <option value="medium">Medium Only</option>
          </select>

          <div className="relative flex-1 sm:w-52">
            <Search className="w-3.5 h-3.5 text-[#5E6E80] absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search GTIN / docket..."
              value={searchGtin}
              onChange={e => setSearchGtin(e.target.value)}
              className="w-full pl-8 pr-2.5 py-1 bg-white border border-[#C4BCAC] text-xs text-[#1C2B3A] placeholder-[#8C9BAA] rounded-none focus:outline-none focus:border-[#1C2B3A]"
            />
          </div>
        </div>
      </div>

      {/* Ticket Cards List */}
      <div className="space-y-3">
        {filteredTickets.length === 0 ? (
          <div className="bg-white border border-[#D8D2C6] p-8 text-center space-y-2">
            <div className="w-10 h-10 bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE] flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <h4 className="text-sm font-bold font-serif text-[#1C2B3A]">No Active Discrepancy Tickets</h4>
            <p className="text-xs text-[#5E6E80] max-w-md mx-auto">
              All recent product label scans agree with the aggregate compliance ledger consensus within allowable tolerances.
            </p>
          </div>
        ) : (
          filteredTickets.map(ticket => {
            const isCritical = ticket.priority === 'critical';
            const isHigh = ticket.priority === 'high';

            return (
              <div
                key={ticket.id}
                className={`bg-white border border-[#D8D2C6] p-5 border-l-4 ${
                  isCritical
                    ? 'border-l-[#A8342A]'
                    : isHigh
                    ? 'border-l-[#B8862B]'
                    : 'border-l-[#1C2B3A]'
                }`}
              >
                {/* Top Badge & Metadata Row */}
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Stamp-Style Priority Tag */}
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold font-mono uppercase tracking-wider border ${
                        isCritical
                          ? 'bg-[#F9EBE9] text-[#A8342A] border-[#A8342A]'
                          : isHigh
                          ? 'bg-[#FAF3E6] text-[#B8862B] border-[#B8862B]'
                          : 'bg-[#F7F5F0] text-[#1C2B3A] border-[#1C2B3A]'
                      }`}
                    >
                      {isCritical && <Flame className="w-3 h-3 text-[#A8342A]" />}
                      {ticket.priority} Escalation
                    </span>

                    {/* Status Stamp */}
                    <span
                      className={`px-2 py-0.5 text-[10px] font-mono uppercase font-semibold border ${
                        ticket.status === 'open'
                          ? 'bg-[#F7F5F0] text-[#1C2B3A] border-[#1C2B3A]'
                          : ticket.status === 'investigating'
                          ? 'bg-[#FAF3E6] text-[#B8862B] border-[#DFBF82]'
                          : ticket.status === 'resolved'
                          ? 'bg-[#EAF4EE] text-[#2F6F4E] border-[#9BC6AE]'
                          : 'bg-[#FAF8F5] text-[#5E6E80] border-[#D8D2C6]'
                      }`}
                    >
                      [{ticket.status}]
                    </span>

                    {/* Docket Monospace Number */}
                    <span className="font-mono text-xs text-[#1C2B3A] bg-[#FAF8F5] px-2 py-0.5 border border-[#D8D2C6]">
                      {ticket.ticket_number}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 text-xs text-[#5E6E80] font-mono">
                    <Clock className="w-3 h-3" />
                    <span>{new Date(ticket.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                </div>

                {/* Product Name & GTIN Identity */}
                <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-1 mb-2.5">
                  <h3 className="text-base font-bold font-serif text-[#1C2B3A]">
                    {ticket.product_name || 'Product Under Regulatory Audit'}
                  </h3>
                  <div className="flex items-center gap-2 text-xs font-mono">
                    <span className="text-[#5E6E80]">GTIN:</span>
                    <span className="text-[#1C2B3A] font-semibold bg-[#FAF8F5] px-2 py-0.5 border border-[#D8D2C6]">
                      {ticket.gtin}
                    </span>
                    {ticket.batch_code && (
                      <span className="text-[#B8862B] bg-[#FAF3E6] px-2 py-0.5 border border-[#DFBF82]">
                        LOT: {ticket.batch_code}
                      </span>
                    )}
                  </div>
                </div>

                {/* Discrepancy Flow Visualizer */}
                <div className="bg-[#FAF8F5] p-3 border border-[#D8D2C6] mb-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="text-center md:text-left">
                      <span className="text-[10px] text-[#5E6E80] uppercase font-semibold block font-sans">Prior Consensus</span>
                      <span
                        className={`inline-block px-2 py-0.5 text-xs font-mono font-bold uppercase mt-0.5 border ${
                          ticket.prior_verdict === 'compliant'
                            ? 'bg-[#EAF4EE] text-[#2F6F4E] border-[#9BC6AE]'
                            : 'bg-[#F9EBE9] text-[#A8342A] border-[#E09891]'
                        }`}
                      >
                        {ticket.prior_verdict} ({(ticket.prior_confidence * 100).toFixed(0)}%)
                      </span>
                      <span className="block text-[10px] text-[#5E6E80] font-mono mt-0.5">
                        Tier: {ticket.prior_calibration_tier || 'dpi_estimated'}
                      </span>
                    </div>

                    <div className="p-1 text-[#1C2B3A] shrink-0">
                      <ArrowRight className="w-4 h-4 text-[#1C2B3A]" />
                    </div>

                    <div className="text-center md:text-left">
                      <span className="text-[10px] text-[#5E6E80] uppercase font-semibold block font-sans">Contradictory Audit</span>
                      <span
                        className={`inline-block px-2 py-0.5 text-xs font-mono font-bold uppercase mt-0.5 border ${
                          ticket.new_verdict === 'compliant'
                            ? 'bg-[#EAF4EE] text-[#2F6F4E] border-[#9BC6AE]'
                            : ticket.new_verdict === 'disputed'
                            ? 'bg-[#FAF3E6] text-[#B8862B] border-[#DFBF82]'
                            : 'bg-[#F9EBE9] text-[#A8342A] border-[#E09891]'
                        }`}
                      >
                        {ticket.new_verdict} ({(ticket.new_confidence * 100).toFixed(0)}%)
                      </span>
                      <span className="block text-[10px] text-[#1C2B3A] font-mono font-semibold mt-0.5">
                        Tier: {ticket.new_calibration_tier}
                      </span>
                    </div>
                  </div>

                  <div className="border-t md:border-t-0 md:border-l border-[#D8D2C6] md:pl-4">
                    <p className="text-xs text-[#1C2B3A] leading-relaxed font-sans">
                      {ticket.discrepancy_reason}
                    </p>
                  </div>
                </div>

                {/* Violations from Trigger Scan */}
                {ticket.trigger_scan_violations && ticket.trigger_scan_violations.length > 0 && (
                  <div className="mb-3 space-y-1">
                    <span className="text-[11px] font-semibold text-[#A8342A] uppercase tracking-wider flex items-center gap-1 font-sans">
                      <AlertOctagon className="w-3.5 h-3.5 text-[#A8342A]" />
                      Documented Violations ({ticket.trigger_scan_violations.length}):
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {ticket.trigger_scan_violations.map((v, idx) => (
                        <div
                          key={idx}
                          className="text-xs px-2 py-1 bg-[#F9EBE9] border border-[#E09891] text-[#A8342A] font-sans"
                        >
                          <strong className="font-mono uppercase">{v.field_name}:</strong> {v.details}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Resolution Note Display */}
                {ticket.resolution_notes && (
                  <div className="mb-3 p-2.5 bg-[#EAF4EE] border border-[#9BC6AE] text-xs text-[#2F6F4E] flex items-start gap-2">
                    <UserCheck className="w-4 h-4 text-[#2F6F4E] shrink-0 mt-0.5" />
                    <div>
                      <strong>Officer Findings:</strong> {ticket.resolution_notes}
                      {ticket.assigned_to && <span className="text-[#5E6E80] block mt-0.5 font-mono">Officer: {ticket.assigned_to}</span>}
                    </div>
                  </div>
                )}

                {/* Inline Resolution Input Prompt */}
                {resolutionInputId === ticket.id && (
                  <div className="mb-3 p-3 bg-[#FAF8F5] border border-[#1C2B3A] space-y-2 text-xs">
                    <p className="font-semibold text-[#1C2B3A] font-serif">Enter Official Regulatory Determination Findings:</p>
                    <textarea
                      value={resolutionNote}
                      onChange={e => setResolutionNote(e.target.value)}
                      placeholder="e.g. Retail sample verified under Rule 7(1). Issued notice to packer for font undersize."
                      className="w-full p-2 bg-white border border-[#C4BCAC] text-xs text-[#1C2B3A] rounded-none focus:outline-none focus:border-[#1C2B3A]"
                      rows={2}
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => {
                          setResolutionInputId(null);
                          setResolutionNote('');
                        }}
                        className="px-3 py-1 bg-white border border-[#D8D2C6] text-[#5E6E80] hover:bg-[#EFECE6] rounded-none"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleStatusChange(ticket.id, 'resolved', resolutionNote)}
                        disabled={updatingId === ticket.id}
                        className="px-3 py-1 bg-[#2F6F4E] text-white hover:bg-[#25583E] font-semibold rounded-none"
                      >
                        Record Resolution
                      </button>
                    </div>
                  </div>
                )}

                {/* Action Bar */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-2.5 border-t border-[#D8D2C6] text-xs">
                  <div>
                    {onSelectScan && (
                      <button
                        onClick={() => onSelectScan(ticket.trigger_scan_id)}
                        className="inline-flex items-center gap-1.5 px-3 py-1 bg-white hover:bg-[#FAF8F5] text-[#1C2B3A] border border-[#D8D2C6] font-medium transition-all rounded-none"
                      >
                        <ExternalLink className="w-3.5 h-3.5 text-[#1C2B3A]" />
                        Audit Trigger Scan #{ticket.trigger_scan_id}
                      </button>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {ticket.status === 'open' && (
                      <button
                        onClick={() => handleStatusChange(ticket.id, 'investigating')}
                        disabled={updatingId === ticket.id}
                        className="px-3 py-1 bg-[#FAF3E6] hover:bg-[#FAF0DC] text-[#B8862B] border border-[#DFBF82] font-semibold transition-all rounded-none disabled:opacity-50"
                      >
                        Assign Investigation
                      </button>
                    )}

                    {ticket.status !== 'resolved' && (
                      <button
                        onClick={() => {
                          setResolutionInputId(ticket.id);
                          setResolutionNote('');
                        }}
                        disabled={updatingId === ticket.id}
                        className="px-3 py-1 bg-[#EAF4EE] hover:bg-[#DDF0E4] text-[#2F6F4E] border border-[#9BC6AE] font-semibold transition-all rounded-none disabled:opacity-50"
                      >
                        Resolve Docket
                      </button>
                    )}

                    {ticket.status !== 'dismissed' && ticket.status !== 'resolved' && (
                      <button
                        onClick={() => handleStatusChange(ticket.id, 'dismissed', 'Dismissed as non-actionable tolerance variance')}
                        disabled={updatingId === ticket.id}
                        className="px-3 py-1 bg-white hover:bg-[#FAF8F5] text-[#5E6E80] border border-[#D8D2C6] transition-all rounded-none disabled:opacity-50"
                      >
                        Dismiss
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
