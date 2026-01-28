import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  Search,
  Filter,
  RefreshCw,
  Edit2,
  Check,
  X,
  Thermometer,
  Gauge,
  Zap,
  ToggleLeft,
  ToggleRight,
  Clock,
  AlertCircle,
} from 'lucide-react';
import { fetchTags, fetchTagValue, writeTagValue } from '../api/client';
import clsx from 'clsx';

interface Tag {
  tag_id: string;
  name: string;
  description: string;
  data_type: string;
  engineering_units: string;
  category: string;
  value?: number | string | boolean;
  quality?: number;
  timestamp?: string;
}

// Mock tags for demonstration
const mockTags: Tag[] = [
  { tag_id: 'TEMP_001', name: 'Mold Temperature 1', description: 'Injection mold cavity temperature', data_type: 'float', engineering_units: '°C', category: 'temperature', value: 185.5, quality: 192 },
  { tag_id: 'TEMP_002', name: 'Mold Temperature 2', description: 'Injection mold core temperature', data_type: 'float', engineering_units: '°C', category: 'temperature', value: 182.3, quality: 192 },
  { tag_id: 'TEMP_003', name: 'Barrel Temperature', description: 'Extruder barrel temperature', data_type: 'float', engineering_units: '°C', category: 'temperature', value: 220.0, quality: 192 },
  { tag_id: 'PRESS_001', name: 'Injection Pressure', description: 'Injection unit pressure', data_type: 'float', engineering_units: 'bar', category: 'pressure', value: 1250.0, quality: 192 },
  { tag_id: 'PRESS_002', name: 'Clamping Pressure', description: 'Mold clamping force', data_type: 'float', engineering_units: 'kN', category: 'pressure', value: 850.0, quality: 192 },
  { tag_id: 'SPEED_001', name: 'Screw Speed', description: 'Extruder screw rotation speed', data_type: 'float', engineering_units: 'RPM', category: 'speed', value: 45.2, quality: 192 },
  { tag_id: 'SPEED_002', name: 'Conveyor Speed', description: 'Output conveyor belt speed', data_type: 'float', engineering_units: 'm/min', category: 'speed', value: 2.5, quality: 192 },
  { tag_id: 'COUNT_001', name: 'Part Counter', description: 'Parts produced this shift', data_type: 'int', engineering_units: 'pcs', category: 'counter', value: 4523, quality: 192 },
  { tag_id: 'BOOL_001', name: 'Machine Running', description: 'Injection molder running status', data_type: 'bool', engineering_units: '', category: 'status', value: true, quality: 192 },
  { tag_id: 'BOOL_002', name: 'Safety Door', description: 'Safety door interlock status', data_type: 'bool', engineering_units: '', category: 'status', value: true, quality: 192 },
  { tag_id: 'BOOL_003', name: 'Cooling Active', description: 'Mold cooling system status', data_type: 'bool', engineering_units: '', category: 'status', value: true, quality: 192 },
  { tag_id: 'SETPT_001', name: 'Temp Setpoint', description: 'Mold temperature setpoint', data_type: 'float', engineering_units: '°C', category: 'setpoint', value: 185.0, quality: 192 },
];

const categoryIcons: Record<string, React.ElementType> = {
  temperature: Thermometer,
  pressure: Gauge,
  speed: Zap,
  counter: Activity,
  status: ToggleLeft,
  setpoint: Edit2,
};

const categoryColors: Record<string, string> = {
  temperature: 'text-red-400',
  pressure: 'text-blue-400',
  speed: 'text-green-400',
  counter: 'text-purple-400',
  status: 'text-yellow-400',
  setpoint: 'text-cyan-400',
};

