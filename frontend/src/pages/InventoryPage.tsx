import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Package,
  Search,
  Filter,
  Plus,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  BarChart3,
  MapPin,
} from 'lucide-react';

interface InventoryItem {
  item_id: string;
  name: string;
  category: string;
  quantity_on_hand: number;
  quantity_available: number;
  quantity_reserved: number;
  reorder_point: number;
  reorder_quantity: number;
  unit_cost: number;
  location: string;
  last_movement: string;
  status: 'in_stock' | 'low_stock' | 'out_of_stock' | 'overstock';
}

const mockInventory: InventoryItem[] = [
  {
    item_id: 'brick_2x4_red',
    name: '2x4 Brick Red',
    category: 'Finished Goods',
    quantity_on_hand: 1250,
    quantity_available: 1100,
    quantity_reserved: 150,
    reorder_point: 500,
    reorder_quantity: 2000,
    unit_cost: 0.15,
    location: 'WH-A-01',
    last_movement: '2026-01-21T10:30:00Z',
    status: 'in_stock',
  },
  {
    item_id: 'brick_2x4_blue',
    name: '2x4 Brick Blue',
    category: 'Finished Goods',
    quantity_on_hand: 380,
    quantity_available: 280,
    quantity_reserved: 100,
    reorder_point: 500,
    reorder_quantity: 2000,
    unit_cost: 0.15,
    location: 'WH-A-02',
    last_movement: '2026-01-21T09:15:00Z',
    status: 'low_stock',
  },
  {
    item_id: 'brick_2x2_yellow',
    name: '2x2 Brick Yellow',
    category: 'Finished Goods',
    quantity_on_hand: 0,
    quantity_available: 0,
    quantity_reserved: 0,
    reorder_point: 300,
    reorder_quantity: 1500,
    unit_cost: 0.08,
    location: 'WH-A-03',
    last_movement: '2026-01-20T16:45:00Z',
    status: 'out_of_stock',
  },
  {
    item_id: 'filament_pla_red',
    name: 'PLA Filament Red 1kg',
    category: 'Raw Materials',
    quantity_on_hand: 45,
    quantity_available: 40,
    quantity_reserved: 5,
    reorder_point: 20,
    reorder_quantity: 50,
    unit_cost: 18.0,
    location: 'WH-B-01',
    last_movement: '2026-01-21T08:00:00Z',
    status: 'in_stock',
  },
  {
    item_id: 'filament_pla_blue',
    name: 'PLA Filament Blue 1kg',
    category: 'Raw Materials',
    quantity_on_hand: 12,
    quantity_available: 12,
    quantity_reserved: 0,
    reorder_point: 20,
    reorder_quantity: 50,
    unit_cost: 18.0,
    location: 'WH-B-02',
    last_movement: '2026-01-20T14:30:00Z',
    status: 'low_stock',
  },
];

function InventoryPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const { data: inventory = mockInventory } = useQuery({
    queryKey: ['inventory'],
    queryFn: async () => {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/api/erp/inventory`
      );
      if (!response.ok) throw new Error('Failed to fetch inventory');
      const data = await response.json();
      return data.items || mockInventory;
    },
    retry: false,
  });

  const filteredInventory = inventory.filter((item: InventoryItem) => {
    const matchesSearch =
      item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.item_id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = categoryFilter === 'all' || item.category === categoryFilter;
    const matchesStatus = statusFilter === 'all' || item.status === statusFilter;
    return matchesSearch && matchesCategory && matchesStatus;
  });

  const categories = [...new Set(inventory.map((i: InventoryItem) => i.category))];

  const stats = {
    totalItems: inventory.length,
    lowStock: inventory.filter((i: InventoryItem) => i.status === 'low_stock').length,
    outOfStock: inventory.filter((i: InventoryItem) => i.status === 'out_of_stock').length,
    totalValue: inventory.reduce(
      (sum: number, i: InventoryItem) => sum + i.quantity_on_hand * i.unit_cost,
      0
    ),
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'in_stock':
        return 'bg-green-900/50 text-green-400';
      case 'low_stock':
        return 'bg-yellow-900/50 text-yellow-400';
      case 'out_of_stock':
        return 'bg-red-900/50 text-red-400';
      case 'overstock':
        return 'bg-blue-900/50 text-blue-400';
      default:
        return 'bg-gray-700 text-gray-400';
    }
  };

  const getStatusLabel = (status: string) => {
    return status.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Inventory Management</h1>
          <p className="text-gray-400">Track stock levels, movements, and reorder points</p>
        </div>
        <button className="px-4 py-2 bg-yellow-500 text-gray-900 rounded-lg font-medium flex items-center gap-2 hover:bg-yellow-400">
          <Plus className="w-5 h-5" />
          Add Item
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <Package className="w-8 h-8 text-blue-400" />
            <span className="text-2xl font-bold text-white">{stats.totalItems}</span>
          </div>
          <p className="text-gray-400 mt-2">Total Items</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <TrendingDown className="w-8 h-8 text-yellow-400" />
            <span className="text-2xl font-bold text-yellow-400">{stats.lowStock}</span>
          </div>
          <p className="text-gray-400 mt-2">Low Stock</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <AlertTriangle className="w-8 h-8 text-red-400" />
            <span className="text-2xl font-bold text-red-400">{stats.outOfStock}</span>
          </div>
          <p className="text-gray-400 mt-2">Out of Stock</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <BarChart3 className="w-8 h-8 text-green-400" />
            <span className="text-2xl font-bold text-white">
              ${stats.totalValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
          </div>
          <p className="text-gray-400 mt-2">Total Value</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-gray-800 rounded-lg p-4">
        <div className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search items..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-yellow-500"
            />
          </div>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-yellow-500"
          >
            <option value="all">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-yellow-500"
          >
            <option value="all">All Status</option>
            <option value="in_stock">In Stock</option>
            <option value="low_stock">Low Stock</option>
            <option value="out_of_stock">Out of Stock</option>
          </select>
        </div>
      </div>

      {/* Inventory Table */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-700">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Item</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Category</th>
              <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">On Hand</th>
              <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">Available</th>
              <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">Reserved</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Location</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Status</th>
              <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {filteredInventory.map((item: InventoryItem) => (
              <tr key={item.item_id} className="hover:bg-gray-700/50">
                <td className="px-4 py-3">
                  <div>
                    <p className="text-white font-medium">{item.name}</p>
                    <p className="text-gray-400 text-sm">{item.item_id}</p>
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-300">{item.category}</td>
                <td className="px-4 py-3 text-right">
                  <span
                    className={
                      item.quantity_on_hand <= item.reorder_point ? 'text-yellow-400' : 'text-white'
                    }
                  >
                    {item.quantity_on_hand.toLocaleString()}
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-white">
                  {item.quantity_available.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right text-gray-400">
                  {item.quantity_reserved.toLocaleString()}
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1 text-gray-300">
                    <MapPin className="w-4 h-4" />
                    {item.location}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(item.status)}`}>
                    {getStatusLabel(item.status)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-white">
                  ${(item.quantity_on_hand * item.unit_cost).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredInventory.length === 0 && (
          <div className="p-8 text-center text-gray-400">
            <Package className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No inventory items found</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default InventoryPage;
