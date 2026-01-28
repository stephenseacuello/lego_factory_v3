import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Factory,
  Plus,
  Play,
  Pause,
  CheckCircle,
  Clock,
  Package,
  Filter,
  Search,
  Calendar,
  ArrowRight,
  AlertTriangle,
  TrendingUp,
  MoreVertical,
} from 'lucide-react';
import {
  fetchWorkOrders,
  createWorkOrder,
  startWorkOrder,
  pauseWorkOrder,
  completeWorkOrder,
  cancelWorkOrder,
} from '../api/client';
import { format } from 'date-fns';
import clsx from 'clsx';

interface WorkOrder {
  id: string;
  wo_number: string;
  product_id: string;
  product_name: string;
  quantity_ordered: number;
  quantity_completed: number;
  status: 'queued' | 'running' | 'paused' | 'completed' | 'cancelled';
  priority: number;
  scheduled_start: string;
  actual_start?: string;
  actual_end?: string;
  estimated_completion?: string;
  notes?: string;
}

const mockWorkOrders: WorkOrder[] = [
  {
    id: '1',
    wo_number: 'WO-2024-001',
    product_id: 'BRICK-2x4-RED',
    product_name: '2x4 Brick - Red',
    quantity_ordered: 10000,
    quantity_completed: 7500,
    status: 'running',
    priority: 1,
    scheduled_start: '2024-01-15T06:00:00Z',
    actual_start: '2024-01-15T06:15:00Z',
    estimated_completion: '2024-01-15T14:00:00Z',
  },
  {
    id: '2',
    wo_number: 'WO-2024-002',
    product_id: 'BRICK-2x4-BLUE',
    product_name: '2x4 Brick - Blue',
    quantity_ordered: 8000,
    quantity_completed: 3200,
    status: 'running',
    priority: 2,
    scheduled_start: '2024-01-15T08:00:00Z',
    actual_start: '2024-01-15T08:30:00Z',
    estimated_completion: '2024-01-15T16:00:00Z',
  },
  {
    id: '3',
    wo_number: 'WO-2024-003',
    product_id: 'BRICK-1x2-YELLOW',
    product_name: '1x2 Brick - Yellow',
    quantity_ordered: 15000,
    quantity_completed: 0,
    status: 'queued',
    priority: 3,
    scheduled_start: '2024-01-15T14:00:00Z',
  },
  {
    id: '4',
    wo_number: 'WO-2024-004',
    product_id: 'PLATE-4x4-GREEN',
    product_name: '4x4 Plate - Green',
    quantity_ordered: 5000,
    quantity_completed: 0,
    status: 'queued',
    priority: 2,
    scheduled_start: '2024-01-16T06:00:00Z',
  },
  {
    id: '5',
    wo_number: 'WO-2024-005',
    product_id: 'BRICK-2x4-WHITE',
    product_name: '2x4 Brick - White',
    quantity_ordered: 12000,
    quantity_completed: 12000,
    status: 'completed',
    priority: 1,
    scheduled_start: '2024-01-14T06:00:00Z',
    actual_start: '2024-01-14T06:00:00Z',
    actual_end: '2024-01-14T18:00:00Z',
  },
];

const statusConfig = {
  queued: { color: 'bg-gray-500', text: 'text-gray-400', label: 'Queued', icon: Clock },
  running: { color: 'bg-green-500', text: 'text-green-400', label: 'Running', icon: Play },
  paused: { color: 'bg-yellow-500', text: 'text-yellow-400', label: 'Paused', icon: Pause },
  completed: { color: 'bg-blue-500', text: 'text-blue-400', label: 'Completed', icon: CheckCircle },
  cancelled: { color: 'bg-red-500', text: 'text-red-400', label: 'Cancelled', icon: AlertTriangle },
};

const priorityColors = {
  1: 'bg-red-500/20 text-red-400 border-red-500/50',
  2: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
  3: 'bg-blue-500/20 text-blue-400 border-blue-500/50',
  4: 'bg-gray-500/20 text-gray-400 border-gray-500/50',
};

