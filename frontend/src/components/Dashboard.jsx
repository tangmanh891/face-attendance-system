import { useEffect, useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from 'recharts'
import { attendanceApi } from '../services/api'
import { format } from 'date-fns'
import { vi } from 'date-fns/locale'

const STATUS_LABELS = {
  ON_TIME: 'Đúng giờ',
  LATE: 'Đi muộn',
  ABSENT: 'Vắng mặt',
  EARLY_LEAVE: 'Về sớm',
}

const PIE_COLORS = ['#22c55e', '#f59e0b', '#ef4444']

function StatCard({ title, value, subtitle, icon, color }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
          {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
        </div>
        <div className="text-4xl opacity-80">{icon}</div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [todayAttendance, setTodayAttendance] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [chartView, setChartView] = useState('weekly')

  useEffect(() => {
    loadData()
    // Auto-refresh mỗi 60 giây
    const timer = setInterval(loadData, 60000)
    return () => clearInterval(timer)
  }, [])

  const loadData = async () => {
    try {
      setError(null)
      const [statsRes, todayRes] = await Promise.all([
        attendanceApi.getStats(),
        attendanceApi.getToday(),
      ])
      setStats(statsRes.data)
      setTodayAttendance(todayRes.data)
    } catch (err) {
      setError(err.message || 'Lỗi tải dữ liệu')
      console.error('Lỗi tải dashboard:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">Đang tải...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          ⚠️ {error}
          <button
            onClick={loadData}
            className="ml-3 text-sm underline"
          >
            Thử lại
          </button>
        </div>
      </div>
    )
  }

  const chartData = chartView === 'weekly' ? stats?.weekly_data : stats?.monthly_data

  const pieData = stats
    ? [
        { name: 'Đúng giờ', value: stats.present_today - stats.late_today },
        { name: 'Đi muộn', value: stats.late_today },
        { name: 'Vắng mặt', value: stats.absent_today },
      ]
    : []

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">
            {format(new Date(), "EEEE, dd/MM/yyyy", { locale: vi })}
          </p>
        </div>
        <button
          onClick={loadData}
          className="btn-secondary text-sm"
        >
          🔄 Làm mới
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Tổng nhân viên"
          value={stats?.total_employees ?? '-'}
          icon="👥"
          color="text-blue-600"
          subtitle="Đang hoạt động"
        />
        <StatCard
          title="Có mặt hôm nay"
          value={stats?.present_today ?? '-'}
          icon="✅"
          color="text-green-600"
          subtitle={`${stats?.on_time_rate ?? 0}% đúng giờ`}
        />
        <StatCard
          title="Đi muộn"
          value={stats?.late_today ?? '-'}
          icon="⏰"
          color="text-yellow-600"
        />
        <StatCard
          title="Vắng mặt"
          value={stats?.absent_today ?? '-'}
          icon="❌"
          color="text-red-600"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Bar chart */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Thống kê điểm danh</h2>
            <div className="flex gap-2">
              <button
                onClick={() => setChartView('weekly')}
                className={`text-xs px-3 py-1 rounded-full ${
                  chartView === 'weekly'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:bg-gray-100'
                }`}
              >
                7 ngày
              </button>
              <button
                onClick={() => setChartView('monthly')}
                className={`text-xs px-3 py-1 rounded-full ${
                  chartView === 'monthly'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:bg-gray-100'
                }`}
              >
                30 ngày
              </button>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={250}>
            {chartView === 'weekly' ? (
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(val) =>
                    new Date(val).toLocaleDateString('vi-VN', {
                      day: '2-digit',
                      month: '2-digit',
                    })
                  }
                />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  labelFormatter={(val) =>
                    new Date(val).toLocaleDateString('vi-VN')
                  }
                />
                <Legend />
                <Bar dataKey="on_time" name="Đúng giờ" fill="#22c55e" radius={[3, 3, 0, 0]} />
                <Bar dataKey="late" name="Đi muộn" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                <Bar dataKey="absent" name="Vắng mặt" fill="#ef4444" radius={[3, 3, 0, 0]} />
              </BarChart>
            ) : (
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10 }}
                  tickFormatter={(val) =>
                    new Date(val).toLocaleDateString('vi-VN', {
                      day: '2-digit',
                      month: '2-digit',
                    })
                  }
                />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  labelFormatter={(val) =>
                    new Date(val).toLocaleDateString('vi-VN')
                  }
                />
                <Bar dataKey="count" name="Điểm danh" fill="#3b82f6" radius={[3, 3, 0, 0]} />
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>

        {/* Pie chart */}
        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-4">
            Tỷ lệ hôm nay
          </h2>
          {stats?.present_today > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    dataKey="value"
                    paddingAngle={3}
                  >
                    {pieData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={PIE_COLORS[index % PIE_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-2">
                {pieData.map((item, idx) => (
                  <div key={idx} className="flex items-center gap-2 text-sm">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: PIE_COLORS[idx] }}
                    />
                    <span className="text-gray-600 flex-1">{item.name}</span>
                    <span className="font-medium">{item.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
              Chưa có dữ liệu hôm nay
            </div>
          )}
        </div>
      </div>

      {/* Recent attendance table */}
      <div className="card">
        <h2 className="font-semibold text-gray-900 mb-4">
          Điểm danh hôm nay ({todayAttendance.length})
        </h2>
        {todayAttendance.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-6">
            Chưa có ai điểm danh hôm nay
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 text-gray-500 font-medium">Mã NV</th>
                  <th className="text-left py-2 text-gray-500 font-medium">Họ tên</th>
                  <th className="text-left py-2 text-gray-500 font-medium">Phòng ban</th>
                  <th className="text-left py-2 text-gray-500 font-medium">Giờ vào</th>
                  <th className="text-left py-2 text-gray-500 font-medium">Giờ ra</th>
                  <th className="text-left py-2 text-gray-500 font-medium">Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {todayAttendance.slice(0, 10).map((record) => (
                  <tr
                    key={record.id}
                    className="border-b border-gray-50 hover:bg-gray-50"
                  >
                    <td className="py-2.5 font-mono text-xs text-gray-500">
                      {record.employee_id}
                    </td>
                    <td className="py-2.5 font-medium">{record.full_name}</td>
                    <td className="py-2.5 text-gray-500">
                      {record.department || '-'}
                    </td>
                    <td className="py-2.5 text-gray-700">
                      {record.check_in_time
                        ? new Date(record.check_in_time).toLocaleTimeString('vi-VN')
                        : '-'}
                    </td>
                    <td className="py-2.5 text-gray-700">
                      {record.check_out_time
                        ? new Date(record.check_out_time).toLocaleTimeString('vi-VN')
                        : '-'}
                    </td>
                    <td className="py-2.5">
                      <StatusBadge status={record.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }) {
  const classes = {
    ON_TIME: 'badge-success',
    LATE: 'badge-warning',
    ABSENT: 'badge-danger',
    EARLY_LEAVE: 'bg-orange-100 text-orange-800 text-xs font-medium px-2.5 py-0.5 rounded-full',
  }
  return (
    <span className={classes[status] || 'badge-info'}>
      {STATUS_LABELS[status] || status}
    </span>
  )
}
