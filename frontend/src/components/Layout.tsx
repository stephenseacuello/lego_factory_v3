import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  LayoutDashboard,
  Activity,
  Database,
  Bell,
  Factory,
  ClipboardCheck,
  Bot,
  BarChart3,
  Settings,
  AlertTriangle,
  Wifi,
  WifiOff,
  Package,
  LogOut,
} from 'lucide-react';
import { fetchHealth, fetchAlarmSummary } from '../api/client';
import clsx from 'clsx';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'SCADA', href: '/scada', icon: Activity },
  { name: 'Historian', href: '/historian', icon: Database },
  { name: 'Alarms', href: '/alarms', icon: Bell },
  { name: 'Production', href: '/production', icon: Factory },
  { name: 'Inventory', href: '/inventory', icon: Package },
  { name: 'QMS', href: '/qms', icon: ClipboardCheck },
  { name: 'Robotics', href: '/robotics', icon: Bot },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
];

interface LayoutProps {
  onLogout?: () => void;
}

export default function Layout({ onLogout }: LayoutProps) {
  const location = useLocation();

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 5000,
  });

  const { data: alarmSummary } = useQuery({
    queryKey: ['alarmSummary'],
    queryFn: fetchAlarmSummary,
    refetchInterval: 5000,
  });

  const isHealthy = health?.status === 'healthy';
  const activeAlarms = alarmSummary?.total_active || 0;
  const criticalAlarms = alarmSummary?.by_priority?.[1] || 0;

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <Factory className="h-8 w-8 text-yellow-500" />
              <span className="text-xl font-bold">LEGO Factory v3</span>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Connection Status */}
            <div className={clsx(
              'flex items-center space-x-2 px-3 py-1 rounded-full text-sm',
              isHealthy ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'
            )}>
              {isHealthy ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
              <span>{isHealthy ? 'Connected' : 'Disconnected'}</span>
            </div>

            {/* Alarm Badge */}
            {activeAlarms > 0 && (
              <Link
                to="/alarms"
                className={clsx(
                  'flex items-center space-x-2 px-3 py-1 rounded-full text-sm',
                  criticalAlarms > 0 ? 'bg-red-900/50 text-red-400' : 'bg-yellow-900/50 text-yellow-400'
                )}
              >
                <AlertTriangle className="h-4 w-4" />
                <span>{activeAlarms} Active Alarm{activeAlarms !== 1 ? 's' : ''}</span>
              </Link>
            )}

            {/* Time */}
            <div className="text-sm text-gray-400">
              {new Date().toLocaleString()}
            </div>

            {/* Logout Button */}
            {onLogout && (
              <button
                onClick={onLogout}
                className="flex items-center space-x-2 px-3 py-1 rounded-lg text-sm text-gray-400 hover:bg-gray-700 hover:text-white transition-colors"
              >
                <LogOut className="h-4 w-4" />
                <span>Logout</span>
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <nav className="w-64 bg-gray-800 min-h-screen border-r border-gray-700">
          <ul className="py-4 space-y-1">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href;
              return (
                <li key={item.name}>
                  <Link
                    to={item.href}
                    className={clsx(
                      'flex items-center space-x-3 px-4 py-3 mx-2 rounded-lg transition-colors',
                      isActive
                        ? 'bg-yellow-500/20 text-yellow-400'
                        : 'text-gray-400 hover:bg-gray-700 hover:text-white'
                    )}
                  >
                    <item.icon className="h-5 w-5" />
                    <span>{item.name}</span>
                    {item.name === 'Alarms' && activeAlarms > 0 && (
                      <span className={clsx(
                        'ml-auto px-2 py-0.5 text-xs rounded-full',
                        criticalAlarms > 0 ? 'bg-red-500' : 'bg-yellow-500'
                      )}>
                        {activeAlarms}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Main Content */}
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
