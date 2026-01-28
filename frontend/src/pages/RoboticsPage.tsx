import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Bot,
  Power,
  PowerOff,
  Play,
  Pause,
  Square,
  Home,
  AlertTriangle,
  CheckCircle,
  Activity,
  Cpu,
  Thermometer,
  Gauge,
  RotateCcw,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  MoveVertical,
  RotateCw,
  Settings,
  RefreshCw,
  Zap,
  Shield,
  Clock,
  Target,
  Grip,
} from 'lucide-react';
import clsx from 'clsx';

interface Robot {
  id: string;
  name: string;
  model: string;
  status: 'running' | 'idle' | 'paused' | 'error' | 'offline';
  mode: 'auto' | 'manual' | 'maintenance';
  program?: string;
  task?: string;
  cycle_count: number;
  uptime_hours: number;
  joints: JointState[];
  end_effector: EndEffector;
  alarms: Alarm[];
  metrics: RobotMetrics;
}

interface JointState {
  name: string;
  position: number;
  velocity: number;
  torque: number;
  temperature: number;
  min_limit: number;
  max_limit: number;
}

interface EndEffector {
  type: 'gripper' | 'vacuum' | 'tool';
  status: 'open' | 'closed' | 'holding' | 'error';
  grip_force?: number;
  vacuum_pressure?: number;
  part_detected: boolean;
}

interface Alarm {
  id: string;
  code: string;
  message: string;
  severity: 'warning' | 'error' | 'critical';
  timestamp: string;
  acknowledged: boolean;
}

interface RobotMetrics {
  cpu_usage: number;
  memory_usage: number;
  network_latency: number;
  position_accuracy: number;
}

