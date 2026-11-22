# Multi-platform Dockerfile for KrshiBandhu
# Supports AMD64 and ARM64 (Raspberry Pi 4/5, Cloud VMs, Render, Railway, Hugging Face)
FROM python:3.11-slim

# Prevent Python from writing .pyc and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV HOST=0.0.0.0
ENV NO_BROWSER=true

# Install system audio, video, and GL dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libasound2 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch CPU build first (smaller image, avoids heavy CUDA binaries)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install application dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose default HTTP ports
EXPOSE 8000 7860

# Launch KrshiBandhu bound to all interfaces
CMD ["python", "run.py", "--host", "0.0.0.0"]