export default function ProductionPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  const { data: workOrdersData, isLoading } = useQuery({
    queryKey: ['workOrders', statusFilter],
    queryFn: () => fetchWorkOrders({ status: statusFilter !== 'all' ? statusFilter : undefined }),
    refetchInterval: 10000,
  });

  const workOrders = workOrdersData?.work_orders || mockWorkOrders;

  const filteredOrders = workOrders.filter((wo: WorkOrder) => {
    const matchesSearch =
      wo.wo_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      wo.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      wo.product_id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || wo.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Calculate summary stats
  const stats = {
    total: workOrders.length,
    running: workOrders.filter((wo: WorkOrder) => wo.status === 'running').length,
    queued: workOrders.filter((wo: WorkOrder) => wo.status === 'queued').length,
    completed: workOrders.filter((wo: WorkOrder) => wo.status === 'completed').length,
    totalOrdered: workOrders.reduce((sum: number, wo: WorkOrder) => sum + wo.quantity_ordered, 0),
    totalCompleted: workOrders.reduce((sum: number, wo: WorkOrder) => sum + wo.quantity_completed, 0),
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Production Management</h1>
          <p className="text-gray-400 mt-1">Work order management and scheduling</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg transition-colors"
        >
          <Plus className="h-4 w-4" />
          <span>New Work Order</span>
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard
          title="Active Orders"
          value={stats.running}
          icon={Play}
          color="green"
          subtext={`${stats.queued} queued`}
        />
        <SummaryCard
          title="Completed Today"
          value={stats.completed}
          icon={CheckCircle}
          color="blue"
        />
        <SummaryCard
          title="Total Output"
          value={stats.totalCompleted.toLocaleString()}
          icon={Package}
          color="purple"
          subtext="units produced"
        />
        <SummaryCard
          title="Completion Rate"
          value={`${Math.round((stats.totalCompleted / stats.totalOrdered) * 100)}%`}
          icon={TrendingUp}
          color="yellow"
        />
      </div>

      {/* Filters */}
      <div className="flex items-center space-x-4 bg-gray-800 p-4 rounded-lg border border-gray-700">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by WO number, product..."
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
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="paused">Paused</option>
            <option value="completed">Completed</option>
          </select>
        </div>
      </div>

      {/* Work Orders List */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold">Work Orders ({filteredOrders.length})</h2>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-400">Loading work orders...</div>
        ) : filteredOrders.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <Factory className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No work orders found</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-700">
            {filteredOrders.map((wo: WorkOrder) => (
              <WorkOrderRow key={wo.id} workOrder={wo} />
            ))}
          </div>
        )}
      </div>

      {/* Production Schedule (Gantt-like view) */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4">Production Schedule</h3>
        <div className="space-y-3">
          {filteredOrders
            .filter((wo: WorkOrder) => wo.status !== 'completed')
            .slice(0, 5)
            .map((wo: WorkOrder) => {
              const progress = (wo.quantity_completed / wo.quantity_ordered) * 100;
              const config = statusConfig[wo.status];

              return (
                <div key={wo.id} className="flex items-center space-x-4">
                  <div className="w-32 truncate text-sm">{wo.wo_number}</div>
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-sm text-gray-400">{wo.product_name}</span>
                      <span className={clsx('text-xs px-2 py-0.5 rounded-full', config.color)}>
                        {config.label}
                      </span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-4 relative overflow-hidden">
                      <div
                        className={clsx('h-4 rounded-full transition-all', config.color)}
                        style={{ width: `${progress}%` }}
                      />
                      <span className="absolute inset-0 flex items-center justify-center text-xs font-medium">
                        {wo.quantity_completed.toLocaleString()} / {wo.quantity_ordered.toLocaleString()}
                      </span>
                    </div>
                  </div>
                  <div className="w-32 text-right text-sm text-gray-400">
                    {wo.estimated_completion
                      ? format(new Date(wo.estimated_completion), 'HH:mm')
                      : '--:--'}
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateWorkOrderModal onClose={() => setShowCreateModal(false)} />
      )}
    </div>
  );
}

function WorkOrderRow({ workOrder: wo }: { workOrder: WorkOrder }) {
  const queryClient = useQueryClient();
  const [showMenu, setShowMenu] = useState(false);
  const config = statusConfig[wo.status];
  const StatusIcon = config.icon;
  const progress = (wo.quantity_completed / wo.quantity_ordered) * 100;

  const startMutation = useMutation({
    mutationFn: () => startWorkOrder(wo.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workOrders'] });
      setShowMenu(false);
    },
    onError: (error) => {
      console.error('Failed to start work order:', error);
      alert('Failed to start work order. Please try again.');
    },
  });

  const pauseMutation = useMutation({
    mutationFn: () => pauseWorkOrder(wo.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workOrders'] });
      setShowMenu(false);
    },
    onError: (error) => {
      console.error('Failed to pause work order:', error);
      alert('Failed to pause work order. Please try again.');
    },
  });

  const completeMutation = useMutation({
    mutationFn: () => completeWorkOrder(wo.id, wo.quantity_ordered),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workOrders'] });
      setShowMenu(false);
    },
    onError: (error) => {
      console.error('Failed to complete work order:', error);
      alert('Failed to complete work order. Please try again.');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelWorkOrder(wo.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workOrders'] });
      setShowMenu(false);
    },
    onError: (error) => {
      console.error('Failed to cancel work order:', error);
      alert('Failed to cancel work order. Please try again.');
    },
  });

  const isLoading = startMutation.isPending || pauseMutation.isPending ||
                    completeMutation.isPending || cancelMutation.isPending;

  return (
    <div className="px-6 py-4 hover:bg-gray-700/30 transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className={clsx('p-2 rounded-lg', `${config.color}/20`)}>
            <StatusIcon className={clsx('h-5 w-5', config.text)} />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-medium">{wo.wo_number}</span>
              <span className={clsx(
                'px-2 py-0.5 text-xs rounded border',
                priorityColors[wo.priority as keyof typeof priorityColors]
              )}>
                P{wo.priority}
              </span>
            </div>
            <div className="text-sm text-gray-400">{wo.product_name}</div>
            <div className="text-xs text-gray-500">{wo.product_id}</div>
          </div>
        </div>

        <div className="flex items-center space-x-8">
          {/* Progress */}
          <div className="w-48">
            <div className="flex justify-between text-xs text-gray-400 mb-1">
              <span>Progress</span>
              <span>{progress.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div
                className={clsx('h-2 rounded-full transition-all', config.color)}
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {wo.quantity_completed.toLocaleString()} / {wo.quantity_ordered.toLocaleString()}
            </div>
          </div>

          {/* Schedule */}
          <div className="text-right">
            <div className="flex items-center text-sm text-gray-400">
              <Calendar className="h-4 w-4 mr-1" />
              {format(new Date(wo.scheduled_start), 'MMM d, HH:mm')}
            </div>
            {wo.estimated_completion && wo.status === 'running' && (
              <div className="flex items-center text-xs text-gray-500 mt-1">
                <ArrowRight className="h-3 w-3 mr-1" />
                Est. {format(new Date(wo.estimated_completion), 'HH:mm')}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-2 hover:bg-gray-600 rounded transition-colors"
            >
              <MoreVertical className="h-5 w-5 text-gray-400" />
            </button>
            {showMenu && (
              <div className="absolute right-0 mt-2 w-48 bg-gray-700 rounded-lg shadow-lg border border-gray-600 py-1 z-10">
                {(wo.status === 'queued' || wo.status === 'paused') && (
                  <button
                    onClick={() => startMutation.mutate()}
                    disabled={isLoading}
                    className="w-full px-4 py-2 text-left text-sm hover:bg-gray-600 flex items-center disabled:opacity-50"
                  >
                    <Play className="h-4 w-4 mr-2" />
                    {wo.status === 'paused' ? 'Resume' : 'Start'}
                  </button>
                )}
                {wo.status === 'running' && (
                  <button
                    onClick={() => pauseMutation.mutate()}
                    disabled={isLoading}
                    className="w-full px-4 py-2 text-left text-sm hover:bg-gray-600 flex items-center disabled:opacity-50"
                  >
                    <Pause className="h-4 w-4 mr-2" />
                    Pause
                  </button>
                )}
                {(wo.status === 'running' || wo.status === 'paused') && (
                  <button
                    onClick={() => completeMutation.mutate()}
                    disabled={isLoading}
                    className="w-full px-4 py-2 text-left text-sm hover:bg-gray-600 flex items-center disabled:opacity-50"
                  >
                    <CheckCircle className="h-4 w-4 mr-2" />
                    Complete
                  </button>
                )}
                {wo.status !== 'completed' && wo.status !== 'cancelled' && (
                  <>
                    <hr className="border-gray-600 my-1" />
                    <button
                      onClick={() => {
                        if (confirm('Are you sure you want to cancel this work order?')) {
                          cancelMutation.mutate();
                        }
                      }}
                      disabled={isLoading}
                      className="w-full px-4 py-2 text-left text-sm hover:bg-gray-600 text-red-400 flex items-center disabled:opacity-50"
                    >
                      <AlertTriangle className="h-4 w-4 mr-2" />
                      Cancel
                    </button>
                  </>
                )}
                {isLoading && (
                  <div className="px-4 py-2 text-sm text-gray-400">Processing...</div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({
  title,
  value,
  icon: Icon,
  color,
  subtext,
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  color: 'green' | 'blue' | 'purple' | 'yellow';
  subtext?: string;
}) {
  const colorClasses = {
    green: 'bg-green-500/10 border-green-500/30 text-green-400',
    blue: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
    purple: 'bg-purple-500/10 border-purple-500/30 text-purple-400',
    yellow: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
  };

  return (
    <div className={clsx('p-4 rounded-lg border', colorClasses[color])}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {subtext && <p className="text-xs text-gray-500 mt-1">{subtext}</p>}
        </div>
        <Icon className="h-8 w-8 opacity-50" />
      </div>
    </div>
  );
}

interface FormErrors {
  product_id?: string;
  quantity?: string;
  scheduled_start?: string;
}

function CreateWorkOrderModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    product_id: '',
    quantity: 1000,
    priority: 2,
    scheduled_start: '',
    notes: '',
  });
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const validateForm = (): boolean => {
    const errors: FormErrors = {};

    if (!formData.product_id) {
      errors.product_id = 'Please select a product';
    }

    if (!formData.quantity || formData.quantity < 1) {
      errors.quantity = 'Quantity must be at least 1';
    } else if (formData.quantity > 100000) {
      errors.quantity = 'Quantity cannot exceed 100,000';
    }

    if (formData.scheduled_start) {
      const scheduledDate = new Date(formData.scheduled_start);
      const now = new Date();
      if (scheduledDate < now) {
        errors.scheduled_start = 'Scheduled start must be in the future';
      }
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleBlur = (field: string) => {
    setTouched({ ...touched, [field]: true });
    validateForm();
  };

  const mutation = useMutation({
    mutationFn: createWorkOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workOrders'] });
      onClose();
    },
    onError: (error) => {
      console.error('Failed to create work order:', error);
      alert('Failed to create work order. Please try again.');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({ product_id: true, quantity: true, scheduled_start: true });

    if (!validateForm()) {
      return;
    }

    mutation.mutate(formData);
  };

  const products = [
    { id: 'BRICK-2x4-RED', name: '2x4 Brick - Red' },
    { id: 'BRICK-2x4-BLUE', name: '2x4 Brick - Blue' },
    { id: 'BRICK-2x4-YELLOW', name: '2x4 Brick - Yellow' },
    { id: 'BRICK-2x4-GREEN', name: '2x4 Brick - Green' },
    { id: 'BRICK-2x4-WHITE', name: '2x4 Brick - White' },
    { id: 'BRICK-1x2-RED', name: '1x2 Brick - Red' },
    { id: 'PLATE-4x4-GREEN', name: '4x4 Plate - Green' },
  ];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-md p-6">
        <h2 className="text-xl font-bold mb-4">Create Work Order</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Product *</label>
            <select
              value={formData.product_id}
              onChange={(e) => setFormData({ ...formData, product_id: e.target.value })}
              onBlur={() => handleBlur('product_id')}
              className={`w-full bg-gray-700 border rounded-lg px-3 py-2 focus:outline-none focus:border-yellow-500 ${
                touched.product_id && formErrors.product_id ? 'border-red-500' : 'border-gray-600'
              }`}
            >
              <option value="">Select a product...</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            {touched.product_id && formErrors.product_id && (
              <p className="mt-1 text-sm text-red-400">{formErrors.product_id}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Quantity *</label>
            <input
              type="number"
              value={formData.quantity}
              onChange={(e) => setFormData({ ...formData, quantity: parseInt(e.target.value) || 0 })}
              onBlur={() => handleBlur('quantity')}
              className={`w-full bg-gray-700 border rounded-lg px-3 py-2 focus:outline-none focus:border-yellow-500 ${
                touched.quantity && formErrors.quantity ? 'border-red-500' : 'border-gray-600'
              }`}
              min="1"
              max="100000"
            />
            {touched.quantity && formErrors.quantity && (
              <p className="mt-1 text-sm text-red-400">{formErrors.quantity}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Priority</label>
            <select
              value={formData.priority}
              onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 focus:outline-none focus:border-yellow-500"
            >
              <option value="1">P1 - Critical</option>
              <option value="2">P2 - High</option>
              <option value="3">P3 - Normal</option>
              <option value="4">P4 - Low</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Scheduled Start</label>
            <input
              type="datetime-local"
              value={formData.scheduled_start}
              onChange={(e) => setFormData({ ...formData, scheduled_start: e.target.value })}
              onBlur={() => handleBlur('scheduled_start')}
              className={`w-full bg-gray-700 border rounded-lg px-3 py-2 focus:outline-none focus:border-yellow-500 ${
                touched.scheduled_start && formErrors.scheduled_start ? 'border-red-500' : 'border-gray-600'
              }`}
            />
            {touched.scheduled_start && formErrors.scheduled_start && (
              <p className="mt-1 text-sm text-red-400">{formErrors.scheduled_start}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Notes</label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 focus:outline-none focus:border-yellow-500 h-20"
              placeholder="Optional notes..."
            />
          </div>

          <div className="flex space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="flex-1 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {mutation.isPending ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
