import axios from 'axios'

const ADMIN_TOKEN_STORAGE_KEY = 'face_attendance_admin_token'

export const getAdminToken = () => localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || ''

export const setAdminToken = (token) => {
  const cleanToken = token.trim()
  if (cleanToken) {
    localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, cleanToken)
  } else {
    localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY)
  }
}

export const clearAdminToken = () => localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY)

export const buildRecognitionWsUrl = () => {
  const baseUrl =
    import.meta.env.VITE_WS_URL || 'ws://localhost:8000/api/recognition/stream'
  const token = getAdminToken()
  if (!token) return baseUrl

  const separator = baseUrl.includes('?') ? '&' : '?'
  return `${baseUrl}${separator}token=${encodeURIComponent(token)}`
}

// Tạo axios instance với base URL
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = getAdminToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Interceptor để xử lý lỗi toàn cục
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'Đã xảy ra lỗi không xác định'
    return Promise.reject(new Error(message))
  }
)

// ===== User APIs =====
export const userApi = {
  /** Đăng ký nhân viên mới */
  register: (data) => api.post('/users/register', data),

  /** Lấy danh sách nhân viên */
  list: (params = {}) => api.get('/users/', { params }),

  /** Lấy thông tin nhân viên theo ID */
  get: (id) => api.get(`/users/${id}`),

  /** Cập nhật thông tin nhân viên */
  update: (id, data) => api.put(`/users/${id}`, data),

  /** Xoá nhân viên */
  delete: (id) => api.delete(`/users/${id}`),

  /** Cập nhật ảnh khuôn mặt */
  updateFace: (id, faceImageBase64) =>
    api.put(`/users/${id}/face`, { face_image_base64: faceImageBase64 }),
}

// ===== Attendance APIs =====
export const attendanceApi = {
  /** Check-in bằng nhận diện khuôn mặt */
  checkIn: (imageBase64, notes) =>
    api.post('/attendance/check-in', { image_base64: imageBase64, notes }),

  /** Check-out */
  checkOut: (data) => api.post('/attendance/check-out', data),

  /** Lấy điểm danh hôm nay */
  getToday: () => api.get('/attendance/today'),

  /** Lấy lịch sử điểm danh */
  getHistory: (params = {}) => api.get('/attendance/history', { params }),

  /** Lấy thống kê */
  getStats: () => api.get('/attendance/stats'),

  /** Xuất CSV */
  export: (params = {}) =>
    api.get('/attendance/export', {
      params,
      responseType: 'blob',
    }),
}

// ===== Recognition APIs =====
export const recognitionApi = {
  /** Phát hiện khuôn mặt */
  detect: (imageBase64) =>
    api.post('/recognition/detect', { image_base64: imageBase64 }),

  /** Nhận diện khuôn mặt */
  identify: (imageBase64) =>
    api.post('/recognition/identify', { image_base64: imageBase64 }),
}

export default api
