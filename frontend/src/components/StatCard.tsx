import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';
import clsx from 'clsx';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  color?: 'green' | 'yellow' | 'red' | 'blue' | 'purple';
  trend?: {
    value: number;
    positive: boolean;
  };
  subtext?: string;
}

const colorClasses = {
  green: {
    bg: 'bg-green-500/10',
    border: 'border-green-500/30',
    icon: 'text-green-500',
    text: 'text-green-400',
  },
  yellow: {
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    icon: 'text-yellow-500',
    text: 'text-yellow-400',
  },
  red: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    icon: 'text-red-500',
    text: 'text-red-400',
  },
  blue: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    icon: 'text-blue-500',
    text: 'text-blue-400',
  },
  purple: {
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/30',
    icon: 'text-purple-500',
    text: 'text-purple-400',
  },
};

export default function StatCard({
  title,
  value,
  icon: Icon,
  color = 'blue',
  trend,
  subtext,
}: StatCardProps) {
  const colors = colorClasses[color];

  return (
    <div
      className={clsx(
        'rounded-lg p-6 border transition-all hover:shadow-lg',
        colors.bg,
        colors.border
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          <p className="text-3xl font-bold mt-1">{value}</p>
          {trend && (
            <div className="flex items-center mt-2">
              {trend.positive ? (
                <TrendingUp className="h-4 w-4 text-green-500 mr-1" />
              ) : (
                <TrendingDown className="h-4 w-4 text-red-500 mr-1" />
              )}
              <span
                className={clsx(
                  'text-sm',
                  trend.positive ? 'text-green-500' : 'text-red-500'
                )}
              >
                {trend.value}%
              </span>
            </div>
          )}
          {subtext && (
            <p className="text-xs text-gray-500 mt-1">{subtext}</p>
          )}
        </div>
        <div className={clsx('p-3 rounded-lg', colors.bg)}>
          <Icon className={clsx('h-6 w-6', colors.icon)} />
        </div>
      </div>
    </div>
  );
}
