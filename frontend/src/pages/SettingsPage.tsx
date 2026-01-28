import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Settings,
  User,
  Users,
  Database,
  Bell,
  Shield,
  Globe,
  Server,
  Mail,
  Clock,
  Save,
  RefreshCw,
  Download,
  Upload,
  Key,
  Trash2,
  Plus,
  Edit2,
  CheckCircle,
  AlertTriangle,
  HardDrive,
  Wifi,
  Lock,
  Eye,
  EyeOff,
  ChevronRight,
} from 'lucide-react';
import clsx from 'clsx';

interface SettingsSection {
  id: string;
  name: string;
  icon: React.ElementType;
  description: string;
}

interface UserAccount {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'operator' | 'viewer';
  status: 'active' | 'inactive';
  last_login: string;
}

interface IntegrationStatus {
  name: string;
  type: string;
  status: 'connected' | 'disconnected' | 'error';
  endpoint: string;
  last_sync?: string;
}

const sections: SettingsSection[] = [
  { id: 'general', name: 'General', icon: Settings, description: 'Basic system configuration' },
  { id: 'users', name: 'Users & Access', icon: Users, description: 'User accounts and permissions' },
  { id: 'integrations', name: 'Integrations', icon: Server, description: 'External system connections' },
  { id: 'notifications', name: 'Notifications', icon: Bell, description: 'Alert and notification settings' },
  { id: 'backup', name: 'Backup & Restore', icon: HardDrive, description: 'Data backup management' },
  { id: 'security', name: 'Security', icon: Shield, description: 'Security and authentication' },
];

const mockUsers: UserAccount[] = [
  { id: 'usr-001', username: 'admin', email: 'admin@legofactory.local', role: 'admin', status: 'active', last_login: '2024-12-08T14:30:00Z' },
  { id: 'usr-002', username: 'jsmith', email: 'jsmith@legofactory.local', role: 'operator', status: 'active', last_login: '2024-12-08T12:15:00Z' },
  { id: 'usr-003', username: 'mgarcia', email: 'mgarcia@legofactory.local', role: 'operator', status: 'active', last_login: '2024-12-08T08:45:00Z' },
  { id: 'usr-004', username: 'rchen', email: 'rchen@legofactory.local', role: 'viewer', status: 'active', last_login: '2024-12-07T16:20:00Z' },
  { id: 'usr-005', username: 'swilson', email: 'swilson@legofactory.local', role: 'viewer', status: 'inactive', last_login: '2024-11-15T10:00:00Z' },
];

