import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { attendanceApi } from '../services/api'
import { format, subDays } from 'date-fns'

const STATUS_LABELS = {
  ON_TIME: 'Đúng giờ',
  LATE: 'Đi muộn',
  ABSENT: 'Vắng mặt',
  EARLY_LEAVE: 'Về sớm',
}

const STATUS_BADGE = {
  ON_TIME: 'badge-success',
  LATE: 'badge-warning',
  ABSENT: 'badge-danger',
  EARLY_LEAVE: 'bg-orange-100 text-orange-800 text-xs font-medium px-2.5 py-0.5 rounded-full',
}

export default function AttendanceLog() {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(false)
  const [startDate, setStartDate] = useState(
    format(subDays(new Date(), 30), 'yyyy-MM-dd')
  )
  const [endDate, setEndDate] = useState(format(new Date(), 'yyyy-MM-dd'))
  const [department, setDepartment] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [exporting, setExporting] = useState(false)

  const DEPARTMENTS = ['Kỹ thuật', 'Kinh doanh', 'Marketing', 'Nhân sự', 'Kế toán', 'Ban giám đốc']

  const loadRecords = useCallback(async () => {
    setLoading(true)
    try {
      const res = await attendanceApi.getHistory({
        start_date: startDate,
        end_date: endDate,
        department: department || undefined,
        status: statusFilter || undefined,
        page,
        size: 50,
      })
      setRecords(res.data)
    } catch (err) {
      toast.error(err.message || 'Lỗi tải dữ liệu')
    } finally {
      setLoading(false)
    }
  }, [startDate, endDate, department, statusFilter, page])

  useEffect(() => {
    loadRecords()
  }, [loadRecords])

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await attendanceApi.export({
        start_date: startDate,
        end_date: endDate,
        department: department || undefined,
      })
      // Tạo link download
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `diem-danh-${startDate}-${endDate}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('Xuất CSV thành công')
    } catch (err) {
      toast.error('Không thể xuất CSV: ' + err.message)
    } finally {
      setExporting(false)
    }
  }

  const handleFilter = () => {
    setPage(1)
    loadRecords()
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Lịch sử điểm danh</h1>
          <p className="text-gray-500 text-sm mt-1">
            {records.length} bản ghi
          </p>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="btn-secondary text-sm"
        >
          {exporting ? 'Đang xuất...' : '📥 Xuất CSV'}
        </button>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Từ ngày</label>
            <input
              type="date"
              className="input-field"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Đến ngày</label>
            <input
              type="date"
              className="input-field"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Phòng ban</label>
            <select
              className="input-field"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
            >
              <option value="">Tất cả</option>
              {DEPARTMENTS.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Trạng thái</label>
            <select
              className="input-field"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">Tất cả</option>
              {Object.entries(STATUS_LABELS).map(([val, label]) => (
                <option key={val} value={val}>{label}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <button onClick={handleFilter} className="btn-primary text-sm">
            🔍 Lọc
          </button>
          <button
            onClick={() => {
              setStartDate(format(subDays(new Date(), 30), 'yyyy-MM-dd'))
              setEndDate(format(new Date(), 'yyyy-MM-dd'))
              setDepartment('')
              setStatusFilter('')
              setPage(1)
            }}
            className="btn-secondary text-sm"
          >
            Đặt lại
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400">Đang tải...</div>
        ) : records.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            Không có bản ghi trong khoảng thời gian này
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Ngày</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Mã NV</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Họ tên</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Phòng ban</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Giờ vào</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Giờ ra</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Độ tin cậy</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr
                    key={record.id}
                    className="border-b border-gray-50 hover:bg-gray-50"
                  >
                    <td className="px-4 py-3 text-gray-700">
                      {new Date(record.date).toLocaleDateString('vi-VN')}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">
                      {record.employee_id}
                    </td>
                    <td className="px-4 py-3 font-medium">{record.full_name}</td>
                    <td className="px-4 py-3 text-gray-500">{record.department || '-'}</td>
                    <td className="px-4 py-3 text-gray-700">
                      {record.check_in_time
                        ? new Date(record.check_in_time).toLocaleTimeString('vi-VN')
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {record.check_out_time
                        ? new Date(record.check_out_time).toLocaleTimeString('vi-VN')
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {record.confidence_score
                        ? `${(record.confidence_score * 100).toFixed(1)}%`
                        : '-'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={STATUS_BADGE[record.status] || 'badge-info'}>
                        {STATUS_LABELS[record.status] || record.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {records.length === 50 && (
          <div className="p-4 flex items-center justify-between border-t border-gray-100">
            <span className="text-sm text-gray-500">
              Trang {page}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-secondary text-xs py-1 px-3 disabled:opacity-40"
              >
                ← Trước
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={records.length < 50}
                className="btn-secondary text-xs py-1 px-3 disabled:opacity-40"
              >
                Sau →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
