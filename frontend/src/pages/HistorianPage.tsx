import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Database,
  Download,
  Calendar,
  RefreshCw,
  TrendingUp,
  Clock,
  FileSpreadsheet,
  FileJson,
  Plus,
  X,
  Search,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Brush,
  ReferenceLine,
} from 'recharts';
import { fetchTrendData, fetchTags } from '../api/client';
import { format, subHours, subDays, subMinutes } from 'date-fns';
import clsx from 'clsx';

const CHART_COLORS = [
  '#22c55e', // green
  '#3b82f6', // blue
  '#eab308', // yellow
  '#ef4444', // red
  '#8b5cf6', // purple
  '#ec4899', // pink
  '#14b8a6', // teal
  '#f97316', // orange
];

const TIME_RANGES = [
  { label: '5 min', value: '5m', getRange: () => ({ start: subMinutes(new Date(), 5), end: new Date() }) },
  { label: '15 min', value: '15m', getRange: () => ({ start: subMinutes(new Date(), 15), end: new Date() }) },
  { label: '1 hour', value: '1h', getRange: () => ({ start: subHours(new Date(), 1), end: new Date() }) },
  { label: '4 hours', value: '4h', getRange: () => ({ start: subHours(new Date(), 4), end: new Date() }) },
  { label: '8 hours', value: '8h', getRange: () => ({ start: subHours(new Date(), 8), end: new Date() }) },
  { label: '24 hours', value: '24h', getRange: () => ({ start: subHours(new Date(), 24), end: new Date() }) },
  { label: '7 days', value: '7d', getRange: () => ({ start: subDays(new Date(), 7), end: new Date() }) },
  { label: '30 days', value: '30d', getRange: () => ({ start: subDays(new Date(), 30), end: new Date() }) },
];

const AGGREGATIONS = [
  { label: 'Raw', value: 'raw' },
  { label: 'Average', value: 'avg' },
  { label: 'Min', value: 'min' },
  { label: 'Max', value: 'max' },
  { label: 'Sum', value: 'sum' },
];

// Mock trend data for demonstration
function generateMockTrendData(tags: string[], hours: number = 1) {
  const data = [];
  const now = new Date();
  const points = Math.min(hours * 60, 500); // 1 point per minute, max 500

  for (let i = points; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 60000);
    const point: Record<string, any> = {
      time: time.toISOString(),
      timeLabel: format(time, 'HH:mm'),
    };

    tags.forEach((tag, idx) => {
      // Generate realistic-looking data based on tag type
      const baseValue = 100 + idx * 50;
      const noise = Math.sin(i / 10) * 5 + Math.random() * 3;
      point[tag] = baseValue + noise;
    });

    data.push(point);
  }

  return data;
}

interface SelectedTag {
  tag_id: string;
  name: string;
  color: string;
}

