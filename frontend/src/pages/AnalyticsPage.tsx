import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
  Area,
} from 'recharts';
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Target,
  Clock,
  Zap,
  CheckCircle,
  AlertTriangle,
  BarChart3,
  PieChart,
  Calendar,
  RefreshCw,
  Download,
  Filter,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';
import { format, subDays, subHours } from 'date-fns';
import clsx from 'clsx';

interface OEEData {
  timestamp: string;
  availability: number;
  performance: number;
  quality: number;
  oee: number;
}

interface SPCDataPoint {
  timestamp: string;
  value: number;
  sample: number;
}

interface DefectData {
  defect_type: string;
  count: number;
  percentage: number;
}

interface KPI {
  id: string;
  name: string;
  value: number;
  unit: string;
  target: number;
  trend: 'up' | 'down' | 'stable';
  trend_value: number;
}

// Generate mock OEE data
const generateOEEData = (days: number): OEEData[] => {
  const data: OEEData[] = [];
  const now = new Date();

  for (let i = days - 1; i >= 0; i--) {
    const date = subDays(now, i);
    const availability = 85 + Math.random() * 12;
    const performance = 80 + Math.random() * 15;
    const quality = 95 + Math.random() * 4.5;
    const oee = (availability * performance * quality) / 10000;

    data.push({
      timestamp: format(date, 'MMM d'),
      availability: Number(availability.toFixed(1)),
      performance: Number(performance.toFixed(1)),
      quality: Number(quality.toFixed(2)),
      oee: Number(oee.toFixed(1)),
    });
  }

  return data;
};

// Generate mock SPC data
const generateSPCData = (points: number): SPCDataPoint[] => {
  const data: SPCDataPoint[] = [];
  const mean = 8.00; // Target dimension in mm
  const sigma = 0.02;

  for (let i = 0; i < points; i++) {
    // Normally distributed random value
    const u1 = Math.random();
    const u2 = Math.random();
    const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    const value = mean + z * sigma;

    data.push({
      timestamp: format(subHours(new Date(), points - i), 'HH:mm'),
      value: Number(value.toFixed(3)),
      sample: i + 1,
    });
  }

  return data;
};

// Mock defect data
const mockDefectData: DefectData[] = [
  { defect_type: 'Dimensional', count: 145, percentage: 32 },
  { defect_type: 'Surface', count: 98, percentage: 22 },
  { defect_type: 'Color', count: 76, percentage: 17 },
  { defect_type: 'Clutch Power', count: 65, percentage: 14 },
  { defect_type: 'Flash', count: 42, percentage: 9 },
  { defect_type: 'Other', count: 27, percentage: 6 },
];

// Mock KPIs
const mockKPIs: KPI[] = [
  { id: 'oee', name: 'Overall OEE', value: 78.5, unit: '%', target: 85, trend: 'up', trend_value: 2.3 },
  { id: 'yield', name: 'First Pass Yield', value: 97.2, unit: '%', target: 98, trend: 'stable', trend_value: 0.1 },
  { id: 'cycle', name: 'Avg Cycle Time', value: 4.2, unit: 's', target: 4.0, trend: 'down', trend_value: -0.3 },
  { id: 'scrap', name: 'Scrap Rate', value: 1.8, unit: '%', target: 2.0, trend: 'down', trend_value: -0.5 },
  { id: 'throughput', name: 'Throughput', value: 12450, unit: 'pcs/hr', target: 15000, trend: 'up', trend_value: 450 },
  { id: 'mtbf', name: 'MTBF', value: 48.5, unit: 'hrs', target: 72, trend: 'up', trend_value: 5.2 },
];

