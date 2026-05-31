// src/components/dashboard/DashboardCharts.tsx
import React from 'react';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import type { ChartData } from '../../types/dashboard';
import { formatCurrency, formatNumber } from '../../utils/formatters';

const RISK_COLORS = ['#22c55e', '#f59e0b', '#ef4444', '#dc2626'];
const BLUE_SHADES = ['#0066CC', '#0080ff', '#3399ff', '#66b3ff', '#99ccff', '#4d9fff', '#1a80ff', '#0073e6', '#0059b3', '#004c99'];

interface ChartCardProps {
  title: string;
  children: React.ReactNode;
  loading?: boolean;
}

function ChartCard({ title, children, loading }: ChartCardProps) {
  return (
    <div className="rounded-xl border border-[#0f2040] bg-[#08111e] p-5">
      <h3 className="text-sm font-semibold text-slate-300 mb-4">{title}</h3>
      {loading ? (
        <div className="h-52 flex items-center justify-center">
          <div className="w-6 h-6 border-2 border-[#0066CC]/30 border-t-[#0066CC] rounded-full animate-spin" />
        </div>
      ) : (
        <div className="h-52">{children}</div>
      )}
    </div>
  );
}

const customTooltipStyle = {
  backgroundColor: '#0a1628',
  border: '1px solid #1a2d4e',
  borderRadius: '8px',
  fontSize: '12px',
  color: '#e2e8f0',
};

// Revenue Trend — Line Chart
export function RevenueChart({ data }: { data: ChartData }) {
  return (
    <ChartCard title={data.title}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data.data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#0f2040" />
          <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => formatCurrency(v, true)} width={52} />
          <Tooltip contentStyle={customTooltipStyle} formatter={(v: number) => [formatCurrency(v, true), 'Revenue']} />
          <Line type="monotone" dataKey="value" stroke="#0066CC" strokeWidth={2.5} dot={false} activeDot={{ r: 4, fill: '#0066CC', strokeWidth: 0 }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// Risk Distribution — Pie Chart
export function RiskChart({ data }: { data: ChartData }) {
  return (
    <ChartCard title={data.title}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data.data} dataKey="value" nameKey="label" cx="50%" cy="50%" outerRadius={80} innerRadius={40} paddingAngle={3}>
            {data.data.map((_, i) => <Cell key={i} fill={RISK_COLORS[i % RISK_COLORS.length]} />)}
          </Pie>
          <Tooltip contentStyle={customTooltipStyle} formatter={(v: number) => [`${v}%`]} />
          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }} />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// Concentration — Bar Chart
export function ConcentrationChart({ data }: { data: ChartData }) {
  return (
    <ChartCard title={data.title}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data.data} layout="vertical" margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#0f2040" horizontal={false} />
          <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => formatCurrency(v, true)} />
          <YAxis type="category" dataKey="label" tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} width={70} />
          <Tooltip contentStyle={customTooltipStyle} formatter={(v: number) => [formatCurrency(v), 'Balance']} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.data.map((_, i) => <Cell key={i} fill={BLUE_SHADES[i % BLUE_SHADES.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// Growth Rate — Area Chart
export function GrowthChart({ data }: { data: ChartData }) {
  return (
    <ChartCard title={data.title}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data.data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="growthGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#0066CC" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#0066CC" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#0f2040" />
          <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} width={36} />
          <Tooltip contentStyle={customTooltipStyle} formatter={(v: number) => [`${v}%`, 'Growth']} />
          <Area type="monotone" dataKey="value" stroke="#0066CC" strokeWidth={2.5} fill="url(#growthGrad)" dot={false} activeDot={{ r: 4, fill: '#0066CC', strokeWidth: 0 }} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// Branch Performance — Bar Chart (used in Branches page)
export function BranchPerformanceChart({ branches }: { branches: { name: string; performance_vs_plan: number }[] }) {
  const data = branches.map((b) => ({ label: b.name.split(' ')[0], value: b.performance_vs_plan }));
  return (
    <ChartCard title="Performance vs Plan (%)">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#0f2040" />
          <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} domain={[80, 115]} width={40} />
          <Tooltip contentStyle={customTooltipStyle} formatter={(v: number) => [`${v}%`, 'vs Plan']} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((d, i) => <Cell key={i} fill={d.value >= 100 ? '#22c55e' : d.value >= 95 ? '#f59e0b' : '#ef4444'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// Customer Growth Chart
export function CustomerGrowthChart({ branches }: { branches: { name: string; customer_growth_rate: number }[] }) {
  const data = branches.map((b) => ({ label: b.name.split(' ')[0], value: b.customer_growth_rate }));
  return (
    <ChartCard title="Customer Growth Rate (%)">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="custGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#22c55e" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#0f2040" />
          <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} width={36} />
          <Tooltip contentStyle={customTooltipStyle} formatter={(v: number) => [`${v}%`, 'Growth']} />
          <Area type="monotone" dataKey="value" stroke="#22c55e" strokeWidth={2.5} fill="url(#custGrad)" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// Generic query result chart — auto-detects type
export function QueryResultChart({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return <div className="h-52 flex items-center justify-center text-slate-500 text-sm">No data</div>;

  const keys = Object.keys(data[0]);
  const labelKey = keys.find((k) => typeof data[0][k] === 'string') ?? keys[0];
  const valueKey = keys.find((k) => typeof data[0][k] === 'number') ?? keys[1];
  const chartData = data.slice(0, 15).map((row) => ({ label: String(row[labelKey]).slice(0, 12), value: Number(row[valueKey]) }));

  return (
    <div className="h-52">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#0f2040" />
          <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => formatNumber(v, true)} width={52} />
          <Tooltip contentStyle={customTooltipStyle} />
          <Bar dataKey="value" fill="#0066CC" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
