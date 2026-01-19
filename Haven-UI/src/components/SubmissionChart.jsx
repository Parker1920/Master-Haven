import React from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'
import { format, parseISO } from 'date-fns'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null

  return (
    <div
      className="rounded-lg p-3 shadow-xl"
      style={{
        background: 'var(--app-card)',
        border: '1px solid rgba(255,255,255,0.1)'
      }}
    >
      <div className="text-xs font-medium mb-2" style={{ color: 'var(--app-text)' }}>
        {label}
      </div>
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center justify-between gap-4 text-sm">
          <span style={{ color: entry.color }}>{entry.name}:</span>
          <span className="font-semibold" style={{ color: 'var(--app-text)' }}>{entry.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function SubmissionChart({ data, loading = false, height = 300 }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ height }}>
        <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: 'var(--app-primary)' }}></div>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center" style={{ height, color: 'var(--app-text)', opacity: 0.5 }}>
        No data available
      </div>
    )
  }

  // Format dates for display
  const formattedData = data.map(item => ({
    ...item,
    displayDate: item.date.includes('W')
      ? item.date  // Week format
      : item.date.length === 7
        ? item.date  // Month format (YYYY-MM)
        : format(parseISO(item.date), 'MMM d')  // Day format
  }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={formattedData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="colorSubmissions" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#00C2B3" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#00C2B3" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorApproved" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorRejected" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis
          dataKey="displayDate"
          tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }}
          axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
          tickLine={{ stroke: 'rgba(255,255,255,0.1)' }}
        />
        <YAxis
          tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }}
          axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
          tickLine={{ stroke: 'rgba(255,255,255,0.1)' }}
          allowDecimals={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ paddingTop: '10px' }}
          formatter={(value) => <span style={{ color: 'var(--app-text)', fontSize: '12px' }}>{value}</span>}
        />
        <Area
          type="monotone"
          dataKey="submissions"
          name="Total"
          stroke="#00C2B3"
          strokeWidth={2}
          fill="url(#colorSubmissions)"
        />
        <Area
          type="monotone"
          dataKey="approved"
          name="Approved"
          stroke="#22c55e"
          strokeWidth={2}
          fill="url(#colorApproved)"
        />
        <Area
          type="monotone"
          dataKey="rejected"
          name="Rejected"
          stroke="#ef4444"
          strokeWidth={2}
          fill="url(#colorRejected)"
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
