import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  FileText,
  Filter,
  Plus,
  Search,
  XCircle,
  ArrowRight,
  Calendar,
  User,
  Tag,
  Link2,
  Eye,
  Edit2,
  Trash2,
  AlertOctagon,
  Shield,
  TrendingUp,
  RefreshCw,
} from 'lucide-react';
import { format, formatDistanceToNow, isPast, addDays } from 'date-fns';
import clsx from 'clsx';

interface NCR {
  id: string;
  ncr_number: string;
  title: string;
  description: string;
  status: 'open' | 'investigating' | 'root_cause' | 'corrective_action' | 'closed';
  severity: 'critical' | 'major' | 'minor';
  category: string;
  product_affected: string;
  lot_number: string;
  quantity_affected: number;
  detected_by: string;
  detected_date: string;
  due_date: string;
  assigned_to: string;
  root_cause?: string;
  linked_capa_id?: string;
  created_at: string;
  updated_at: string;
}

interface CAPA {
  id: string;
  capa_number: string;
  title: string;
  description: string;
  type: 'corrective' | 'preventive';
  status: 'draft' | 'planning' | 'implementing' | 'verifying' | 'closed';
  priority: 'high' | 'medium' | 'low';
  category: string;
  source: string;
  linked_ncr_ids: string[];
  owner: string;
  due_date: string;
  actions: CAPAAction[];
  effectiveness_criteria: string;
  verification_results?: string;
  created_at: string;
  updated_at: string;
}

interface CAPAAction {
  id: string;
  description: string;
  assignee: string;
  due_date: string;
  status: 'pending' | 'in_progress' | 'completed';
  completed_date?: string;
}

// Mock data
const mockNCRs: NCR[] = [
  {
    id: 'ncr-001',
    ncr_number: 'NCR-2024-0042',
    title: 'Dimensional variance on 2x4 brick',
    description: 'Bricks from injection molder #3 are 0.2mm oversized in length dimension',
    status: 'corrective_action',
    severity: 'major',
    category: 'Dimensional',
    product_affected: '2x4 Standard Brick - Red',
    lot_number: 'LOT-2024-1205-A',
    quantity_affected: 5000,
    detected_by: 'Quality Inspector',
    detected_date: '2024-12-05',
    due_date: '2024-12-15',
    assigned_to: 'John Smith',
    root_cause: 'Worn mold cavity causing dimensional drift',
    linked_capa_id: 'capa-001',
    created_at: '2024-12-05T08:30:00Z',
    updated_at: '2024-12-08T14:22:00Z',
  },
  {
    id: 'ncr-002',
    ncr_number: 'NCR-2024-0043',
    title: 'Color inconsistency in yellow batch',
    description: 'Yellow pigment batch showing visible color variation between runs',
    status: 'investigating',
    severity: 'minor',
    category: 'Appearance',
    product_affected: '1x2 Standard Brick - Yellow',
    lot_number: 'LOT-2024-1206-B',
    quantity_affected: 2000,
    detected_by: 'Production Operator',
    detected_date: '2024-12-06',
    due_date: '2024-12-20',
    assigned_to: 'Maria Garcia',
    created_at: '2024-12-06T10:15:00Z',
    updated_at: '2024-12-06T10:15:00Z',
  },
  {
    id: 'ncr-003',
    ncr_number: 'NCR-2024-0044',
    title: 'Clutch power failure on technic pins',
    description: 'Technic pins not achieving specified clutch power - parts falling out of assemblies',
    status: 'open',
    severity: 'critical',
    category: 'Functional',
    product_affected: 'Technic Pin - Black',
    lot_number: 'LOT-2024-1207-C',
    quantity_affected: 10000,
    detected_by: 'Customer Complaint',
    detected_date: '2024-12-07',
    due_date: '2024-12-10',
    assigned_to: 'Robert Chen',
    created_at: '2024-12-07T09:00:00Z',
    updated_at: '2024-12-07T09:00:00Z',
  },
  {
    id: 'ncr-004',
    ncr_number: 'NCR-2024-0041',
    title: 'Surface defects on clear bricks',
    description: 'Visible flow marks and slight haze on transparent brick surfaces',
    status: 'closed',
    severity: 'minor',
    category: 'Appearance',
    product_affected: '2x2 Standard Brick - Clear',
    lot_number: 'LOT-2024-1201-A',
    quantity_affected: 1500,
    detected_by: 'Final Inspection',
    detected_date: '2024-12-01',
    due_date: '2024-12-08',
    assigned_to: 'Sarah Wilson',
    root_cause: 'Injection speed too high causing turbulent flow',
    linked_capa_id: 'capa-002',
    created_at: '2024-12-01T11:30:00Z',
    updated_at: '2024-12-08T16:00:00Z',
  },
];