export default function SCADAPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [editingTag, setEditingTag] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');

  const { data: tagsData, isLoading, refetch } = useQuery({
    queryKey: ['tags', categoryFilter],
    queryFn: () => fetchTags({ category: categoryFilter !== 'all' ? categoryFilter : undefined }),
    refetchInterval: 2000,
  });

  const writeMutation = useMutation({
    mutationFn: ({ tagId, value }: { tagId: string; value: number | string | boolean }) =>
      writeTagValue(tagId, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setEditingTag(null);
    },
  });

  // Use mock data if API not available
  const tags = tagsData?.tags || mockTags;

  const filteredTags = tags.filter((tag: Tag) => {
    const matchesSearch =
      tag.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      tag.tag_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      tag.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = categoryFilter === 'all' || tag.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  const categories = [...new Set(tags.map((t: Tag) => t.category))];

  const handleStartEdit = (tag: Tag) => {
    setEditingTag(tag.tag_id);
    setEditValue(String(tag.value));
  };

  const handleSaveEdit = (tag: Tag) => {
    let value: number | string | boolean = editValue;
    if (tag.data_type === 'float' || tag.data_type === 'int') {
      value = Number(editValue);
    } else if (tag.data_type === 'bool') {
      value = editValue === 'true';
    }
    writeMutation.mutate({ tagId: tag.tag_id, value });
  };

  const handleCancelEdit = () => {
    setEditingTag(null);
    setEditValue('');
  };

  const getQualityStatus = (quality: number) => {
    if (quality >= 192) return { label: 'Good', color: 'text-green-400' };
    if (quality >= 128) return { label: 'Uncertain', color: 'text-yellow-400' };
    return { label: 'Bad', color: 'text-red-400' };
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">SCADA Tag Management</h1>
          <p className="text-gray-400 mt-1">Real-time tag monitoring and control interface</p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center space-x-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center space-x-4 bg-gray-800 p-4 rounded-lg border border-gray-700">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search tags by name, ID, or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-yellow-500"
          />
        </div>
        <div className="flex items-center space-x-2">
          <Filter className="h-4 w-4 text-gray-400" />
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 focus:outline-none focus:border-yellow-500"
          >
            <option value="all">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat.charAt(0).toUpperCase() + cat.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatBox label="Total Tags" value={tags.length} color="blue" />
        <StatBox
          label="Good Quality"
          value={tags.filter((t: Tag) => (t.quality || 0) >= 192).length}
          color="green"
        />
        <StatBox
          label="Boolean Tags"
          value={tags.filter((t: Tag) => t.data_type === 'bool').length}
          color="yellow"
        />
        <StatBox
          label="Analog Tags"
          value={tags.filter((t: Tag) => t.data_type === 'float' || t.data_type === 'int').length}
          color="purple"
        />
      </div>

      {/* Tag Table */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold">
            Tags ({filteredTags.length})
          </h2>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-400">
            <RefreshCw className="h-8 w-8 mx-auto mb-4 animate-spin" />
            <p>Loading tags...</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-700/50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Tag
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Value
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Quality
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Category
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {filteredTags.map((tag: Tag) => {
                  const Icon = categoryIcons[tag.category] || Activity;
                  const iconColor = categoryColors[tag.category] || 'text-gray-400';
                  const quality = getQualityStatus(tag.quality || 0);
                  const isEditing = editingTag === tag.tag_id;

                  return (
                    <tr key={tag.tag_id} className="hover:bg-gray-700/30 transition-colors">
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-3">
                          <div className={clsx('p-2 rounded-lg bg-gray-700/50', iconColor)}>
                            <Icon className="h-4 w-4" />
                          </div>
                          <div>
                            <div className="font-medium">{tag.name}</div>
                            <div className="text-sm text-gray-500">{tag.tag_id}</div>
                            <div className="text-xs text-gray-600">{tag.description}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {isEditing ? (
                          <div className="flex items-center space-x-2">
                            {tag.data_type === 'bool' ? (
                              <select
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                className="bg-gray-700 border border-yellow-500 rounded px-2 py-1 text-sm"
                              >
                                <option value="true">True</option>
                                <option value="false">False</option>
                              </select>
                            ) : (
                              <input
                                type="number"
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                className="w-24 bg-gray-700 border border-yellow-500 rounded px-2 py-1 text-sm"
                                step={tag.data_type === 'float' ? '0.1' : '1'}
                              />
                            )}
                          </div>
                        ) : (
                          <div className="flex items-center space-x-2">
                            {tag.data_type === 'bool' ? (
                              <span className={clsx(
                                'flex items-center space-x-1',
                                tag.value ? 'text-green-400' : 'text-gray-400'
                              )}>
                                {tag.value ? (
                                  <ToggleRight className="h-5 w-5" />
                                ) : (
                                  <ToggleLeft className="h-5 w-5" />
                                )}
                                <span>{tag.value ? 'ON' : 'OFF'}</span>
                              </span>
                            ) : (
                              <span className="font-mono text-lg">
                                {typeof tag.value === 'number' ? tag.value.toFixed(1) : tag.value}
                                <span className="ml-1 text-sm text-gray-500">
                                  {tag.engineering_units}
                                </span>
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span className={clsx('flex items-center space-x-1', quality.color)}>
                          {quality.label === 'Good' ? (
                            <Check className="h-4 w-4" />
                          ) : (
                            <AlertCircle className="h-4 w-4" />
                          )}
                          <span className="text-sm">{quality.label}</span>
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={clsx(
                          'px-2 py-1 text-xs rounded-full',
                          'bg-gray-700/50',
                          iconColor
                        )}>
                          {tag.category}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {isEditing ? (
                          <div className="flex items-center space-x-2">
                            <button
                              onClick={() => handleSaveEdit(tag)}
                              disabled={writeMutation.isPending}
                              className="p-1.5 bg-green-600 hover:bg-green-700 rounded transition-colors"
                            >
                              <Check className="h-4 w-4" />
                            </button>
                            <button
                              onClick={handleCancelEdit}
                              className="p-1.5 bg-gray-600 hover:bg-gray-500 rounded transition-colors"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => handleStartEdit(tag)}
                            className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                            title="Edit value"
                          >
                            <Edit2 className="h-4 w-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Last Update */}
      <div className="flex items-center justify-end text-sm text-gray-500">
        <Clock className="h-4 w-4 mr-1" />
        Last updated: {new Date().toLocaleTimeString()}
      </div>
    </div>
  );
}

function StatBox({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: 'blue' | 'green' | 'yellow' | 'purple';
}) {
  const colorClasses = {
    blue: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
    green: 'bg-green-500/10 border-green-500/30 text-green-400',
    yellow: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
    purple: 'bg-purple-500/10 border-purple-500/30 text-purple-400',
  };

  return (
    <div className={clsx('p-4 rounded-lg border', colorClasses[color])}>
      <p className="text-sm text-gray-400">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}