const mockIntegrations: IntegrationStatus[] = [
  { name: 'OPC-UA Server', type: 'OPC-UA', status: 'connected', endpoint: 'opc.tcp://192.168.1.100:4840', last_sync: '2024-12-08T14:32:15Z' },
  { name: 'TimescaleDB', type: 'Database', status: 'connected', endpoint: 'postgresql://192.168.1.50:5432/historian', last_sync: '2024-12-08T14:32:00Z' },
  { name: 'ROS2 Bridge', type: 'ROS2', status: 'connected', endpoint: 'ws://192.168.1.75:9090', last_sync: '2024-12-08T14:31:45Z' },
  { name: 'ERP System', type: 'REST API', status: 'connected', endpoint: 'https://erp.legofactory.local/api', last_sync: '2024-12-08T14:00:00Z' },
  { name: 'Email Server', type: 'SMTP', status: 'error', endpoint: 'smtp://mail.legofactory.local:587' },
];

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState('general');
  const [showSaveNotification, setShowSaveNotification] = useState(false);

  const handleSave = () => {
    setShowSaveNotification(true);
    setTimeout(() => setShowSaveNotification(false), 3000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-gray-400 mt-1">System configuration and preferences</p>
        </div>
        {showSaveNotification && (
          <div className="flex items-center space-x-2 px-4 py-2 bg-green-500/20 border border-green-500/30 rounded-lg text-green-400">
            <CheckCircle className="h-4 w-4" />
            <span>Settings saved successfully</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Navigation */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden h-fit">
          <div className="px-4 py-3 border-b border-gray-700">
            <h2 className="font-semibold">Configuration</h2>
          </div>
          <nav className="p-2">
            {sections.map((section) => {
              const Icon = section.icon;
              return (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={clsx(
                    'w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-left transition-colors',
                    activeSection === section.id
                      ? 'bg-yellow-500/20 text-yellow-400'
                      : 'hover:bg-gray-700 text-gray-300'
                  )}
                >
                  <Icon className="h-5 w-5" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium">{section.name}</div>
                    <div className="text-xs text-gray-500 truncate">{section.description}</div>
                  </div>
                  <ChevronRight className={clsx(
                    'h-4 w-4 transition-transform',
                    activeSection === section.id && 'transform rotate-90'
                  )} />
                </button>
              );
            })}
          </nav>
        </div>

        {/* Content */}
        <div className="lg:col-span-3">
          {activeSection === 'general' && <GeneralSettings onSave={handleSave} />}
          {activeSection === 'users' && <UsersSettings users={mockUsers} onSave={handleSave} />}
          {activeSection === 'integrations' && <IntegrationsSettings integrations={mockIntegrations} />}
          {activeSection === 'notifications' && <NotificationsSettings onSave={handleSave} />}
          {activeSection === 'backup' && <BackupSettings />}
          {activeSection === 'security' && <SecuritySettings onSave={handleSave} />}
        </div>
      </div>
    </div>
  );
}

function GeneralSettings({ onSave }: { onSave: () => void }) {
  const [siteName, setSiteName] = useState('LEGO Factory MES');
  const [timezone, setTimezone] = useState('America/New_York');
  const [language, setLanguage] = useState('en-US');
  const [dateFormat, setDateFormat] = useState('MM/dd/yyyy');
  const [refreshInterval, setRefreshInterval] = useState(5);

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700">
      <div className="px-6 py-4 border-b border-gray-700">
        <h2 className="text-lg font-semibold">General Settings</h2>
        <p className="text-sm text-gray-400">Configure basic system options</p>
      </div>
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Site Name</label>
            <input
              type="text"
              value={siteName}
              onChange={(e) => setSiteName(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-yellow-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Timezone</label>
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-yellow-500"
            >
              <option value="America/New_York">Eastern Time (ET)</option>
              <option value="America/Chicago">Central Time (CT)</option>
              <option value="America/Denver">Mountain Time (MT)</option>
              <option value="America/Los_Angeles">Pacific Time (PT)</option>
              <option value="Europe/London">London (GMT)</option>
              <option value="Europe/Berlin">Berlin (CET)</option>
              <option value="Asia/Tokyo">Tokyo (JST)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Language</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-yellow-500"
            >
              <option value="en-US">English (US)</option>
              <option value="en-GB">English (UK)</option>
              <option value="de-DE">German</option>
              <option value="es-ES">Spanish</option>
              <option value="fr-FR">French</option>
              <option value="ja-JP">Japanese</option>
              <option value="zh-CN">Chinese (Simplified)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Date Format</label>
            <select
              value={dateFormat}
              onChange={(e) => setDateFormat(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-yellow-500"
            >
              <option value="MM/dd/yyyy">MM/DD/YYYY</option>
              <option value="dd/MM/yyyy">DD/MM/YYYY</option>
              <option value="yyyy-MM-dd">YYYY-MM-DD</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Dashboard Refresh Interval: {refreshInterval} seconds
          </label>
          <input
            type="range"
            min="1"
            max="30"
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>1s (Real-time)</span>
            <span>30s (Low bandwidth)</span>
          </div>
        </div>

        <div className="flex justify-end pt-4 border-t border-gray-700">
          <button
            onClick={onSave}
            className="flex items-center space-x-2 px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-black font-medium rounded-lg transition-colors"
          >
            <Save className="h-4 w-4" />
            <span>Save Changes</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function UsersSettings({ users, onSave }: { users: UserAccount[]; onSave: () => void }) {
  const roleColors = {
    admin: 'bg-red-500/20 text-red-400 border-red-500/30',
    operator: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    viewer: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  };

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700">
      <div className="px-6 py-4 border-b border-gray-700 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Users & Access Control</h2>
          <p className="text-sm text-gray-400">Manage user accounts and permissions</p>
        </div>
        <button className="flex items-center space-x-2 px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-black font-medium rounded-lg transition-colors">
          <Plus className="h-4 w-4" />
          <span>Add User</span>
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-700/50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">User</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Role</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Last Login</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {users.map((user) => (
              <tr key={user.id} className="hover:bg-gray-700/30">
                <td className="px-6 py-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center">
                      <User className="h-4 w-4 text-gray-400" />
                    </div>
                    <div>
                      <div className="font-medium">{user.username}</div>
                      <div className="text-sm text-gray-500">{user.email}</div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className={clsx(
                    'px-2 py-1 rounded text-xs font-medium border',
                    roleColors[user.role]
                  )}>
                    {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span className={clsx(
                    'flex items-center space-x-1 text-sm',
                    user.status === 'active' ? 'text-green-400' : 'text-gray-500'
                  )}>
                    <span className={clsx(
                      'w-2 h-2 rounded-full',
                      user.status === 'active' ? 'bg-green-400' : 'bg-gray-500'
                    )} />
                    <span>{user.status === 'active' ? 'Active' : 'Inactive'}</span>
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-400">
                  {new Date(user.last_login).toLocaleString()}
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center space-x-2">
                    <button className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded transition-colors" title="Edit">
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded transition-colors" title="Reset Password">
                      <Key className="h-4 w-4" />
                    </button>
                    <button className="p-1.5 bg-gray-700 hover:bg-red-600 rounded transition-colors" title="Delete">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function IntegrationsSettings({ integrations }: { integrations: IntegrationStatus[] }) {
  const statusColors = {
    connected: 'text-green-400',
    disconnected: 'text-gray-400',
    error: 'text-red-400',
  };

  const statusIcons = {
    connected: CheckCircle,
    disconnected: Wifi,
    error: AlertTriangle,
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="px-6 py-4 border-b border-gray-700 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">System Integrations</h2>
            <p className="text-sm text-gray-400">External system connections and APIs</p>
          </div>
          <button className="flex items-center space-x-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
            <Plus className="h-4 w-4" />
            <span>Add Integration</span>
          </button>
        </div>
        <div className="divide-y divide-gray-700">
          {integrations.map((integration, idx) => {
            const StatusIcon = statusIcons[integration.status];
            return (
              <div key={idx} className="p-4 flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className={clsx(
                    'p-2 rounded-lg',
                    integration.status === 'connected' ? 'bg-green-500/20' :
                    integration.status === 'error' ? 'bg-red-500/20' : 'bg-gray-700'
                  )}>
                    <Server className={clsx('h-5 w-5', statusColors[integration.status])} />
                  </div>
                  <div>
                    <div className="font-medium">{integration.name}</div>
                    <div className="text-sm text-gray-500">{integration.type}</div>
                    <div className="text-xs text-gray-600 font-mono mt-1">{integration.endpoint}</div>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="text-right">
                    <div className={clsx('flex items-center space-x-1', statusColors[integration.status])}>
                      <StatusIcon className="h-4 w-4" />
                      <span className="text-sm capitalize">{integration.status}</span>
                    </div>
                    {integration.last_sync && (
                      <div className="text-xs text-gray-500">
                        Last sync: {new Date(integration.last_sync).toLocaleTimeString()}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center space-x-2">
                    <button className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded transition-colors" title="Test Connection">
                      <RefreshCw className="h-4 w-4" />
                    </button>
                    <button className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded transition-colors" title="Configure">
                      <Settings className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function NotificationsSettings({ onSave }: { onSave: () => void }) {
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [emailAddress, setEmailAddress] = useState('alerts@legofactory.local');
  const [alarmNotify, setAlarmNotify] = useState(true);
  const [downtimeNotify, setDowntimeNotify] = useState(true);
  const [qualityNotify, setQualityNotify] = useState(true);
  const [maintenanceNotify, setMaintenanceNotify] = useState(false);

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700">
      <div className="px-6 py-4 border-b border-gray-700">
        <h2 className="text-lg font-semibold">Notification Settings</h2>
        <p className="text-sm text-gray-400">Configure alerts and notifications</p>
      </div>
      <div className="p-6 space-y-6">
        {/* Email Settings */}
        <div>
          <h3 className="font-medium mb-4">Email Notifications</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg">
              <div className="flex items-center space-x-3">
                <Mail className="h-5 w-5 text-gray-400" />
                <div>
                  <div className="font-medium">Email Alerts</div>
                  <div className="text-sm text-gray-500">Send notifications via email</div>
                </div>
              </div>
              <button
                onClick={() => setEmailEnabled(!emailEnabled)}
                className={clsx(
                  'w-12 h-6 rounded-full transition-colors relative',
                  emailEnabled ? 'bg-yellow-500' : 'bg-gray-600'
                )}
              >
                <span className={clsx(
                  'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                  emailEnabled ? 'right-1' : 'left-1'
                )} />
              </button>
            </div>
            {emailEnabled && (
              <div className="ml-8">
                <label className="block text-sm font-medium text-gray-300 mb-2">Notification Email</label>
                <input
                  type="email"
                  value={emailAddress}
                  onChange={(e) => setEmailAddress(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-yellow-500"
                />
              </div>
            )}
          </div>
        </div>

        {/* Notification Types */}
        <div>
          <h3 className="font-medium mb-4">Notification Types</h3>
          <div className="space-y-3">
            <NotificationToggle
              label="Critical Alarms"
              description="Machine faults and critical alerts"
              enabled={alarmNotify}
              onChange={setAlarmNotify}
            />
            <NotificationToggle
              label="Downtime Events"
              description="Unplanned machine stoppages"
              enabled={downtimeNotify}
              onChange={setDowntimeNotify}
            />
            <NotificationToggle
              label="Quality Alerts"
              description="SPC violations and quality issues"
              enabled={qualityNotify}
              onChange={setQualityNotify}
            />
            <NotificationToggle
              label="Maintenance Reminders"
              description="Scheduled maintenance notifications"
              enabled={maintenanceNotify}
              onChange={setMaintenanceNotify}
            />
          </div>
        </div>

        <div className="flex justify-end pt-4 border-t border-gray-700">
          <button
            onClick={onSave}
            className="flex items-center space-x-2 px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-black font-medium rounded-lg transition-colors"
          >
            <Save className="h-4 w-4" />
            <span>Save Changes</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function NotificationToggle({
  label,
  description,
  enabled,
  onChange,
}: {
  label: string;
  description: string;
  enabled: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
      <div>
        <div className="font-medium">{label}</div>
        <div className="text-sm text-gray-500">{description}</div>
      </div>
      <button
        onClick={() => onChange(!enabled)}
        className={clsx(
          'w-12 h-6 rounded-full transition-colors relative',
          enabled ? 'bg-yellow-500' : 'bg-gray-600'
        )}
      >
        <span className={clsx(
          'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
          enabled ? 'right-1' : 'left-1'
        )} />
      </button>
    </div>
  );
}

function BackupSettings() {
  const backups = [
    { id: 'bkp-001', date: '2024-12-08T02:00:00Z', size: '2.4 GB', type: 'Automatic', status: 'completed' },
    { id: 'bkp-002', date: '2024-12-07T02:00:00Z', size: '2.3 GB', type: 'Automatic', status: 'completed' },
    { id: 'bkp-003', date: '2024-12-06T14:30:00Z', size: '2.3 GB', type: 'Manual', status: 'completed' },
    { id: 'bkp-004', date: '2024-12-06T02:00:00Z', size: '2.2 GB', type: 'Automatic', status: 'completed' },
  ];

  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="px-6 py-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold">Backup & Restore</h2>
          <p className="text-sm text-gray-400">Manage system backups and data recovery</p>
        </div>
        <div className="p-6 space-y-6">
          {/* Backup Actions */}
          <div className="flex items-center space-x-4">
            <button className="flex items-center space-x-2 px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-black font-medium rounded-lg transition-colors">
              <Download className="h-4 w-4" />
              <span>Create Backup</span>
            </button>
            <button className="flex items-center space-x-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
              <Upload className="h-4 w-4" />
              <span>Restore from Backup</span>
            </button>
          </div>

          {/* Auto Backup Settings */}
          <div className="p-4 bg-gray-700/50 rounded-lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="font-medium">Automatic Backups</div>
                <div className="text-sm text-gray-500">Daily at 2:00 AM</div>
              </div>
              <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-sm">Enabled</span>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-400">Retention:</span>
                <span className="ml-2">30 days</span>
              </div>
              <div>
                <span className="text-gray-400">Storage Used:</span>
                <span className="ml-2">45.2 GB / 100 GB</span>
              </div>
            </div>
          </div>

          {/* Backup History */}
          <div>
            <h3 className="font-medium mb-3">Recent Backups</h3>
            <div className="space-y-2">
              {backups.map((backup) => (
                <div key={backup.id} className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                  <div className="flex items-center space-x-4">
                    <HardDrive className="h-5 w-5 text-gray-400" />
                    <div>
                      <div className="font-medium">
                        {new Date(backup.date).toLocaleDateString()} - {new Date(backup.date).toLocaleTimeString()}
                      </div>
                      <div className="text-sm text-gray-500">{backup.type} • {backup.size}</div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="text-green-400 text-sm flex items-center space-x-1">
                      <CheckCircle className="h-4 w-4" />
                      <span>Completed</span>
                    </span>
                    <button className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded transition-colors" title="Download">
                      <Download className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SecuritySettings({ onSave }: { onSave: () => void }) {
  const [sessionTimeout, setSessionTimeout] = useState(30);
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [passwordExpiry, setPasswordExpiry] = useState(90);
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700">
      <div className="px-6 py-4 border-b border-gray-700">
        <h2 className="text-lg font-semibold">Security Settings</h2>
        <p className="text-sm text-gray-400">Authentication and security configuration</p>
      </div>
      <div className="p-6 space-y-6">
        {/* Session Settings */}
        <div>
          <h3 className="font-medium mb-4">Session Management</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Session Timeout: {sessionTimeout} minutes
              </label>
              <input
                type="range"
                min="5"
                max="120"
                value={sessionTimeout}
                onChange={(e) => setSessionTimeout(Number(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>5 min</span>
                <span>120 min</span>
              </div>
            </div>
          </div>
        </div>

        {/* MFA */}
        <div className="p-4 bg-gray-700/50 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Shield className="h-5 w-5 text-gray-400" />
              <div>
                <div className="font-medium">Two-Factor Authentication</div>
                <div className="text-sm text-gray-500">Require MFA for all users</div>
              </div>
            </div>
            <button
              onClick={() => setMfaEnabled(!mfaEnabled)}
              className={clsx(
                'w-12 h-6 rounded-full transition-colors relative',
                mfaEnabled ? 'bg-yellow-500' : 'bg-gray-600'
              )}
            >
              <span className={clsx(
                'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                mfaEnabled ? 'right-1' : 'left-1'
              )} />
            </button>
          </div>
        </div>

        {/* Password Policy */}
        <div>
          <h3 className="font-medium mb-4">Password Policy</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Password Expiry (days)</label>
              <select
                value={passwordExpiry}
                onChange={(e) => setPasswordExpiry(Number(e.target.value))}
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-yellow-500"
              >
                <option value={30}>30 days</option>
                <option value={60}>60 days</option>
                <option value={90}>90 days</option>
                <option value={180}>180 days</option>
                <option value={0}>Never</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Minimum Length</label>
              <input
                type="number"
                value={12}
                readOnly
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg"
              />
            </div>
          </div>
          <div className="mt-4 p-3 bg-gray-700/30 rounded-lg">
            <h4 className="text-sm font-medium mb-2">Password Requirements</h4>
            <ul className="text-sm text-gray-400 space-y-1">
              <li className="flex items-center space-x-2">
                <CheckCircle className="h-4 w-4 text-green-400" />
                <span>Minimum 12 characters</span>
              </li>
              <li className="flex items-center space-x-2">
                <CheckCircle className="h-4 w-4 text-green-400" />
                <span>At least one uppercase letter</span>
              </li>
              <li className="flex items-center space-x-2">
                <CheckCircle className="h-4 w-4 text-green-400" />
                <span>At least one number</span>
              </li>
              <li className="flex items-center space-x-2">
                <CheckCircle className="h-4 w-4 text-green-400" />
                <span>At least one special character</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Audit Log */}
        <div className="p-4 bg-gray-700/50 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Lock className="h-5 w-5 text-gray-400" />
              <div>
                <div className="font-medium">Security Audit Log</div>
                <div className="text-sm text-gray-500">Track all security-related events</div>
              </div>
            </div>
            <button className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">
              View Logs
            </button>
          </div>
        </div>

        <div className="flex justify-end pt-4 border-t border-gray-700">
          <button
            onClick={onSave}
            className="flex items-center space-x-2 px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-black font-medium rounded-lg transition-colors"
          >
            <Save className="h-4 w-4" />
            <span>Save Changes</span>
          </button>
        </div>
      </div>
    </div>
  );
}
