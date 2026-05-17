import { useEffect, useRef, useState, useCallback } from 'react'
import toast from 'react-hot-toast'
import { buildRecognitionWsUrl } from '../services/api'

export default function Camera() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const wsRef = useRef(null)
  const streamRef = useRef(null)
  const intervalRef = useRef(null)

  const [isConnected, setIsConnected] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [faces, setFaces] = useState([])
  const [fps, setFps] = useState(0)
  const [recentCheckins, setRecentCheckins] = useState([])
  const [facingMode, setFacingMode] = useState('user')
  const [error, setError] = useState(null)

  // Khởi tạo camera
  const startCamera = useCallback(async () => {
    try {
      setError(null)
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode,
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }
    } catch (err) {
      setError('Không thể truy cập camera: ' + err.message)
      console.error('Lỗi camera:', err)
    }
  }, [facingMode])

  // Dừng camera
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
  }, [])

  // Kết nối WebSocket với auto-reconnect
  const reconnectTimeoutRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)
  const maxReconnectAttempts = 10

  // Vẽ bounding boxes lên canvas
  const drawFaces = useCallback((detectedFaces) => {
    const canvas = canvasRef.current
    const video = videoRef.current
    if (!canvas || !video) return

    canvas.width = video.videoWidth || 640
    canvas.height = video.videoHeight || 480
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    detectedFaces.forEach((face) => {
      const [x1, y1, x2, y2] = face.bbox || []
      if (x1 == null) return

      const isKnown = face.name !== 'Unknown' && face.name

      // Vẽ bounding box
      ctx.strokeStyle = isKnown ? '#22c55e' : '#ef4444'
      ctx.lineWidth = 2
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)

      // Vẽ nền cho label
      const label = isKnown
        ? `${face.name} (${(face.confidence * 100).toFixed(0)}%)`
        : 'Unknown'
      ctx.font = '14px Arial'
      const textWidth = ctx.measureText(label).width
      ctx.fillStyle = isKnown
        ? 'rgba(34, 197, 94, 0.85)'
        : 'rgba(239, 68, 68, 0.85)'
      ctx.fillRect(x1, y1 - 24, textWidth + 8, 22)

      // Vẽ text
      ctx.fillStyle = '#ffffff'
      ctx.fillText(label, x1 + 4, y1 - 6)

      // Flash xanh khi check-in
      if (face.checked_in) {
        ctx.fillStyle = 'rgba(34, 197, 94, 0.2)'
        ctx.fillRect(x1, y1, x2 - x1, y2 - y1)
      }
    })
  }, [])

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(buildRecognitionWsUrl())
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      setError(null)
      reconnectAttemptsRef.current = 0
      console.log('WebSocket đã kết nối')
    }

    ws.onclose = () => {
      setIsConnected(false)
      console.log('WebSocket ngắt kết nối')

      // Auto-reconnect với exponential backoff
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        const delay = Math.min(1000 * 2 ** reconnectAttemptsRef.current, 30000)
        reconnectAttemptsRef.current += 1
        console.log(`Reconnect sau ${delay}ms (lần ${reconnectAttemptsRef.current})`)
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, delay)
      }
    }

    ws.onerror = (err) => {
      console.error('WebSocket lỗi:', err)
      setIsConnected(false)
      setError('Không thể kết nối WebSocket. Kiểm tra admin token và backend.')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === 'result') {
          setFaces(data.faces || [])
          setFps(data.fps || 0)

          // Vẽ bounding boxes
          drawFaces(data.faces || [])

          // Thông báo check-in thành công
          data.faces?.forEach((face) => {
            if (face.checked_in && face.name !== 'Unknown') {
              toast.success(`Check-in: ${face.name}`, { duration: 3000 })
              setRecentCheckins((prev) => [
                {
                  name: face.name,
                  confidence: face.confidence,
                  time: new Date().toLocaleTimeString('vi-VN'),
                },
                ...prev.slice(0, 4),
              ])
            }
          })
        }
      } catch (err) {
        console.error('Lỗi parse WebSocket message:', err)
      }
    }
  }, [drawFaces])

  // Bắt đầu gửi frames
  const startStreaming = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      toast.error('Chưa kết nối WebSocket')
      return
    }
    if (!streamRef.current) {
      toast.error('Chưa bật camera')
      return
    }

    setIsStreaming(true)

    intervalRef.current = setInterval(() => {
      const video = videoRef.current
      if (!video || video.readyState < 2) return

      // Capture frame
      const tempCanvas = document.createElement('canvas')
      tempCanvas.width = video.videoWidth || 640
      tempCanvas.height = video.videoHeight || 480
      const ctx = tempCanvas.getContext('2d')
      ctx.drawImage(video, 0, 0)

      // Compress và gửi
      const imageBase64 = tempCanvas.toDataURL('image/jpeg', 0.7)
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'frame', image: imageBase64 }))
      }
    }, 100) // 10 FPS
  }, [])

  // Dừng gửi frames
  const stopStreaming = useCallback(() => {
    setIsStreaming(false)
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    // Xoá canvas
    const canvas = canvasRef.current
    if (canvas) {
      const ctx = canvas.getContext('2d')
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
    setFaces([])
  }, [])

  // Đổi camera
  const switchCamera = useCallback(() => {
    stopStreaming()
    stopCamera()
    setFacingMode((prev) => (prev === 'user' ? 'environment' : 'user'))
  }, [stopStreaming, stopCamera])

  // Khởi tạo khi mount
  useEffect(() => {
    startCamera()
    connectWebSocket()

    const reconnectWithNewToken = () => {
      wsRef.current?.close()
      wsRef.current = null
      reconnectAttemptsRef.current = 0
      connectWebSocket()
    }
    window.addEventListener('admin-token-changed', reconnectWithNewToken)

    return () => {
      stopStreaming()
      stopCamera()
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      window.removeEventListener('admin-token-changed', reconnectWithNewToken)
      wsRef.current?.close()
    }
  }, [connectWebSocket, startCamera, stopCamera, stopStreaming])

  // Khi facingMode thay đổi
  useEffect(() => {
    startCamera()
  }, [facingMode, startCamera])

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Camera Điểm danh</h1>
          <p className="text-gray-500 text-sm mt-1">
            Nhận diện khuôn mặt real-time bằng ArcFace
          </p>
        </div>

        {/* Trạng thái kết nối */}
        <div className="flex items-center gap-2">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
            }`}
          />
          <span className="text-sm text-gray-600">
            {isConnected ? 'Đã kết nối' : 'Chưa kết nối'}
          </span>
          {isStreaming && (
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
              {fps} FPS
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          ⚠️ {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Video stream */}
        <div className="lg:col-span-2">
          <div className="card p-0 overflow-hidden">
            <div className="relative bg-black aspect-video">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover"
              />
              <canvas
                ref={canvasRef}
                className="absolute inset-0 w-full h-full"
                style={{ pointerEvents: 'none' }}
              />

              {/* Overlay khi không stream */}
              {!isStreaming && (
                <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-40">
                  <div className="text-white text-center">
                    <div className="text-5xl mb-3">📷</div>
                    <p className="text-sm">Nhấn &quot;Bắt đầu&quot; để điểm danh</p>
                  </div>
                </div>
              )}
            </div>

            {/* Controls */}
            <div className="p-4 flex items-center gap-3">
              {!isStreaming ? (
                <button onClick={startStreaming} className="btn-primary flex-1">
                  ▶ Bắt đầu nhận diện
                </button>
              ) : (
                <button onClick={stopStreaming} className="btn-danger flex-1">
                  ⏹ Dừng
                </button>
              )}
              <button
                onClick={switchCamera}
                className="btn-secondary px-3"
                title="Đổi camera"
              >
                🔄
              </button>
            </div>
          </div>
        </div>

        {/* Panel thông tin */}
        <div className="space-y-4">
          {/* Thông tin khuôn mặt đang nhận diện */}
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-3">
              Đang nhận diện ({faces.length})
            </h3>
            {faces.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">
                Không có khuôn mặt nào
              </p>
            ) : (
              <div className="space-y-2">
                {faces.map((face, idx) => (
                  <div
                    key={idx}
                    className={`p-3 rounded-lg text-sm ${
                      face.name !== 'Unknown'
                        ? 'bg-green-50 border border-green-200'
                        : 'bg-gray-50 border border-gray-200'
                    }`}
                  >
                    <div className="font-medium">
                      {face.name !== 'Unknown' ? face.name : '👤 Không xác định'}
                    </div>
                    {face.employee_id && (
                      <div className="text-gray-500 text-xs">
                        Mã: {face.employee_id}
                      </div>
                    )}
                    {face.confidence > 0 && (
                      <div className="text-gray-500 text-xs">
                        Độ tin cậy: {(face.confidence * 100).toFixed(1)}%
                      </div>
                    )}
                    {face.checked_in && (
                      <div className="text-green-600 text-xs font-medium mt-1">
                        ✅ Đã check-in
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Lịch sử check-in gần đây */}
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-3">Check-in gần đây</h3>
            {recentCheckins.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">
                Chưa có check-in nào
              </p>
            ) : (
              <div className="space-y-2">
                {recentCheckins.map((checkin, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between text-sm"
                  >
                    <div>
                      <div className="font-medium text-gray-900">{checkin.name}</div>
                      <div className="text-xs text-gray-500">
                        {(checkin.confidence * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div className="text-xs text-gray-400">{checkin.time}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
