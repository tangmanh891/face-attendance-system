# Multi-stage build cho Backend FastAPI
# Stage 1: Build
FROM python:3.11-slim AS builder

WORKDIR /app

# Cài đặt các dependencies hệ thống cần thiết cho OpenCV và InsightFace
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

# Cài đặt các runtime dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages từ builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code
COPY . .

# Tạo user non-root cho bảo mật
RUN useradd -m -u 1000 appuser

# Tạo thư mục upload với quyền cho appuser
RUN mkdir -p uploads/faces uploads/checkins uploads/checkouts && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Khởi động ứng dụng
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