const mockCAPAs: CAPA[] = [
  {
    id: 'capa-001',
    capa_number: 'CAPA-2024-0018',
    title: 'Mold maintenance program enhancement',
    description: 'Implement predictive maintenance for injection molds to prevent dimensional drift',
    type: 'corrective',
    status: 'implementing',
    priority: 'high',
    category: 'Equipment',
    source: 'NCR Investigation',
    linked_ncr_ids: ['ncr-001'],
    owner: 'John Smith',
    due_date: '2024-12-20',
    actions: [
      { id: 'act-1', description: 'Install wear sensors on critical molds', assignee: 'Mike Brown', due_date: '2024-12-12', status: 'completed', completed_date: '2024-12-11' },
      { id: 'act-2', description: 'Update maintenance schedule based on part count', assignee: 'John Smith', due_date: '2024-12-15', status: 'in_progress' },
      { id: 'act-3', description: 'Train operators on new inspection procedure', assignee: 'Lisa Taylor', due_date: '2024-12-18', status: 'pending' },
    ],
    effectiveness_criteria: 'Zero dimensional NCRs related to mold wear for 30 days after implementation',
    created_at: '2024-12-06T09:00:00Z',
    updated_at: '2024-12-11T14:30:00Z',
  },
  {
    id: 'capa-002',
    capa_number: 'CAPA-2024-0017',
    title: 'Transparent material process optimization',
    description: 'Optimize injection parameters for transparent materials to eliminate flow marks',
    type: 'corrective',
    status: 'closed',
    priority: 'medium',
    category: 'Process',
    source: 'NCR Investigation',
    linked_ncr_ids: ['ncr-004'],
    owner: 'Sarah Wilson',
    due_date: '2024-12-08',
    actions: [
      { id: 'act-4', description: 'Run DOE for injection speed optimization', assignee: 'Sarah Wilson', due_date: '2024-12-04', status: 'completed', completed_date: '2024-12-04' },
      { id: 'act-5', description: 'Update process parameters in MES', assignee: 'David Lee', due_date: '2024-12-05', status: 'completed', completed_date: '2024-12-05' },
      { id: 'act-6', description: 'Verify quality on 3 production runs', assignee: 'Quality Team', due_date: '2024-12-08', status: 'completed', completed_date: '2024-12-08' },
    ],
    effectiveness_criteria: 'No surface defect NCRs on transparent materials for 14 days',
    verification_results: 'Verified effective - 14 days of production with zero defects',
    created_at: '2024-12-02T10:00:00Z',
    updated_at: '2024-12-08T16:30:00Z',
  },
  {
    id: 'capa-003',
    capa_number: 'CAPA-2024-0019',
    title: 'Incoming material inspection enhancement',
    description: 'Add color measurement to incoming pigment inspection procedure',
    type: 'preventive',
    status: 'planning',
    priority: 'medium',
    category: 'Procedure',
    source: 'Trend Analysis',
    linked_ncr_ids: [],
    owner: 'Maria Garcia',
    due_date: '2024-12-30',
    actions: [
      { id: 'act-7', description: 'Procure colorimeter for QC lab', assignee: 'Purchasing', due_date: '2024-12-15', status: 'pending' },
      { id: 'act-8', description: 'Develop color measurement procedure', assignee: 'Maria Garcia', due_date: '2024-12-20', status: 'pending' },
      { id: 'act-9', description: 'Train QC inspectors on new equipment', assignee: 'Maria Garcia', due_date: '2024-12-28', status: 'pending' },
    ],
    effectiveness_criteria: 'Detect color variation before production - measure by rejected incoming batches',
    created_at: '2024-12-08T11:00:00Z',
    updated_at: '2024-12-08T11:00:00Z',
  },
];