// Mock data for demonstration
const mockRobots: Robot[] = [
  {
    id: 'robot-001',
    name: 'Pick & Place Robot 1',
    model: 'UR10e',
    status: 'running',
    mode: 'auto',
    program: 'brick_sorting_v2.urp',
    task: 'Sorting red 2x4 bricks',
    cycle_count: 15847,
    uptime_hours: 1247.5,
    joints: [
      { name: 'Base', position: 45.2, velocity: 12.5, torque: 25.3, temperature: 42, min_limit: -360, max_limit: 360 },
      { name: 'Shoulder', position: -32.8, velocity: 8.2, torque: 48.7, temperature: 45, min_limit: -360, max_limit: 360 },
      { name: 'Elbow', position: 78.5, velocity: 15.1, torque: 32.1, temperature: 41, min_limit: -360, max_limit: 360 },
      { name: 'Wrist 1', position: -90.0, velocity: 5.8, torque: 12.4, temperature: 38, min_limit: -360, max_limit: 360 },
      { name: 'Wrist 2', position: 45.0, velocity: 6.2, torque: 8.9, temperature: 37, min_limit: -360, max_limit: 360 },
      { name: 'Wrist 3', position: 0.0, velocity: 4.1, torque: 5.2, temperature: 35, min_limit: -360, max_limit: 360 },
    ],
    end_effector: {
      type: 'gripper',
      status: 'holding',
      grip_force: 45,
      part_detected: true,
    },
    alarms: [],
    metrics: {
      cpu_usage: 45,
      memory_usage: 62,
      network_latency: 2.3,
      position_accuracy: 0.02,
    },
  },
  {
    id: 'robot-002',
    name: 'Assembly Robot 1',
    model: 'FANUC CRX-10iA/L',
    status: 'idle',
    mode: 'auto',
    program: 'minifig_assembly.ls',
    cycle_count: 8432,
    uptime_hours: 892.3,
    joints: [
      { name: 'J1', position: 0.0, velocity: 0.0, torque: 5.1, temperature: 35, min_limit: -170, max_limit: 170 },
      { name: 'J2', position: -45.0, velocity: 0.0, torque: 28.3, temperature: 36, min_limit: -135, max_limit: 135 },
      { name: 'J3', position: 90.0, velocity: 0.0, torque: 15.2, temperature: 34, min_limit: -203, max_limit: 203 },
      { name: 'J4', position: 0.0, velocity: 0.0, torque: 4.8, temperature: 33, min_limit: -190, max_limit: 190 },
      { name: 'J5', position: -45.0, velocity: 0.0, torque: 6.2, temperature: 32, min_limit: -125, max_limit: 125 },
      { name: 'J6', position: 0.0, velocity: 0.0, torque: 2.1, temperature: 31, min_limit: -360, max_limit: 360 },
    ],
    end_effector: {
      type: 'vacuum',
      status: 'open',
      vacuum_pressure: 0,
      part_detected: false,
    },
    alarms: [],
    metrics: {
      cpu_usage: 22,
      memory_usage: 45,
      network_latency: 1.8,
      position_accuracy: 0.015,
    },
  },
  {
    id: 'robot-003',
    name: 'Packaging Robot 1',
    model: 'ABB IRB 1200',
    status: 'error',
    mode: 'manual',
    program: 'box_packing.mod',
    cycle_count: 23156,
    uptime_hours: 1834.2,
    joints: [
      { name: 'Axis 1', position: 12.5, velocity: 0.0, torque: 18.2, temperature: 52, min_limit: -170, max_limit: 170 },
      { name: 'Axis 2', position: -28.3, velocity: 0.0, torque: 42.1, temperature: 58, min_limit: -100, max_limit: 135 },
      { name: 'Axis 3', position: 45.0, velocity: 0.0, torque: 22.8, temperature: 48, min_limit: -200, max_limit: 70 },
      { name: 'Axis 4', position: 0.0, velocity: 0.0, torque: 8.5, temperature: 42, min_limit: -270, max_limit: 270 },
      { name: 'Axis 5', position: 90.0, velocity: 0.0, torque: 12.3, temperature: 44, min_limit: -130, max_limit: 130 },
      { name: 'Axis 6', position: -15.0, velocity: 0.0, torque: 4.7, temperature: 40, min_limit: -360, max_limit: 360 },
    ],
    end_effector: {
      type: 'gripper',
      status: 'error',
      grip_force: 0,
      part_detected: false,
    },
    alarms: [
      { id: 'alm-001', code: 'E5012', message: 'Gripper actuator fault - check pneumatic supply', severity: 'error', timestamp: '2024-12-08T14:32:00Z', acknowledged: false },
      { id: 'alm-002', code: 'W2001', message: 'Axis 2 temperature approaching limit', severity: 'warning', timestamp: '2024-12-08T14:28:00Z', acknowledged: true },
    ],
    metrics: {
      cpu_usage: 15,
      memory_usage: 38,
      network_latency: 3.1,
      position_accuracy: 0.025,
    },
  },
  {
    id: 'robot-004',
    name: 'Inspection Robot 1',
    model: 'KUKA LBR iiwa 7',
    status: 'paused',
    mode: 'auto',
    program: 'visual_inspection.src',
    task: 'Quality check - paused for operator',
    cycle_count: 5621,
    uptime_hours: 456.8,
    joints: [
      { name: 'A1', position: 30.0, velocity: 0.0, torque: 8.2, temperature: 38, min_limit: -170, max_limit: 170 },
      { name: 'A2', position: -45.0, velocity: 0.0, torque: 22.5, temperature: 40, min_limit: -120, max_limit: 120 },
      { name: 'A3', position: 60.0, velocity: 0.0, torque: 12.1, temperature: 37, min_limit: -170, max_limit: 170 },
      { name: 'A4', position: -90.0, velocity: 0.0, torque: 6.8, temperature: 35, min_limit: -120, max_limit: 120 },
      { name: 'A5', position: 15.0, velocity: 0.0, torque: 4.2, temperature: 34, min_limit: -170, max_limit: 170 },
      { name: 'A6', position: 0.0, velocity: 0.0, torque: 3.1, temperature: 33, min_limit: -120, max_limit: 120 },
      { name: 'A7', position: -30.0, velocity: 0.0, torque: 1.8, temperature: 32, min_limit: -175, max_limit: 175 },
    ],
    end_effector: {
      type: 'tool',
      status: 'closed',
      part_detected: true,
    },
    alarms: [],
    metrics: {
      cpu_usage: 35,
      memory_usage: 52,
      network_latency: 1.5,
      position_accuracy: 0.01,
    },
  },
];

