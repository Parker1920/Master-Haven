import React from 'react'
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'

const COLORS = [
  '#00C2B3', // Cyan (primary)
  '#9d4edd', // Purple
  '#22c55e', // Green
  '#f59e0b', // Amber
  '#ef4444', // Red
  '#3b82f6', // Blue
  '#ec4899', // Pink
  '#8b5cf6', // Violet
  '#14b8a6', // Teal
  '#f97316', // Orange
]

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload || !payload.length) return null

  const data = payload[0].payload

  return (
    <div
      className="rounded-lg p-3 shadow-xl"
      style={{
        background: 'var(--app-card)',
        border: '1px solid rgba(255,255,255,0.1)'
      }}
    >
      <div className="font-medium mb-1" style={{ color: payload[0].payload.fill }}>
        {data.discord_tag || 'Untagged'}
      </div>
      <div className="text-sm" style={{ color: 'var(--app-text)' }}>
        <div>Submissions: <span className="font-semibold">{data.total_submissions}</span></div>
        <div>Submitters: <span className="font-semibold">{data.unique_submitters}</span></div>
        <div>Approval Rate: <span className="font-semibold">{data.approval_rate}%</span></div>
      </div>
    </div>
  )
}

const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  if (percent < 0.05) return null // Don't show labels for very small slices

  const RADIAN = Math.PI / 180
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)

  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      style={{ fontSize: '12px', fontWeight: 600 }}
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  )
}

export default function CommunityPieChart({ data, loading = false, height = 300, showLegend = true }) {
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

  // Add colors to data
  const coloredData = data.map((item, index) => ({
    ...item,
    fill: COLORS[index % COLORS.length]
  }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={coloredData}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={renderCustomLabel}
          outerRadius={height / 3}
          innerRadius={height / 6}
          dataKey="total_submissions"
          nameKey="discord_tag"
          paddingAngle={2}
        >
          {coloredData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.fill} />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        {showLegend && (
          <Legend
            layout="vertical"
            align="right"
            verticalAlign="middle"
            formatter={(value, entry) => (
              <span style={{ color: 'var(--app-text)', fontSize: '12px' }}>
                {value || 'Untagged'}
              </span>
            )}
          />
        )}
      </PieChart>
    </ResponsiveContainer>
  )
}
