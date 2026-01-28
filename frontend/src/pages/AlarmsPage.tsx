import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Bell, BellOff, Check, Clock, Filter } from 'lucide-react';
import { fetchActiveAlarms, fetchAlarmSummary, acknowledgeAlarm, shelveAlarm } from '../api/client';
import clsx from 'clsx';

const priorityColors = {
  1: { bg: 'bg-red-500/20', border: 'border-red-500', text: 'text-red-400', label: 'Emergency' },
  2: { bg: 'bg-orange-500/20', border: 'border-orange-500', text: 'text-orange-400', label: 'High' },
  3: { bg: 'bg-yellow-500/20', border: 'border-yellow-500', text: 'text-yellow-400', label: 'Medium' },
  4: { bg: 'bg-blue-500/20', border: 'border-blue-500', text: 'text-blue-400', label: 'Low' },
  5: { bg: 'bg-gray-500/20', border: 'border-gray-500', text: 'text-gray-400', label: 'Diagnostic' },
};

export default function AlarmsPage() {
  const queryClient = useQueryClient();
  const [filterPriority, setFilterPriority] = useState<number | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('active');

  const { data: summary } = useQuery({
    queryKey: ['alarmSummary'],
    queryFn: fetchAlarmSummary,
    refetchInterval: 5000,
  });

  const { data: alarms, isLoading } = useQuery({
    queryKey: ['activeAlarms'],
    queryFn: fetchActiveAlarms,
    refetchInterval: 5000,
  });

  const ackMutation = useMutation({
    mutationFn: ({ alarmId, notes }: { alarmId: string; notes?: string }) =>
      acknowledgeAlarm(alarmId, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activeAlarms'] });
      queryClient.invalidateQueries({ queryKey: ['alarmSummary'] });
    },
  });

  const shelveMutation = useMutation({
    mutationFn: ({ alarmId, duration, reason }: { alarmId: string; duration: number; reason: string }) =>
      shelveAlarm(alarmId, duration, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activeAlarms'] });
    },
  });

  const filteredAlarms = alarms?.filter((alarm: any) => {
    if (filterPriority && alarm.priority !== filterPriority) return false;
    if (filterStatus === 'unacked' && alarm.is_acknowledged) return false;
    return true;
  }) || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Alarm Management</h1>
        <div className="flex items-center space-x-2">
          <Bell className="h-5 w-5 text-gray-400" />
          <span className="text-sm text-gray-400">ISA-18.2 Compliant</span>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <SummaryCard
          title="Total Active"
          value={summary?.total_active || 0}
          color="yellow"
        />
        <SummaryCard
          title="Unacknowledged"
          value={summary?.unacknowledged || 0}
          color="red"
        />
        <SummaryCard
          title="Acknowledged"
          value={summary?.acknowledged_active || 0}
          color="blue"
        />
        <SummaryCard
          title="Shelved"
          value={summary?.shelved || 0}
          color="gray"
        />
        <SummaryCard
          title="Critical"
          value={summary?.by_priority?.[1] || 0}
          color="red"
        />
      </div>

      {/* Filters */}
      <div className="flex items-center space-x-4 bg-gray-800 p-4 rounded-lg border border-gray-700">
        <Filter className="h-5 w-5 text-gray-400" />
        <div className="flex items-center space-x-2">
          <span className="text-sm text-gray-400">Priority:</span>
          <select
            value={filterPriority || ''}
            onChange={(e) => setFilterPriority(e.target.value ? Number(e.target.value) : null)}
            className="bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
          >
            <option value="">All</option>
            <option value="1">Emergency</option>
            <option value="2">High</option>
            <option value="3">Medium</option>
            <option value="4">Low</option>
            <option value="5">Diagnostic</option>
          </select>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-gray-400">Status:</span>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
          >
            <option value="active">All Active</option>
            <option value="unacked">Unacknowledged</option>
          </select>
        </div>
      </div>

      {/* Alarm List */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold">Active Alarms ({filteredAlarms.length})</h2>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-400">Loading alarms...</div>
        ) : filteredAlarms.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <Check className="h-12 w-12 mx-auto mb-4 text-green-500" />
            <p>No active alarms</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-700">
            {filteredAlarms.map((alarm: any) => (
              <AlarmRow
                key={alarm.instance_id}
                alarm={alarm}
                onAcknowledge={(notes) =>
                  ackMutation.mutate({ alarmId: alarm.alarm_id, notes })
                }
                onShelve={(duration, reason) =>
                  shelveMutation.mutate({ alarmId: alarm.alarm_id, duration, reason })
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({
  title,
  value,
  color,
}: {
  title: string;
  value: number;
  color: 'yellow' | 'red' | 'blue' | 'gray' | 'green';
}) {
  const colorClasses = {
    yellow: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
    red: 'bg-red-500/10 border-red-500/30 text-red-400',
    blue: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
    gray: 'bg-gray-500/10 border-gray-500/30 text-gray-400',
    green: 'bg-green-500/10 border-green-500/30 text-green-400',
  };

  return (
    <div className={clsx('p-4 rounded-lg border', colorClasses[color])}>
      <p className="text-sm text-gray-400">{title}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}

function AlarmRow({
  alarm,
  onAcknowledge,
  onShelve,
}: {
  alarm: any;
  onAcknowledge: (notes?: string) => void;
  onShelve: (duration: number, reason: string) => void;
}) {
  const [showActions, setShowActions] = useState(false);
  const priority = priorityColors[alarm.priority as keyof typeof priorityColors] || priorityColors[4];

  return (
    <div
      className={clsx(
        'px-6 py-4 hover:bg-gray-700/50 transition-colors',
        !alarm.is_acknowledged && 'border-l-4',
        !alarm.is_acknowledged && priority.border
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-4">
          <div className={clsx('p-2 rounded-lg', priority.bg)}>
            <AlertTriangle className={clsx('h-5 w-5', priority.text)} />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-medium">{alarm.tag_name}</span>
              <span className={clsx('px-2 py-0.5 text-xs rounded-full', priority.bg, priority.text)}>
                {priority.label}
              </span>
              {alarm.is_acknowledged && (
                <span className="px-2 py-0.5 text-xs rounded-full bg-green-500/20 text-green-400">
                  Acknowledged
                </span>
              )}
            </div>
            <p className="text-sm text-gray-400 mt-1">{alarm.message}</p>
            <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
              <span>Value: {alarm.value?.toFixed(2)}</span>
              <span>Limit: {alarm.limit_value?.toFixed(2)}</span>
              <span className="flex items-center">
                <Clock className="h-3 w-3 mr-1" />
                {new Date(alarm.timestamp).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {!alarm.is_acknowledged && (
            <button
              onClick={() => onAcknowledge()}
              className="px-3 py-1.5 bg-green-600 hover:bg-green-700 rounded text-sm flex items-center space-x-1"
            >
              <Check className="h-4 w-4" />
              <span>Acknowledge</span>
            </button>
          )}
          <button
            onClick={() => setShowActions(!showActions)}
            className="px-3 py-1.5 bg-gray-600 hover:bg-gray-500 rounded text-sm flex items-center space-x-1"
          >
            <BellOff className="h-4 w-4" />
            <span>Shelve</span>
          </button>
        </div>
      </div>

      {showActions && (
        <div className="mt-4 p-4 bg-gray-700/50 rounded-lg">
          <p className="text-sm text-gray-400 mb-3">Shelve this alarm for:</p>
          <div className="flex items-center space-x-2">
            {[15, 30, 60, 120].map((minutes) => (
              <button
                key={minutes}
                onClick={() => {
                  onShelve(minutes, 'Shelved from dashboard');
                  setShowActions(false);
                }}
                className="px-3 py-1.5 bg-gray-600 hover:bg-gray-500 rounded text-sm"
              >
                {minutes} min
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