// SPC calculation helpers
const calculateSPCLimits = (data: SPCDataPoint[]) => {
  const values = data.map(d => d.value);
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / values.length;
  const stdDev = Math.sqrt(variance);

  return {
    mean: Number(mean.toFixed(3)),
    ucl: Number((mean + 3 * stdDev).toFixed(3)),
    lcl: Number((mean - 3 * stdDev).toFixed(3)),
    usl: 8.05, // Upper spec limit
    lsl: 7.95, // Lower spec limit
  };
};

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<'7d' | '14d' | '30d'>('7d');
  const [selectedMachine, setSelectedMachine] = useState('all');

  const oeeData = useMemo(() => generateOEEData(timeRange === '7d' ? 7 : timeRange === '14d' ? 14 : 30), [timeRange]);
  const spcData = useMemo(() => generateSPCData(50), []);
  const spcLimits = useMemo(() => calculateSPCLimits(spcData), [spcData]);

  // Calculate cumulative percentage for Pareto
  const paretoData = useMemo(() => {
    let cumulative = 0;
    return mockDefectData.map(d => {
      cumulative += d.percentage;
      return { ...d, cumulative };
    });
  }, []);

  // Current OEE values (latest)
  const currentOEE = oeeData[oeeData.length - 1];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Analytics & SPC</h1>
          <p className="text-gray-400 mt-1">Statistical process control and OEE monitoring</p>
        </div>
        <div className="flex items-center space-x-4">
          <select
            value={selectedMachine}
            onChange={(e) => setSelectedMachine(e.target.value)}
            className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 focus:outline-none focus:border-yellow-500"
          >
            <option value="all">All Machines</option>
            <option value="im-001">Injection Molder 1</option>
            <option value="im-002">Injection Molder 2</option>
            <option value="im-003">Injection Molder 3</option>
          </select>
          <div className="flex space-x-1 bg-gray-800 rounded-lg p-1">
            {(['7d', '14d', '30d'] as const).map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={clsx(
                  'px-3 py-1 rounded text-sm transition-colors',
                  timeRange === range
                    ? 'bg-yellow-500 text-black font-medium'
                    : 'text-gray-400 hover:text-white'
                )}
              >
                {range}
              </button>
            ))}
          </div>
          <button className="flex items-center space-x-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
            <Download className="h-4 w-4" />
            <span>Export</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {mockKPIs.map((kpi) => (
          <KPICard key={kpi.id} kpi={kpi} />
        ))}
      </div>

      {/* OEE Dashboard */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* OEE Gauges */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="font-semibold mb-6">Current OEE</h3>
          <div className="space-y-6">
            <OEEGauge label="OEE" value={currentOEE.oee} target={85} color="yellow" />
            <OEEGauge label="Availability" value={currentOEE.availability} target={90} color="green" />
            <OEEGauge label="Performance" value={currentOEE.performance} target={95} color="blue" />
            <OEEGauge label="Quality" value={currentOEE.quality} target={99} color="purple" />
          </div>
        </div>

        {/* OEE Trend Chart */}
        <div className="lg:col-span-3 bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="font-semibold mb-4">OEE Trend</h3>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={oeeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="timestamp" stroke="#9CA3AF" fontSize={12} />
              <YAxis stroke="#9CA3AF" fontSize={12} domain={[0, 100]} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                labelStyle={{ color: '#F3F4F6' }}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="oee"
                fill="#EAB308"
                fillOpacity={0.2}
                stroke="#EAB308"
                strokeWidth={2}
                name="OEE"
              />
              <Line
                type="monotone"
                dataKey="availability"
                stroke="#22C55E"
                strokeWidth={1.5}
                dot={false}
                name="Availability"
              />
              <Line
                type="monotone"
                dataKey="performance"
                stroke="#3B82F6"
                strokeWidth={1.5}
                dot={false}
                name="Performance"
              />
              <Line
                type="monotone"
                dataKey="quality"
                stroke="#A855F7"
                strokeWidth={1.5}
                dot={false}
                name="Quality"
              />
              <ReferenceLine y={85} stroke="#EAB308" strokeDasharray="5 5" label={{ value: 'Target', fill: '#EAB308', fontSize: 10 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* SPC and Pareto */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SPC Control Chart */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold">SPC Control Chart</h3>
              <p className="text-sm text-gray-400">Brick Length (mm) - X-bar Chart</p>
            </div>
            <div className="text-right text-sm">
              <div className="text-gray-400">Target: 8.000 mm</div>
              <div className="text-gray-400">Cp: 1.67 | Cpk: 1.52</div>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={spcData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="sample" stroke="#9CA3AF" fontSize={12} />
              <YAxis
                stroke="#9CA3AF"
                fontSize={12}
                domain={[spcLimits.lsl - 0.02, spcLimits.usl + 0.02]}
                tickFormatter={(v) => v.toFixed(2)}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                labelStyle={{ color: '#F3F4F6' }}
                formatter={(value: number) => [value.toFixed(3) + ' mm', 'Value']}
              />
              {/* Spec Limits */}
              <ReferenceLine y={spcLimits.usl} stroke="#EF4444" strokeDasharray="5 5" label={{ value: 'USL', fill: '#EF4444', fontSize: 10 }} />
              <ReferenceLine y={spcLimits.lsl} stroke="#EF4444" strokeDasharray="5 5" label={{ value: 'LSL', fill: '#EF4444', fontSize: 10 }} />
              {/* Control Limits */}
              <ReferenceLine y={spcLimits.ucl} stroke="#F59E0B" strokeDasharray="3 3" label={{ value: 'UCL', fill: '#F59E0B', fontSize: 10 }} />
              <ReferenceLine y={spcLimits.lcl} stroke="#F59E0B" strokeDasharray="3 3" label={{ value: 'LCL', fill: '#F59E0B', fontSize: 10 }} />
              {/* Mean */}
              <ReferenceLine y={spcLimits.mean} stroke="#22C55E" label={{ value: 'Mean', fill: '#22C55E', fontSize: 10 }} />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#3B82F6"
                strokeWidth={2}
                dot={{ r: 3, fill: '#3B82F6' }}
              />
            </LineChart>
          </ResponsiveContainer>
          <div className="flex items-center justify-center space-x-6 mt-4 text-sm">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-0.5 bg-red-500" />
              <span className="text-gray-400">Spec Limits</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-0.5 bg-yellow-500" style={{ borderStyle: 'dashed' }} />
              <span className="text-gray-400">Control Limits (3σ)</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-0.5 bg-green-500" />
              <span className="text-gray-400">Mean</span>
            </div>
          </div>
        </div>

        {/* Pareto Chart */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold">Defect Pareto Analysis</h3>
              <p className="text-sm text-gray-400">Last 30 days - All machines</p>
            </div>
            <div className="text-sm text-gray-400">
              Total: {mockDefectData.reduce((a, b) => a + b.count, 0)} defects
            </div>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={paretoData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="defect_type" stroke="#9CA3AF" fontSize={11} angle={-15} textAnchor="end" height={60} />
              <YAxis yAxisId="left" stroke="#9CA3AF" fontSize={12} />
              <YAxis yAxisId="right" orientation="right" stroke="#9CA3AF" fontSize={12} domain={[0, 100]} unit="%" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                labelStyle={{ color: '#F3F4F6' }}
              />
              <Legend />
              <Bar yAxisId="left" dataKey="count" fill="#3B82F6" name="Count" radius={[4, 4, 0, 0]} />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="cumulative"
                stroke="#EAB308"
                strokeWidth={2}
                dot={{ r: 4, fill: '#EAB308' }}
                name="Cumulative %"
              />
              <ReferenceLine yAxisId="right" y={80} stroke="#EF4444" strokeDasharray="5 5" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Loss Analysis */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h3 className="font-semibold mb-4">Loss Analysis - Six Big Losses</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Availability Losses */}
          <div>
            <h4 className="text-sm font-medium text-green-400 mb-3">Availability Losses</h4>
            <div className="space-y-3">
              <LossBar label="Equipment Failure" value={3.2} maxValue={10} color="green" />
              <LossBar label="Setup & Adjustment" value={5.8} maxValue={10} color="green" />
            </div>
          </div>
          {/* Performance Losses */}
          <div>
            <h4 className="text-sm font-medium text-blue-400 mb-3">Performance Losses</h4>
            <div className="space-y-3">
              <LossBar label="Idling & Minor Stops" value={4.5} maxValue={10} color="blue" />
              <LossBar label="Reduced Speed" value={6.2} maxValue={10} color="blue" />
            </div>
          </div>
          {/* Quality Losses */}
          <div>
            <h4 className="text-sm font-medium text-purple-400 mb-3">Quality Losses</h4>
            <div className="space-y-3">
              <LossBar label="Defects & Rework" value={1.8} maxValue={10} color="purple" />
              <LossBar label="Startup Losses" value={0.5} maxValue={10} color="purple" />
            </div>
          </div>
        </div>
      </div>

      {/* Process Capability Summary */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-700">
          <h3 className="font-semibold">Process Capability Summary</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-700/50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Characteristic</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Nominal</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Mean</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Std Dev</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Cp</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Cpk</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {[
                { name: 'Brick Length', nominal: '8.00 mm', mean: '7.998 mm', stdDev: '0.018 mm', cp: 1.85, cpk: 1.72, status: 'capable' },
                { name: 'Brick Width', nominal: '8.00 mm', mean: '8.003 mm', stdDev: '0.015 mm', cp: 2.22, cpk: 2.11, status: 'capable' },
                { name: 'Brick Height', nominal: '9.60 mm', mean: '9.595 mm', stdDev: '0.022 mm', cp: 1.52, cpk: 1.45, status: 'capable' },
                { name: 'Stud Diameter', nominal: '4.85 mm', mean: '4.848 mm', stdDev: '0.012 mm', cp: 1.39, cpk: 1.28, status: 'marginal' },
                { name: 'Clutch Force', nominal: '3.0 N', mean: '2.92 N', stdDev: '0.15 N', cp: 1.11, cpk: 0.95, status: 'warning' },
              ].map((row) => (
                <tr key={row.name} className="hover:bg-gray-700/30">
                  <td className="px-6 py-4 font-medium">{row.name}</td>
                  <td className="px-6 py-4 font-mono text-sm">{row.nominal}</td>
                  <td className="px-6 py-4 font-mono text-sm">{row.mean}</td>
                  <td className="px-6 py-4 font-mono text-sm">{row.stdDev}</td>
                  <td className="px-6 py-4 font-mono text-sm">{row.cp.toFixed(2)}</td>
                  <td className="px-6 py-4">
                    <span className={clsx(
                      'font-mono text-sm font-medium',
                      row.cpk >= 1.33 ? 'text-green-400' : row.cpk >= 1.0 ? 'text-yellow-400' : 'text-red-400'
                    )}>
                      {row.cpk.toFixed(2)}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={clsx(
                      'px-2 py-1 rounded text-xs font-medium',
                      row.status === 'capable' && 'bg-green-500/20 text-green-400',
                      row.status === 'marginal' && 'bg-yellow-500/20 text-yellow-400',
                      row.status === 'warning' && 'bg-red-500/20 text-red-400'
                    )}>
                      {row.status === 'capable' ? 'Capable' : row.status === 'marginal' ? 'Marginal' : 'Needs Attention'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function KPICard({ kpi }: { kpi: KPI }) {
  const isOnTarget = kpi.name === 'Scrap Rate' || kpi.name === 'Avg Cycle Time'
    ? kpi.value <= kpi.target
    : kpi.value >= kpi.target;

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-400">{kpi.name}</span>
        {kpi.trend !== 'stable' && (
          <span className={clsx(
            'flex items-center text-xs',
            kpi.trend === 'up' ? 'text-green-400' : 'text-red-400'
          )}>
            {kpi.trend === 'up' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
            {Math.abs(kpi.trend_value)}
          </span>
        )}
      </div>
      <div className="flex items-baseline space-x-1">
        <span className={clsx(
          'text-2xl font-bold',
          isOnTarget ? 'text-white' : 'text-yellow-400'
        )}>
          {kpi.value.toLocaleString()}
        </span>
        <span className="text-sm text-gray-500">{kpi.unit}</span>
      </div>
      <div className="mt-2 flex items-center space-x-2">
        <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={clsx(
              'h-full rounded-full transition-all',
              isOnTarget ? 'bg-green-500' : 'bg-yellow-500'
            )}
            style={{
              width: `${Math.min(100, (kpi.value / kpi.target) * 100)}%`
            }}
          />
        </div>
        <span className="text-xs text-gray-500">{kpi.target}{kpi.unit}</span>
      </div>
    </div>
  );
}

function OEEGauge({
  label,
  value,
  target,
  color,
}: {
  label: string;
  value: number;
  target: number;
  color: 'yellow' | 'green' | 'blue' | 'purple';
}) {
  const colorClasses = {
    yellow: 'text-yellow-500',
    green: 'text-green-500',
    blue: 'text-blue-500',
    purple: 'text-purple-500',
  };

  const bgClasses = {
    yellow: 'bg-yellow-500',
    green: 'bg-green-500',
    blue: 'bg-blue-500',
    purple: 'bg-purple-500',
  };

  const isOnTarget = value >= target;

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-gray-400">{label}</span>
        <span className={clsx('text-lg font-bold', colorClasses[color])}>
          {value.toFixed(1)}%
        </span>
      </div>
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden relative">
        <div
          className={clsx('h-full rounded-full transition-all', bgClasses[color])}
          style={{ width: `${Math.min(100, value)}%` }}
        />
        <div
          className="absolute top-0 h-full w-0.5 bg-white/50"
          style={{ left: `${target}%` }}
        />
      </div>
      <div className="flex justify-between mt-1 text-xs text-gray-500">
        <span>0%</span>
        <span className={isOnTarget ? 'text-green-400' : 'text-yellow-400'}>
          Target: {target}%
        </span>
        <span>100%</span>
      </div>
    </div>
  );
}

function LossBar({
  label,
  value,
  maxValue,
  color,
}: {
  label: string;
  value: number;
  maxValue: number;
  color: 'green' | 'blue' | 'purple';
}) {
  const colorClasses = {
    green: 'bg-green-500',
    blue: 'bg-blue-500',
    purple: 'bg-purple-500',
  };

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="text-gray-300">{label}</span>
        <span className="text-gray-400">{value.toFixed(1)}%</span>
      </div>
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={clsx('h-full rounded-full transition-all', colorClasses[color])}
          style={{ width: `${(value / maxValue) * 100}%` }}
        />
      </div>
    </div>
  );
}
