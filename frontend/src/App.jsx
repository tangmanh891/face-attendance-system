import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import Camera from './components/Camera'
import UserManagement from './components/UserManagement'
import AttendanceLog from './components/AttendanceLog'
import { clearAdminToken, getAdminToken, setAdminToken } from './services/api'

const navItems = [
  { path: '/', label: 'Dashboard', icon: '📊' },
  { path: '/camera', label: 'Camera', icon: '📷' },
  { path: '/users', label: 'Nhân viên', icon: '👥' },
  { path: '/attendance', label: 'Lịch sử', icon: '📋' },
]

function TokenControl() {
  const [token, setToken] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const current = getAdminToken()
    setToken(current)
    setSaved(Boolean(current))
  }, [])

  const handleSave = () => {
    setAdminToken(token)
    setSaved(Boolean(token.trim()))
    window.dispatchEvent(new Event('admin-token-changed'))
  }

  const handleClear = () => {
    clearAdminToken()
    setToken('')
    setSaved(false)
    window.dispatchEvent(new Event('admin-token-changed'))
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-gray-500">
        {saved ? 'Admin token đã lưu' : 'Nhập admin token'}
      </div>
      <input
        type="password"
        className="input-field text-xs py-1.5"
        value={token}
        onChange={(e) => setToken(e.target.value)}
        placeholder="dev-admin-token"
      />
      <div className="flex gap-2">
        <button onClick={handleSave} className="btn-primary text-xs py-1 px-2 flex-1">
          Lưu
        </button>
        <button onClick={handleClear} className="btn-secondary text-xs py-1 px-2 flex-1">
          Xoá
        </button>
      </div>
    </div>
  )
}

function Layout({ children }) {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center text-white text-xl">
              👁️
            </div>
            <div>
              <h1 className="font-bold text-gray-900 text-sm leading-tight">
                Face Attendance
              </h1>
              <p className="text-xs text-gray-500">ArcFace System</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-gray-600 hover:bg-gray-100'
                }`
              }
            >
              <span className="text-lg">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 space-y-4">
          <TokenControl />
          <p className="text-xs text-gray-400 text-center">
            Face Attendance v1.0
          </p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/camera" element={<Camera />} />
          <Route path="/users" element={<UserManagement />} />
          <Route path="/attendance" element={<AttendanceLog />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
