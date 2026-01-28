import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
  Cpu,
  Factory,
  TrendingUp,
  Wrench,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { fetchDashboardKPIs, fetchOEEData, fetchAlarmSummary } from '../api/client';
import StatCard from '../components/StatCard';
import clsx from 'clsx';

const COLORS = ['#22c55e', '#eab308', '#ef4444', '#3b82f6'];

export default function Dashboard() {
  const { data: kpis, isLoading: kpisLoading } = useQuery({
    queryKey: ['dashboardKPIs'],
    queryFn: fetchDashboardKPIs,
  });

  const { data: oeeData } = useQuery({
    queryKey: ['oeeData'],
    queryFn: fetchOEEData,
  });

  const { data: alarmSummary } = useQuery({
    queryKey: ['alarmSummary'],
    queryFn: fetchAlarmSummary,
  });

  // Mock data for charts
  const productionTrend = [
    { time: '06:00', actual: 420, target: 500 },
    { time: '08:00', actual: 890, target: 1000 },
    { time: '10:00', actual: 1350, target: 1500 },
    { time: '12:00', actual: 1820, target: 2000 },
    { time: '14:00', actual: 2290, target: 2500 },
    { time: '16:00', actual: 2750, target: 3000 },
  ];

  const alarmsByPriority = [
    { name: 'Critical', value: alarmSummary?.by_priority?.[1] || 0 },
    { name: 'High', value: alarmSummary?.by_priority?.[2] || 0 },
    { name: 'Medium', value: alarmSummary?.by_priority?.[3] || 0 },
    { name: 'Low', value: alarmSummary?.by_priority?.[4] || 0 },
  ];

  const qualityMetrics = [
    { name: 'Good', value: 96.5 },
    { name: 'Rework', value: 2.5 },
    { name: 'Scrap', value: 1.0 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Production Dashboard</h1>
        <div className="text-sm text-gray-400">
          Last updated: {new Date().toLocaleTimeString()}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="OEE"
          value={`${oeeData?.oee || 78.5}%`}
          icon={TrendingUp}
          trend={{ value: 2.3, positive: true }}
          color="yellow"
        />
        <StatCard
          title="Active Alarms"
          value={alarmSummary?.total_active || 0}
          icon={AlertTriangle}
          color={alarmSummary?.total_active > 0 ? 'red' : 'green'}
          subtext={`${alarmSummary?.unacknowledged || 0} unacknowledged`}
        />
        <StatCard
          title="Production Rate"
          value="1,285/hr"
          icon={Factory}
          trend={{ value: 5.1, positive: true }}
          color="blue"
        />
        <StatCard
          title="Quality Rate"
          value="96.6%"
          icon={CheckCircle}
          trend={{ value: 0.8, positive: true }}
          color="green"
        />
      </div>

      {/* OEE Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <OEEGauge
          title="Availability"
          value={oeeData?.availability || 92.3}
          color="#22c55e"
        />
        <OEEGauge
          title="Performance"
          value={oeeData?.performance || 88.7}
          color="#3b82f6"
        />
        <OEEGauge
          title="Quality"
          value={oeeData?.quality || 96.6}
          color="#8b5cf6"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Production Trend */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Production vs Target</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={productionTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="time" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: 'none' }}
              />
              <Line
                type="monotone"
                dataKey="actual"
                stroke="#22c55e"
                strokeWidth={2}
                name="Actual"
              />
              <Line
                type="monotone"
                dataKey="target"
                stroke="#6b7280"
                strokeDasharray="5 5"
                strokeWidth={2}
                name="Target"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Alarm Distribution */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Alarm Distribution</h3>
          <div className="flex items-center justify-center">
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={alarmsByPriority}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {alarmsByPriority.map((entry, index) => (
                    <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#1f2937', border: 'none' }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2">
              {alarmsByPriority.map((item, index) => (
                <div key={item.name} className="flex items-center space-x-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: COLORS[index] }}
                  />
                  <span className="text-sm text-gray-400">{item.name}</span>
                  <span className="font-semibold">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Work Orders & Equipment Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Work Orders */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Active Work Orders</h3>
          <div className="space-y-3">
            {[
              { id: 'WO-2024-001', product: 'BRICK-2x4-RED', progress: 75, status: 'running' },
              { id: 'WO-2024-002', product: 'BRICK-2x4-BLUE', progress: 45, status: 'running' },
              { id: 'WO-2024-003', product: 'BRICK-1x2-YELLOW', progress: 0, status: 'queued' },
            ].map((wo) => (
              <div key={wo.id} className="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg">
                <div>
                  <div className="font-medium">{wo.id}</div>
                  <div className="text-sm text-gray-400">{wo.product}</div>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="w-32 bg-gray-700 rounded-full h-2">
                    <div
                      className={clsx(
                        'h-2 rounded-full',
                        wo.status === 'running' ? 'bg-green-500' : 'bg-gray-500'
                      )}
                      style={{ width: `${wo.progress}%` }}
                    />
                  </div>
                  <span className="text-sm w-12 text-right">{wo.progress}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Equipment Status */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Equipment Status</h3>
          <div className="grid grid-cols-2 gap-3">
            {[
              { name: 'Injection Molder 1', status: 'running', health: 95 },
              { name: 'Injection Molder 2', status: 'running', health: 87 },
              { name: 'Robot Arm 1', status: 'running', health: 92 },
              { name: 'Robot Arm 2', status: 'idle', health: 88 },
              { name: 'Conveyor A', status: 'running', health: 96 },
              { name: 'Quality Station', status: 'running', health: 100 },
            ].map((equip) => (
              <div
                key={equip.name}
                className={clsx(
                  'p-3 rounded-lg border',
                  equip.status === 'running'
                    ? 'border-green-500/30 bg-green-500/10'
                    : 'border-gray-600 bg-gray-700/30'
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{equip.name}</span>
                  <span
                    className={clsx(
                      'w-2 h-2 rounded-full',
                      equip.status === 'running' ? 'bg-green-500' : 'bg-gray-500'
                    )}
                  />
                </div>
                <div className="mt-2 text-xs text-gray-400">
                  Health: {equip.health}%
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function OEEGauge({ title, value, color }: { title: string; value: number; color: string }) {
  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h3 className="text-sm text-gray-400 mb-2">{title}</h3>
      <div className="flex items-end space-x-2">
        <span className="text-4xl font-bold" style={{ color }}>
          {value.toFixed(1)}
        </span>
        <span className="text-xl text-gray-400 pb-1">%</span>
      </div>
      <div className="mt-4 w-full bg-gray-700 rounded-full h-3">
        <div
          className="h-3 rounded-full transition-all duration-500"
          style={{ width: `${value}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}