export default function HistorianPage() {
  const [selectedTags, setSelectedTags] = useState<SelectedTag[]>([
    { tag_id: 'TEMP_001', name: 'Mold Temperature 1', color: CHART_COLORS[0] },
  ]);
  const [timeRange, setTimeRange] = useState('1h');
  const [aggregation, setAggregation] = useState('avg');
  const [showTagPicker, setShowTagPicker] = useState(false);
  const [tagSearch, setTagSearch] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);

  const range = useMemo(() => {
    const rangeConfig = TIME_RANGES.find(r => r.value === timeRange);
    return rangeConfig ? rangeConfig.getRange() : { start: subHours(new Date(), 1), end: new Date() };
  }, [timeRange]);

  const { data: trendData, isLoading, refetch } = useQuery({
    queryKey: ['trend', selectedTags.map(t => t.tag_id), timeRange, aggregation],
    queryFn: () => fetchTrendData(
      selectedTags.map(t => t.tag_id),
      range.start.toISOString(),
      range.end.toISOString(),
      aggregation
    ),
    refetchInterval: autoRefresh ? 5000 : false,
  });

  // Use mock data if API not available
  const hours = timeRange.includes('h') ? parseInt(timeRange) : timeRange.includes('d') ? parseInt(timeRange) * 24 : 1;
  const chartData = trendData?.data || generateMockTrendData(selectedTags.map(t => t.tag_id), hours);

  // Mock available tags
  const availableTags = [
    { tag_id: 'TEMP_001', name: 'Mold Temperature 1' },
    { tag_id: 'TEMP_002', name: 'Mold Temperature 2' },
    { tag_id: 'TEMP_003', name: 'Barrel Temperature' },
    { tag_id: 'PRESS_001', name: 'Injection Pressure' },
    { tag_id: 'PRESS_002', name: 'Clamping Pressure' },
    { tag_id: 'SPEED_001', name: 'Screw Speed' },
    { tag_id: 'SPEED_002', name: 'Conveyor Speed' },
    { tag_id: 'COUNT_001', name: 'Part Counter' },
  ];

  const filteredTags = availableTags.filter(tag =>
    !selectedTags.find(s => s.tag_id === tag.tag_id) &&
    (tag.name.toLowerCase().includes(tagSearch.toLowerCase()) ||
     tag.tag_id.toLowerCase().includes(tagSearch.toLowerCase()))
  );

  const addTag = (tag: { tag_id: string; name: string }) => {
    if (selectedTags.length >= 8) return;
    const color = CHART_COLORS[selectedTags.length % CHART_COLORS.length];
    setSelectedTags([...selectedTags, { ...tag, color }]);
    setShowTagPicker(false);
    setTagSearch('');
  };

  const removeTag = (tagId: string) => {
    setSelectedTags(selectedTags.filter(t => t.tag_id !== tagId));
  };

  const exportData = (format: 'csv' | 'json') => {
    const filename = `historian_export_${format(new Date(), 'yyyyMMdd_HHmmss')}.${format}`;

    if (format === 'json') {
      const blob = new Blob([JSON.stringify(chartData, null, 2)], { type: 'application/json' });
      downloadBlob(blob, filename);
    } else {
      const headers = ['time', ...selectedTags.map(t => t.tag_id)];
      const rows = chartData.map((point: any) =>
        headers.map(h => point[h] ?? '').join(',')
      );
      const csv = [headers.join(','), ...rows].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      downloadBlob(blob, filename);
    }
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Calculate statistics
  const stats = useMemo(() => {
    if (!chartData || chartData.length === 0) return {};

    const result: Record<string, { min: number; max: number; avg: number; last: number }> = {};

    selectedTags.forEach(tag => {
      const values = chartData.map((p: any) => p[tag.tag_id]).filter((v: any) => typeof v === 'number');
      if (values.length > 0) {
        result[tag.tag_id] = {
          min: Math.min(...values),
          max: Math.max(...values),
          avg: values.reduce((a: number, b: number) => a + b, 0) / values.length,
          last: values[values.length - 1],
        };
      }
    });

    return result;
  }, [chartData, selectedTags]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Historian</h1>
          <p className="text-gray-400 mt-1">Time-series data visualization and export</p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={clsx(
              'flex items-center space-x-2 px-3 py-2 rounded-lg transition-colors',
              autoRefresh ? 'bg-green-600 hover:bg-green-700' : 'bg-gray-700 hover:bg-gray-600'
            )}
          >
            <RefreshCw className={clsx('h-4 w-4', autoRefresh && 'animate-spin')} />
            <span>{autoRefresh ? 'Auto' : 'Manual'}</span>
          </button>
          <button
            onClick={() => refetch()}
            className="flex items-center space-x-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Tag Selection */}
        <div className="lg:col-span-2 bg-gray-800 p-4 rounded-lg border border-gray-700">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-400">Selected Tags ({selectedTags.length}/8)</h3>
            <button
              onClick={() => setShowTagPicker(!showTagPicker)}
              disabled={selectedTags.length >= 8}
              className="flex items-center space-x-1 px-2 py-1 bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-600 rounded text-sm transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>Add Tag</span>
            </button>
          </div>

          {showTagPicker && (
            <div className="mb-3 p-3 bg-gray-700/50 rounded-lg">
              <div className="relative mb-2">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search tags..."
                  value={tagSearch}
                  onChange={(e) => setTagSearch(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-gray-700 border border-gray-600 rounded text-sm focus:outline-none focus:border-yellow-500"
                />
              </div>
              <div className="max-h-32 overflow-y-auto space-y-1">
                {filteredTags.map(tag => (
                  <button
                    key={tag.tag_id}
                    onClick={() => addTag(tag)}
                    className="w-full text-left px-3 py-2 hover:bg-gray-600 rounded text-sm transition-colors"
                  >
                    <span className="font-medium">{tag.name}</span>
                    <span className="text-gray-500 ml-2">{tag.tag_id}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {selectedTags.map(tag => (
              <div
                key={tag.tag_id}
                className="flex items-center space-x-2 px-3 py-1.5 bg-gray-700/50 rounded-full"
              >
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: tag.color }} />
                <span className="text-sm">{tag.name}</span>
                <button
                  onClick={() => removeTag(tag.tag_id)}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Time Range */}
        <div className="bg-gray-800 p-4 rounded-lg border border-gray-700">
          <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center">
            <Calendar className="h-4 w-4 mr-2" />
            Time Range
          </h3>
          <div className="grid grid-cols-4 gap-1">
            {TIME_RANGES.map(range => (
              <button
                key={range.value}
                onClick={() => setTimeRange(range.value)}
                className={clsx(
                  'px-2 py-1.5 text-xs rounded transition-colors',
                  timeRange === range.value
                    ? 'bg-yellow-600 text-white'
                    : 'bg-gray-700 hover:bg-gray-600'
                )}
              >
                {range.label}
              </button>
            ))}
          </div>
        </div>

        {/* Aggregation & Export */}
        <div className="bg-gray-800 p-4 rounded-lg border border-gray-700">
          <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center">
            <TrendingUp className="h-4 w-4 mr-2" />
            Options
          </h3>
          <div className="space-y-3">
            <select
              value={aggregation}
              onChange={(e) => setAggregation(e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-yellow-500"
            >
              {AGGREGATIONS.map(agg => (
                <option key={agg.value} value={agg.value}>{agg.label}</option>
              ))}
            </select>
            <div className="flex space-x-2">
              <button
                onClick={() => exportData('csv')}
                className="flex-1 flex items-center justify-center space-x-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors"
              >
                <FileSpreadsheet className="h-4 w-4" />
                <span>CSV</span>
              </button>
              <button
                onClick={() => exportData('json')}
                className="flex-1 flex items-center justify-center space-x-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors"
              >
                <FileJson className="h-4 w-4" />
                <span>JSON</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
        <h3 className="text-lg font-semibold mb-4">Trend Chart</h3>
        {isLoading ? (
          <div className="h-80 flex items-center justify-center text-gray-400">
            <RefreshCw className="h-8 w-8 animate-spin" />
          </div>
        ) : selectedTags.length === 0 ? (
          <div className="h-80 flex items-center justify-center text-gray-400">
            <div className="text-center">
              <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>Select tags to display trend data</p>
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="timeLabel"
                stroke="#9ca3af"
                tick={{ fontSize: 12 }}
                interval="preserveStartEnd"
              />
              <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1f2937',
                  border: '1px solid #374151',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: '#9ca3af' }}
              />
              <Legend />
              <Brush dataKey="timeLabel" height={30} stroke="#6b7280" fill="#1f2937" />
              {selectedTags.map(tag => (
                <Line
                  key={tag.tag_id}
                  type="monotone"
                  dataKey={tag.tag_id}
                  name={tag.name}
                  stroke={tag.color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Statistics */}
      {selectedTags.length > 0 && Object.keys(stats).length > 0 && (
        <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Statistics</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-700/50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase">Tag</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-400 uppercase">Min</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-400 uppercase">Max</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-400 uppercase">Average</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-400 uppercase">Last</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {selectedTags.map(tag => {
                  const tagStats = stats[tag.tag_id];
                  if (!tagStats) return null;

                  return (
                    <tr key={tag.tag_id}>
                      <td className="px-4 py-3">
                        <div className="flex items-center space-x-2">
                          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: tag.color }} />
                          <span>{tag.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-blue-400">
                        {tagStats.min.toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-red-400">
                        {tagStats.max.toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-yellow-400">
                        {tagStats.avg.toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-green-400">
                        {tagStats.last.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Info */}
      <div className="flex items-center justify-between text-sm text-gray-500">
        <div className="flex items-center">
          <Clock className="h-4 w-4 mr-1" />
          Data points: {chartData?.length || 0}
        </div>
        <div>
          Period: {format(range.start, 'MMM d, HH:mm')} - {format(range.end, 'MMM d, HH:mm')}
        </div>
      </div>
    </div>
  );
}