const statusConfig = {
  running: { label: 'Running', color: 'bg-green-500', textColor: 'text-green-400', icon: Play },
  idle: { label: 'Idle', color: 'bg-blue-500', textColor: 'text-blue-400', icon: Pause },
  paused: { label: 'Paused', color: 'bg-yellow-500', textColor: 'text-yellow-400', icon: Pause },
  error: { label: 'Error', color: 'bg-red-500', textColor: 'text-red-400', icon: AlertTriangle },
  offline: { label: 'Offline', color: 'bg-gray-500', textColor: 'text-gray-400', icon: PowerOff },
};

const modeConfig = {
  auto: { label: 'Auto', color: 'bg-green-500/20 text-green-400 border-green-500/30' },
  manual: { label: 'Manual', color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  maintenance: { label: 'Maintenance', color: 'bg-purple-500/20 text-purple-400 border-purple-500/30' },
};

export default function RoboticsPage() {
  const [selectedRobot, setSelectedRobot] = useState<Robot | null>(mockRobots[0]);
  const [jogMode, setJogMode] = useState<'joint' | 'cartesian'>('cartesian');
  const [jogSpeed, setJogSpeed] = useState(25);

  const robots = mockRobots;

  // Statistics
  const runningCount = robots.filter((r) => r.status === 'running').length;
  const errorCount = robots.filter((r) => r.status === 'error').length;
  const totalAlarms = robots.reduce((sum, r) => sum + r.alarms.filter((a) => !a.acknowledged).length, 0);
  const avgUptime = robots.reduce((sum, r) => sum + r.uptime_hours, 0) / robots.length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Robotics Control</h1>
          <p className="text-gray-400 mt-1">ROS2 robot monitoring and control interface</p>
        </div>
        <button className="flex items-center space-x-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
          <RefreshCw className="h-4 w-4" />
          <span>Refresh All</span>
        </button>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Running" value={runningCount} total={robots.length} icon={Play} color="green" />
        <StatCard label="Errors" value={errorCount} icon={AlertTriangle} color="red" />
        <StatCard label="Active Alarms" value={totalAlarms} icon={Shield} color="yellow" />
        <StatCard label="Avg Uptime" value={`${avgUptime.toFixed(0)}h`} icon={Clock} color="blue" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Robot List */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-700">
            <h2 className="font-semibold">Robots ({robots.length})</h2>
          </div>
          <div className="divide-y divide-gray-700">
            {robots.map((robot) => {
              const status = statusConfig[robot.status];
              const StatusIcon = status.icon;
              const hasAlarms = robot.alarms.filter((a) => !a.acknowledged).length > 0;

              return (
                <button
                  key={robot.id}
                  onClick={() => setSelectedRobot(robot)}
                  className={clsx(
                    'w-full p-4 text-left hover:bg-gray-700/50 transition-colors',
                    selectedRobot?.id === robot.id && 'bg-gray-700/50 border-l-2 border-yellow-500'
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className={clsx('p-2 rounded-lg', status.color + '/20')}>
                        <Bot className={clsx('h-5 w-5', status.textColor)} />
                      </div>
                      <div>
                        <div className="font-medium">{robot.name}</div>
                        <div className="text-sm text-gray-500">{robot.model}</div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {hasAlarms && (
                        <AlertTriangle className="h-4 w-4 text-red-400" />
                      )}
                      <span className={clsx(
                        'flex items-center space-x-1 px-2 py-1 rounded-full text-xs',
                        status.color + '/20',
                        status.textColor
                      )}>
                        <StatusIcon className="h-3 w-3" />
                        <span>{status.label}</span>
                      </span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Robot Details */}
        {selectedRobot && (
          <div className="lg:col-span-2 space-y-6">
            {/* Header */}
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-xl font-bold">{selectedRobot.name}</h2>
                  <p className="text-gray-400">{selectedRobot.model}</p>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={clsx(
                    'px-3 py-1 rounded-full text-sm font-medium border',
                    modeConfig[selectedRobot.mode].color
                  )}>
                    {modeConfig[selectedRobot.mode].label}
                  </span>
                  <span className={clsx(
                    'flex items-center space-x-1 px-3 py-1 rounded-full text-sm',
                    statusConfig[selectedRobot.status].color + '/20',
                    statusConfig[selectedRobot.status].textColor
                  )}>
                    {React.createElement(statusConfig[selectedRobot.status].icon, { className: 'h-4 w-4' })}
                    <span>{statusConfig[selectedRobot.status].label}</span>
                  </span>
                </div>
              </div>

              {/* Program Info */}
              {selectedRobot.program && (
                <div className="bg-gray-700/50 rounded-lg p-3 mb-4">
                  <div className="text-sm text-gray-400">Current Program</div>
                  <div className="font-mono text-yellow-400">{selectedRobot.program}</div>
                  {selectedRobot.task && (
                    <div className="text-sm text-gray-300 mt-1">{selectedRobot.task}</div>
                  )}
                </div>
              )}

              {/* Quick Stats */}
              <div className="grid grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold">{selectedRobot.cycle_count.toLocaleString()}</div>
                  <div className="text-xs text-gray-400">Cycles</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">{selectedRobot.uptime_hours.toFixed(0)}h</div>
                  <div className="text-xs text-gray-400">Uptime</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">{selectedRobot.metrics.position_accuracy * 1000}mm</div>
                  <div className="text-xs text-gray-400">Accuracy</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">{selectedRobot.metrics.network_latency}ms</div>
                  <div className="text-xs text-gray-400">Latency</div>
                </div>
              </div>

              {/* Control Buttons */}
              <div className="flex items-center space-x-2 mt-4 pt-4 border-t border-gray-700">
                <button className="flex items-center space-x-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors">
                  <Play className="h-4 w-4" />
                  <span>Start</span>
                </button>
                <button className="flex items-center space-x-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg transition-colors">
                  <Pause className="h-4 w-4" />
                  <span>Pause</span>
                </button>
                <button className="flex items-center space-x-2 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg transition-colors">
                  <Square className="h-4 w-4" />
                  <span>Stop</span>
                </button>
                <button className="flex items-center space-x-2 px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded-lg transition-colors">
                  <Home className="h-4 w-4" />
                  <span>Home</span>
                </button>
                <button className="flex items-center space-x-2 px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded-lg transition-colors">
                  <RotateCcw className="h-4 w-4" />
                  <span>Reset</span>
                </button>
              </div>
            </div>

            {/* Alarms */}
            {selectedRobot.alarms.length > 0 && (
              <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-700 bg-red-500/10">
                  <h3 className="font-semibold text-red-400 flex items-center space-x-2">
                    <AlertTriangle className="h-4 w-4" />
                    <span>Active Alarms ({selectedRobot.alarms.length})</span>
                  </h3>
                </div>
                <div className="divide-y divide-gray-700">
                  {selectedRobot.alarms.map((alarm) => (
                    <div
                      key={alarm.id}
                      className={clsx(
                        'p-4 flex items-start justify-between',
                        alarm.severity === 'critical' && 'bg-red-500/10',
                        alarm.severity === 'error' && 'bg-red-500/5',
                        alarm.severity === 'warning' && 'bg-yellow-500/5'
                      )}
                    >
                      <div className="flex items-start space-x-3">
                        <AlertTriangle className={clsx(
                          'h-5 w-5 mt-0.5',
                          alarm.severity === 'critical' && 'text-red-500',
                          alarm.severity === 'error' && 'text-red-400',
                          alarm.severity === 'warning' && 'text-yellow-400'
                        )} />
                        <div>
                          <div className="font-mono text-sm">{alarm.code}</div>
                          <div className="text-gray-300">{alarm.message}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            {new Date(alarm.timestamp).toLocaleString()}
                          </div>
                        </div>
                      </div>
                      {!alarm.acknowledged && (
                        <button className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors">
                          Acknowledge
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Joint States */}
            <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-700">
                <h3 className="font-semibold">Joint States</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-700/50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase">Joint</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase">Position</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase">Velocity</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase">Torque</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase">Temp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {selectedRobot.joints.map((joint) => {
                      const positionPercent = ((joint.position - joint.min_limit) / (joint.max_limit - joint.min_limit)) * 100;
                      const tempWarning = joint.temperature > 50;

                      return (
                        <tr key={joint.name} className="hover:bg-gray-700/30">
                          <td className="px-4 py-3 font-medium">{joint.name}</td>
                          <td className="px-4 py-3">
                            <div className="flex items-center space-x-2">
                              <span className="font-mono w-16">{joint.position.toFixed(1)}°</span>
                              <div className="w-24 h-2 bg-gray-700 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-yellow-500"
                                  style={{ width: `${Math.max(0, Math.min(100, positionPercent))}%` }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3 font-mono text-sm">
                            {joint.velocity.toFixed(1)}°/s
                          </td>
                          <td className="px-4 py-3 font-mono text-sm">
                            {joint.torque.toFixed(1)} Nm
                          </td>
                          <td className="px-4 py-3">
                            <span className={clsx(
                              'font-mono text-sm',
                              tempWarning ? 'text-red-400' : 'text-gray-300'
                            )}>
                              {joint.temperature}°C
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* End Effector & Jog Control */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* End Effector */}
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                <h3 className="font-semibold mb-4 flex items-center space-x-2">
                  <Grip className="h-4 w-4" />
                  <span>End Effector</span>
                </h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Type</span>
                    <span className="capitalize">{selectedRobot.end_effector.type}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Status</span>
                    <span className={clsx(
                      'px-2 py-1 rounded text-sm',
                      selectedRobot.end_effector.status === 'holding' && 'bg-green-500/20 text-green-400',
                      selectedRobot.end_effector.status === 'open' && 'bg-gray-500/20 text-gray-400',
                      selectedRobot.end_effector.status === 'closed' && 'bg-blue-500/20 text-blue-400',
                      selectedRobot.end_effector.status === 'error' && 'bg-red-500/20 text-red-400'
                    )}>
                      {selectedRobot.end_effector.status.toUpperCase()}
                    </span>
                  </div>
                  {selectedRobot.end_effector.grip_force !== undefined && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">Grip Force</span>
                      <span>{selectedRobot.end_effector.grip_force}%</span>
                    </div>
                  )}
                  {selectedRobot.end_effector.vacuum_pressure !== undefined && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">Vacuum</span>
                      <span>{selectedRobot.end_effector.vacuum_pressure} kPa</span>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Part Detected</span>
                    <span className={selectedRobot.end_effector.part_detected ? 'text-green-400' : 'text-gray-500'}>
                      {selectedRobot.end_effector.part_detected ? 'Yes' : 'No'}
                    </span>
                  </div>
                  <div className="flex space-x-2 pt-2">
                    <button className="flex-1 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded transition-colors text-sm">
                      Open
                    </button>
                    <button className="flex-1 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded transition-colors text-sm">
                      Close
                    </button>
                  </div>
                </div>
              </div>

              {/* Jog Control */}
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold flex items-center space-x-2">
                    <Target className="h-4 w-4" />
                    <span>Jog Control</span>
                  </h3>
                  <div className="flex space-x-1 bg-gray-700 rounded-lg p-0.5">
                    <button
                      onClick={() => setJogMode('cartesian')}
                      className={clsx(
                        'px-2 py-1 text-xs rounded transition-colors',
                        jogMode === 'cartesian' ? 'bg-yellow-500 text-black' : 'text-gray-400'
                      )}
                    >
                      Cartesian
                    </button>
                    <button
                      onClick={() => setJogMode('joint')}
                      className={clsx(
                        'px-2 py-1 text-xs rounded transition-colors',
                        jogMode === 'joint' ? 'bg-yellow-500 text-black' : 'text-gray-400'
                      )}
                    >
                      Joint
                    </button>
                  </div>
                </div>

                {/* Speed Slider */}
                <div className="mb-4">
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-gray-400">Speed</span>
                    <span>{jogSpeed}%</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="100"
                    value={jogSpeed}
                    onChange={(e) => setJogSpeed(Number(e.target.value))}
                    className="w-full"
                  />
                </div>

                {/* Jog Buttons */}
                <div className="grid grid-cols-3 gap-2">
                  <div />
                  <button className="p-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                    <ArrowUp className="h-5 w-5 mx-auto" />
                    <span className="text-xs">+Y</span>
                  </button>
                  <div />
                  <button className="p-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                    <ArrowLeft className="h-5 w-5 mx-auto" />
                    <span className="text-xs">-X</span>
                  </button>
                  <button className="p-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                    <MoveVertical className="h-5 w-5 mx-auto" />
                    <span className="text-xs">Z</span>
                  </button>
                  <button className="p-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                    <ArrowRight className="h-5 w-5 mx-auto" />
                    <span className="text-xs">+X</span>
                  </button>
                  <button className="p-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                    <RotateCcw className="h-5 w-5 mx-auto" />
                    <span className="text-xs">-Rz</span>
                  </button>
                  <button className="p-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                    <ArrowDown className="h-5 w-5 mx-auto" />
                    <span className="text-xs">-Y</span>
                  </button>
                  <button className="p-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                    <RotateCw className="h-5 w-5 mx-auto" />
                    <span className="text-xs">+Rz</span>
                  </button>
                </div>
              </div>
            </div>

            {/* System Metrics */}
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
              <h3 className="font-semibold mb-4 flex items-center space-x-2">
                <Cpu className="h-4 w-4" />
                <span>System Metrics</span>
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricGauge label="CPU Usage" value={selectedRobot.metrics.cpu_usage} unit="%" />
                <MetricGauge label="Memory" value={selectedRobot.metrics.memory_usage} unit="%" />
                <MetricGauge label="Network Latency" value={selectedRobot.metrics.network_latency} unit="ms" max={10} />
                <MetricGauge label="Position Accuracy" value={selectedRobot.metrics.position_accuracy * 1000} unit="mm" max={1} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  total,
  icon: Icon,
  color,
}: {
  label: string;
  value: number | string;
  total?: number;
  icon: React.ElementType;
  color: 'green' | 'red' | 'yellow' | 'blue';
}) {
  const colorClasses = {
    green: 'bg-green-500/10 border-green-500/30 text-green-400',
    red: 'bg-red-500/10 border-red-500/30 text-red-400',
    yellow: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
    blue: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
  };

  return (
    <div className={clsx('p-4 rounded-lg border', colorClasses[color])}>
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">{label}</p>
        <Icon className="h-5 w-5" />
      </div>
      <p className="text-2xl font-bold mt-2">
        {value}
        {total !== undefined && <span className="text-gray-500 text-lg">/{total}</span>}
      </p>
    </div>
  );
}

function MetricGauge({
  label,
  value,
  unit,
  max = 100,
}: {
  label: string;
  value: number;
  unit: string;
  max?: number;
}) {
  const percentage = Math.min(100, (value / max) * 100);
  const isWarning = percentage > 80;
  const isDanger = percentage > 90;

  return (
    <div className="text-center">
      <div className="relative w-20 h-20 mx-auto">
        <svg className="w-full h-full transform -rotate-90">
          <circle
            cx="40"
            cy="40"
            r="35"
            stroke="currentColor"
            strokeWidth="6"
            fill="none"
            className="text-gray-700"
          />
          <circle
            cx="40"
            cy="40"
            r="35"
            stroke="currentColor"
            strokeWidth="6"
            fill="none"
            strokeDasharray={`${percentage * 2.2} 220`}
            className={clsx(
              isDanger ? 'text-red-500' : isWarning ? 'text-yellow-500' : 'text-green-500'
            )}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold">{value.toFixed(value < 1 ? 2 : 0)}</span>
        </div>
      </div>
      <div className="text-xs text-gray-400 mt-2">{label}</div>
      <div className="text-xs text-gray-500">{unit}</div>
    </div>
  );
}
