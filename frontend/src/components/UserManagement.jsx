import { useCallback, useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { userApi } from '../services/api'

const DEPARTMENTS = ['Kỹ thuật', 'Kinh doanh', 'Marketing', 'Nhân sự', 'Kế toán', 'Ban giám đốc']

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-screen overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="font-semibold text-lg text-gray-900">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
          >
            ×
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  )
}

function RegisterModal({ onClose, onSuccess }) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [capturedImage, setCapturedImage] = useState(null)
  const [formData, setFormData] = useState({
    employee_id: '',
    full_name: '',
    email: '',
    department: '',
    position: '',
  })
  const [loading, setLoading] = useState(false)
  const [cameraError, setCameraError] = useState(null)

  useEffect(() => {
    startCamera()
    return () => stopCamera()
  }, [])

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true })
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
    } catch (err) {
      setCameraError('Không thể truy cập camera: ' + err.message)
    }
  }

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
  }

  const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024 // 5MB

  const capturePhoto = () => {
    const video = videoRef.current
    if (!video) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)

    let quality = 0.9
    let dataUrl = canvas.toDataURL('image/jpeg', quality)

    // Giảm chất lượng nếu vượt quá giới hạn 5MB
    while (dataUrl.length * 0.75 > MAX_IMAGE_SIZE_BYTES && quality > 0.3) {
      quality -= 0.1
      dataUrl = canvas.toDataURL('image/jpeg', quality)
    }

    if (dataUrl.length * 0.75 > MAX_IMAGE_SIZE_BYTES) {
      toast.error('Ảnh quá lớn, vui lòng thử lại')
      return
    }

    setCapturedImage(dataUrl)
    stopCamera()
  }

  const retake = () => {
    setCapturedImage(null)
    startCamera()
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formData.employee_id || !formData.full_name) {
      toast.error('Vui lòng điền đầy đủ thông tin bắt buộc')
      return
    }

    setLoading(true)
    try {
      await userApi.register({
        ...formData,
        face_image_base64: capturedImage,
      })
      toast.success('Đăng ký nhân viên thành công!')
      onSuccess()
      onClose()
    } catch (err) {
      toast.error(err.message || 'Đăng ký thất bại')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Camera section */}
      <div className="aspect-video bg-black rounded-lg overflow-hidden relative">
        {capturedImage ? (
          <img src={capturedImage} alt="Ảnh chụp" className="w-full h-full object-cover" />
        ) : (
          <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
        )}
        {cameraError && (
          <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-60 text-white text-sm text-center px-4">
            {cameraError}
          </div>
        )}
      </div>

      <div className="flex gap-2">
        {!capturedImage ? (
          <button
            type="button"
            onClick={capturePhoto}
            className="btn-primary flex-1"
            disabled={!!cameraError}
          >
            📸 Chụp ảnh
          </button>
        ) : (
          <button type="button" onClick={retake} className="btn-secondary flex-1">
            🔄 Chụp lại
          </button>
        )}
      </div>

      {/* Form fields */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Mã nhân viên <span className="text-red-500">*</span>
          </label>
          <input
            className="input-field"
            value={formData.employee_id}
            onChange={(e) => setFormData({ ...formData, employee_id: e.target.value })}
            placeholder="NV001"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Họ và tên <span className="text-red-500">*</span>
          </label>
          <input
            className="input-field"
            value={formData.full_name}
            onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            placeholder="Nguyễn Văn A"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input
            className="input-field"
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            placeholder="email@company.com"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Phòng ban</label>
          <select
            className="input-field"
            value={formData.department}
            onChange={(e) => setFormData({ ...formData, department: e.target.value })}
          >
            <option value="">-- Chọn phòng ban --</option>
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Chức vụ</label>
          <input
            className="input-field"
            value={formData.position}
            onChange={(e) => setFormData({ ...formData, position: e.target.value })}
            placeholder="Kỹ sư phần mềm"
          />
        </div>
      </div>

      <div className="flex gap-3 pt-2">
        <button type="button" onClick={onClose} className="btn-secondary flex-1">
          Huỷ
        </button>
        <button type="submit" className="btn-primary flex-1" disabled={loading}>
          {loading ? 'Đang xử lý...' : 'Đăng ký'}
        </button>
      </div>
    </form>
  )
}

export default function UserManagement() {
  const [users, setUsers] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [department, setDepartment] = useState('')
  const [loading, setLoading] = useState(false)
  const [showRegister, setShowRegister] = useState(false)

  const loadUsers = useCallback(async () => {
    setLoading(true)
    try {
      const res = await userApi.list({
        page,
        size: 20,
        search: search || undefined,
        department: department || undefined,
      })
      setUsers(res.data.items)
      setTotal(res.data.total)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }, [page, search, department])

  useEffect(() => {
    loadUsers()
  }, [loadUsers])

  const handleDelete = async (user) => {
    if (!confirm(`Xoá nhân viên "${user.full_name}"?`)) return
    try {
      await userApi.delete(user.id)
      toast.success('Đã xoá nhân viên')
      loadUsers()
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Quản lý nhân viên</h1>
          <p className="text-gray-500 text-sm mt-1">Tổng: {total} nhân viên</p>
        </div>
        <button onClick={() => setShowRegister(true)} className="btn-primary">
          + Thêm nhân viên
        </button>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex gap-3 flex-wrap">
          <input
            className="input-field max-w-xs"
            placeholder="Tìm theo tên hoặc mã NV..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          />
          <select
            className="input-field max-w-xs"
            value={department}
            onChange={(e) => { setDepartment(e.target.value); setPage(1) }}
          >
            <option value="">-- Tất cả phòng ban --</option>
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400">Đang tải...</div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center text-gray-400">Không có dữ liệu</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Mã NV</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Họ tên</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Email</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Phòng ban</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Khuôn mặt</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Trạng thái</th>
                  <th className="text-right px-4 py-3 text-gray-500 font-medium">Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">
                      {user.employee_id}
                    </td>
                    <td className="px-4 py-3 font-medium">{user.full_name}</td>
                    <td className="px-4 py-3 text-gray-500">{user.email || '-'}</td>
                    <td className="px-4 py-3 text-gray-500">{user.department || '-'}</td>
                    <td className="px-4 py-3">
                      {user.has_face_embedding ? (
                        <span className="badge-success">✓ Đã đăng ký</span>
                      ) : (
                        <span className="badge-warning">Chưa đăng ký</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {user.is_active ? (
                        <span className="badge-success">Hoạt động</span>
                      ) : (
                        <span className="badge-danger">Vô hiệu</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(user)}
                        className="text-red-500 hover:text-red-700 text-xs"
                      >
                        Xoá
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {total > 20 && (
          <div className="p-4 flex items-center justify-between border-t border-gray-100">
            <span className="text-sm text-gray-500">
              Hiển thị {(page - 1) * 20 + 1}-{Math.min(page * 20, total)} / {total}
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
                disabled={page * 20 >= total}
                className="btn-secondary text-xs py-1 px-3 disabled:opacity-40"
              >
                Sau →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Register modal */}
      {showRegister && (
        <Modal title="Đăng ký nhân viên mới" onClose={() => setShowRegister(false)}>
          <RegisterModal
            onClose={() => setShowRegister(false)}
            onSuccess={loadUsers}
          />
        </Modal>
      )}
    </div>
  )
}