const ncrStatusConfig = {
  open: { label: 'Open', color: 'bg-red-500/20 text-red-400 border-red-500/30', icon: AlertOctagon },
  investigating: { label: 'Investigating', color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30', icon: Search },
  root_cause: { label: 'Root Cause', color: 'bg-orange-500/20 text-orange-400 border-orange-500/30', icon: TrendingUp },
  corrective_action: { label: 'Corrective Action', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', icon: Shield },
  closed: { label: 'Closed', color: 'bg-green-500/20 text-green-400 border-green-500/30', icon: CheckCircle },
};

const capaStatusConfig = {
  draft: { label: 'Draft', color: 'bg-gray-500/20 text-gray-400 border-gray-500/30' },
  planning: { label: 'Planning', color: 'bg-purple-500/20 text-purple-400 border-purple-500/30' },
  implementing: { label: 'Implementing', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  verifying: { label: 'Verifying', color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  closed: { label: 'Closed', color: 'bg-green-500/20 text-green-400 border-green-500/30' },
};

const severityConfig = {
  critical: { label: 'Critical', color: 'bg-red-600 text-white' },
  major: { label: 'Major', color: 'bg-orange-500 text-white' },
  minor: { label: 'Minor', color: 'bg-yellow-500 text-black' },
};

const priorityConfig = {
  high: { label: 'High', color: 'text-red-400' },
  medium: { label: 'Medium', color: 'text-yellow-400' },
  low: { label: 'Low', color: 'text-green-400' },
};

export default function QMSPage() {
  const [activeTab, setActiveTab] = useState<'ncr' | 'capa'>('ncr');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedNCR, setSelectedNCR] = useState<NCR | null>(null);
  const [selectedCAPA, setSelectedCAPA] = useState<CAPA | null>(null);

  // Use mock data (in production, these would be API calls)
  const ncrs = mockNCRs;
  const capas = mockCAPAs;

  const filteredNCRs = ncrs.filter((ncr) => {
    const matchesSearch =
      ncr.ncr_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ncr.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ncr.product_affected.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || ncr.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const filteredCAPAs = capas.filter((capa) => {
    const matchesSearch =
      capa.capa_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      capa.title.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || capa.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Statistics
  const openNCRs = ncrs.filter((n) => n.status !== 'closed').length;
  const criticalNCRs = ncrs.filter((n) => n.severity === 'critical' && n.status !== 'closed').length;
  const overdueNCRs = ncrs.filter((n) => n.status !== 'closed' && isPast(new Date(n.due_date))).length;
  const activeCAPAs = capas.filter((c) => c.status !== 'closed').length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Quality Management System</h1>
          <p className="text-gray-400 mt-1">NCR and CAPA management for continuous improvement</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-black font-medium rounded-lg transition-colors"
        >
          <Plus className="h-4 w-4" />
          <span>Create {activeTab === 'ncr' ? 'NCR' : 'CAPA'}</span>
        </button>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Open NCRs"
          value={openNCRs}
          icon={AlertTriangle}
          color="yellow"
        />
        <StatCard
          label="Critical Issues"
          value={criticalNCRs}
          icon={AlertOctagon}
          color="red"
        />
        <StatCard
          label="Overdue Items"
          value={overdueNCRs}
          icon={Clock}
          color="orange"
        />
        <StatCard
          label="Active CAPAs"
          value={activeCAPAs}
          icon={Shield}
          color="blue"
        />
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 bg-gray-800 p-1 rounded-lg w-fit">
        <button
          onClick={() => { setActiveTab('ncr'); setStatusFilter('all'); }}
          className={clsx(
            'px-4 py-2 rounded-md text-sm font-medium transition-colors',
            activeTab === 'ncr'
              ? 'bg-yellow-500 text-black'
              : 'text-gray-400 hover:text-white hover:bg-gray-700'
          )}
        >
          Non-Conformance Reports ({ncrs.length})
        </button>
        <button
          onClick={() => { setActiveTab('capa'); setStatusFilter('all'); }}
          className={clsx(
            'px-4 py-2 rounded-md text-sm font-medium transition-colors',
            activeTab === 'capa'
              ? 'bg-yellow-500 text-black'
              : 'text-gray-400 hover:text-white hover:bg-gray-700'
          )}
        >
          CAPA ({capas.length})
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center space-x-4 bg-gray-800 p-4 rounded-lg border border-gray-700">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder={`Search ${activeTab === 'ncr' ? 'NCRs' : 'CAPAs'}...`}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-yellow-500"
          />
        </div>
        <div className="flex items-center space-x-2">
          <Filter className="h-4 w-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 focus:outline-none focus:border-yellow-500"
          >
            <option value="all">All Status</option>
            {activeTab === 'ncr' ? (
              <>
                <option value="open">Open</option>
                <option value="investigating">Investigating</option>
                <option value="root_cause">Root Cause</option>
                <option value="corrective_action">Corrective Action</option>
                <option value="closed">Closed</option>
              </>
            ) : (
              <>
                <option value="draft">Draft</option>
                <option value="planning">Planning</option>
                <option value="implementing">Implementing</option>
                <option value="verifying">Verifying</option>
                <option value="closed">Closed</option>
              </>
            )}
          </select>
        </div>
      </div>

      {/* Content */}
      {activeTab === 'ncr' ? (
        <NCRList
          ncrs={filteredNCRs}
          onSelect={setSelectedNCR}
          capas={capas}
        />
      ) : (
        <CAPAList
          capas={filteredCAPAs}
          onSelect={setSelectedCAPA}
        />
      )}

      {/* NCR Detail Modal */}
      {selectedNCR && (
        <NCRDetailModal
          ncr={selectedNCR}
          capa={capas.find((c) => c.id === selectedNCR.linked_capa_id)}
          onClose={() => setSelectedNCR(null)}
        />
      )}

      {/* CAPA Detail Modal */}
      {selectedCAPA && (
        <CAPADetailModal
          capa={selectedCAPA}
          ncrs={ncrs.filter((n) => selectedCAPA.linked_ncr_ids.includes(n.id))}
          onClose={() => setSelectedCAPA(null)}
        />
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  color: 'yellow' | 'red' | 'orange' | 'blue';
}) {
  const colorClasses = {
    yellow: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
    red: 'bg-red-500/10 border-red-500/30 text-red-400',
    orange: 'bg-orange-500/10 border-orange-500/30 text-orange-400',
    blue: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
  };

  return (
    <div className={clsx('p-4 rounded-lg border', colorClasses[color])}>
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">{label}</p>
        <Icon className="h-5 w-5" />
      </div>
      <p className="text-2xl font-bold mt-2">{value}</p>
    </div>
  );
}

function NCRList({
  ncrs,
  onSelect,
  capas,
}: {
  ncrs: NCR[];
  onSelect: (ncr: NCR) => void;
  capas: CAPA[];
}) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-700/50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                NCR
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Severity
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Product / Lot
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Due Date
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Assigned
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {ncrs.map((ncr) => {
              const statusConf = ncrStatusConfig[ncr.status];
              const severityConf = severityConfig[ncr.severity];
              const StatusIcon = statusConf.icon;
              const isOverdue = ncr.status !== 'closed' && isPast(new Date(ncr.due_date));
              const linkedCAPA = capas.find((c) => c.id === ncr.linked_capa_id);

              return (
                <tr key={ncr.id} className="hover:bg-gray-700/30 transition-colors">
                  <td className="px-6 py-4">
                    <div>
                      <div className="font-medium text-yellow-400">{ncr.ncr_number}</div>
                      <div className="text-sm text-gray-300">{ncr.title}</div>
                      <div className="text-xs text-gray-500">{ncr.category}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={clsx(
                      'inline-flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium border',
                      statusConf.color
                    )}>
                      <StatusIcon className="h-3 w-3" />
                      <span>{statusConf.label}</span>
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={clsx(
                      'px-2 py-1 rounded text-xs font-bold',
                      severityConf.color
                    )}>
                      {severityConf.label}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm">{ncr.product_affected}</div>
                    <div className="text-xs text-gray-500">{ncr.lot_number}</div>
                    <div className="text-xs text-gray-500">{ncr.quantity_affected.toLocaleString()} pcs</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className={clsx(
                      'flex items-center space-x-1 text-sm',
                      isOverdue ? 'text-red-400' : 'text-gray-300'
                    )}>
                      <Calendar className="h-4 w-4" />
                      <span>{format(new Date(ncr.due_date), 'MMM d, yyyy')}</span>
                    </div>
                    {isOverdue && (
                      <div className="text-xs text-red-400 mt-1">OVERDUE</div>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-2">
                      <User className="h-4 w-4 text-gray-400" />
                      <span className="text-sm">{ncr.assigned_to}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => onSelect(ncr)}
                        className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                        title="View details"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                      {linkedCAPA && (
                        <span className="flex items-center text-xs text-blue-400">
                          <Link2 className="h-3 w-3 mr-1" />
                          CAPA
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {ncrs.length === 0 && (
        <div className="p-8 text-center text-gray-400">
          <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No NCRs found</p>
        </div>
      )}
    </div>
  );
}

function CAPAList({
  capas,
  onSelect,
}: {
  capas: CAPA[];
  onSelect: (capa: CAPA) => void;
}) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-700/50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                CAPA
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Type
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Priority
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Progress
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Due Date
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {capas.map((capa) => {
              const statusConf = capaStatusConfig[capa.status];
              const priorityConf = priorityConfig[capa.priority];
              const isOverdue = capa.status !== 'closed' && isPast(new Date(capa.due_date));
              const completedActions = capa.actions.filter((a) => a.status === 'completed').length;
              const progress = Math.round((completedActions / capa.actions.length) * 100);

              return (
                <tr key={capa.id} className="hover:bg-gray-700/30 transition-colors">
                  <td className="px-6 py-4">
                    <div>
                      <div className="font-medium text-yellow-400">{capa.capa_number}</div>
                      <div className="text-sm text-gray-300">{capa.title}</div>
                      <div className="text-xs text-gray-500">{capa.category} • {capa.source}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={clsx(
                      'px-2 py-1 rounded text-xs font-medium',
                      capa.type === 'corrective'
                        ? 'bg-orange-500/20 text-orange-400'
                        : 'bg-purple-500/20 text-purple-400'
                    )}>
                      {capa.type === 'corrective' ? 'Corrective' : 'Preventive'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={clsx(
                      'px-2 py-1 rounded-full text-xs font-medium border',
                      statusConf.color
                    )}>
                      {statusConf.label}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={clsx('text-sm font-medium', priorityConf.color)}>
                      {priorityConf.label}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="w-24">
                      <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                        <span>{completedActions}/{capa.actions.length} actions</span>
                        <span>{progress}%</span>
                      </div>
                      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-yellow-500 transition-all"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className={clsx(
                      'flex items-center space-x-1 text-sm',
                      isOverdue ? 'text-red-400' : 'text-gray-300'
                    )}>
                      <Calendar className="h-4 w-4" />
                      <span>{format(new Date(capa.due_date), 'MMM d, yyyy')}</span>
                    </div>
                    {isOverdue && (
                      <div className="text-xs text-red-400 mt-1">OVERDUE</div>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => onSelect(capa)}
                      className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                      title="View details"
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {capas.length === 0 && (
        <div className="p-8 text-center text-gray-400">
          <Shield className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No CAPAs found</p>
        </div>
      )}
    </div>
  );
}

function NCRDetailModal({
  ncr,
  capa,
  onClose,
}: {
  ncr: NCR;
  capa?: CAPA;
  onClose: () => void;
}) {
  const statusConf = ncrStatusConfig[ncr.status];
  const severityConf = severityConfig[ncr.severity];
  const StatusIcon = statusConf.icon;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-700">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-yellow-400 font-mono">{ncr.ncr_number}</div>
              <h2 className="text-xl font-bold mt-1">{ncr.title}</h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
            >
              <XCircle className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Status and Severity */}
          <div className="flex items-center space-x-4">
            <span className={clsx(
              'inline-flex items-center space-x-1 px-3 py-1.5 rounded-full text-sm font-medium border',
              statusConf.color
            )}>
              <StatusIcon className="h-4 w-4" />
              <span>{statusConf.label}</span>
            </span>
            <span className={clsx(
              'px-3 py-1.5 rounded text-sm font-bold',
              severityConf.color
            )}>
              {severityConf.label}
            </span>
          </div>

          {/* Description */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-2">Description</h3>
            <p className="text-gray-300">{ncr.description}</p>
          </div>

          {/* Details Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Product Affected</h3>
              <p className="text-gray-300">{ncr.product_affected}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Lot Number</h3>
              <p className="text-gray-300">{ncr.lot_number}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Quantity Affected</h3>
              <p className="text-gray-300">{ncr.quantity_affected.toLocaleString()} pieces</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Category</h3>
              <p className="text-gray-300">{ncr.category}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Detected By</h3>
              <p className="text-gray-300">{ncr.detected_by}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Detected Date</h3>
              <p className="text-gray-300">{format(new Date(ncr.detected_date), 'MMMM d, yyyy')}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Assigned To</h3>
              <p className="text-gray-300">{ncr.assigned_to}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Due Date</h3>
              <p className={clsx(
                ncr.status !== 'closed' && isPast(new Date(ncr.due_date))
                  ? 'text-red-400'
                  : 'text-gray-300'
              )}>
                {format(new Date(ncr.due_date), 'MMMM d, yyyy')}
              </p>
            </div>
          </div>

          {/* Root Cause */}
          {ncr.root_cause && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Root Cause</h3>
              <p className="text-gray-300 bg-gray-700/50 p-3 rounded-lg">{ncr.root_cause}</p>
            </div>
          )}

          {/* Linked CAPA */}
          {capa && (
            <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
              <div className="flex items-center space-x-2 text-blue-400 mb-2">
                <Link2 className="h-4 w-4" />
                <span className="font-medium">Linked CAPA</span>
              </div>
              <div className="text-yellow-400 font-mono">{capa.capa_number}</div>
              <div className="text-gray-300">{capa.title}</div>
              <div className="text-sm text-gray-500 mt-1">
                Status: {capaStatusConfig[capa.status].label}
              </div>
            </div>
          )}

          {/* Timestamps */}
          <div className="text-xs text-gray-500 pt-4 border-t border-gray-700">
            <p>Created: {format(new Date(ncr.created_at), 'MMM d, yyyy HH:mm')}</p>
            <p>Last Updated: {format(new Date(ncr.updated_at), 'MMM d, yyyy HH:mm')}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function CAPADetailModal({
  capa,
  ncrs,
  onClose,
}: {
  capa: CAPA;
  ncrs: NCR[];
  onClose: () => void;
}) {
  const statusConf = capaStatusConfig[capa.status];
  const priorityConf = priorityConfig[capa.priority];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-700">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-yellow-400 font-mono">{capa.capa_number}</div>
              <h2 className="text-xl font-bold mt-1">{capa.title}</h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
            >
              <XCircle className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Status and Type */}
          <div className="flex items-center space-x-4">
            <span className={clsx(
              'px-3 py-1.5 rounded-full text-sm font-medium border',
              statusConf.color
            )}>
              {statusConf.label}
            </span>
            <span className={clsx(
              'px-3 py-1.5 rounded text-sm font-medium',
              capa.type === 'corrective'
                ? 'bg-orange-500/20 text-orange-400'
                : 'bg-purple-500/20 text-purple-400'
            )}>
              {capa.type === 'corrective' ? 'Corrective Action' : 'Preventive Action'}
            </span>
            <span className={clsx('text-sm font-medium', priorityConf.color)}>
              Priority: {priorityConf.label}
            </span>
          </div>

          {/* Description */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-2">Description</h3>
            <p className="text-gray-300">{capa.description}</p>
          </div>

          {/* Details */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Category</h3>
              <p className="text-gray-300">{capa.category}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Source</h3>
              <p className="text-gray-300">{capa.source}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Owner</h3>
              <p className="text-gray-300">{capa.owner}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">Due Date</h3>
              <p className={clsx(
                capa.status !== 'closed' && isPast(new Date(capa.due_date))
                  ? 'text-red-400'
                  : 'text-gray-300'
              )}>
                {format(new Date(capa.due_date), 'MMMM d, yyyy')}
              </p>
            </div>
          </div>

          {/* Actions */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-3">Action Items</h3>
            <div className="space-y-2">
              {capa.actions.map((action) => (
                <div
                  key={action.id}
                  className={clsx(
                    'p-3 rounded-lg border',
                    action.status === 'completed'
                      ? 'bg-green-500/10 border-green-500/30'
                      : action.status === 'in_progress'
                      ? 'bg-blue-500/10 border-blue-500/30'
                      : 'bg-gray-700/50 border-gray-600'
                  )}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-3">
                      {action.status === 'completed' ? (
                        <CheckCircle className="h-5 w-5 text-green-400 mt-0.5" />
                      ) : action.status === 'in_progress' ? (
                        <RefreshCw className="h-5 w-5 text-blue-400 mt-0.5" />
                      ) : (
                        <Clock className="h-5 w-5 text-gray-400 mt-0.5" />
                      )}
                      <div>
                        <p className="text-gray-300">{action.description}</p>
                        <p className="text-sm text-gray-500 mt-1">
                          Assignee: {action.assignee}
                        </p>
                      </div>
                    </div>
                    <div className="text-right text-sm">
                      <p className="text-gray-400">
                        Due: {format(new Date(action.due_date), 'MMM d')}
                      </p>
                      {action.completed_date && (
                        <p className="text-green-400">
                          Done: {format(new Date(action.completed_date), 'MMM d')}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Effectiveness Criteria */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-2">Effectiveness Criteria</h3>
            <p className="text-gray-300 bg-gray-700/50 p-3 rounded-lg">{capa.effectiveness_criteria}</p>
          </div>

          {/* Verification Results */}
          {capa.verification_results && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Verification Results</h3>
              <p className="text-green-400 bg-green-500/10 p-3 rounded-lg border border-green-500/30">
                {capa.verification_results}
              </p>
            </div>
          )}

          {/* Linked NCRs */}
          {ncrs.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Linked NCRs</h3>
              <div className="space-y-2">
                {ncrs.map((ncr) => (
                  <div
                    key={ncr.id}
                    className="flex items-center space-x-3 p-3 bg-gray-700/50 rounded-lg"
                  >
                    <Link2 className="h-4 w-4 text-yellow-400" />
                    <div>
                      <span className="text-yellow-400 font-mono">{ncr.ncr_number}</span>
                      <span className="mx-2 text-gray-500">-</span>
                      <span className="text-gray-300">{ncr.title}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Timestamps */}
          <div className="text-xs text-gray-500 pt-4 border-t border-gray-700">
            <p>Created: {format(new Date(capa.created_at), 'MMM d, yyyy HH:mm')}</p>
            <p>Last Updated: {format(new Date(capa.updated_at), 'MMM d, yyyy HH:mm')}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
