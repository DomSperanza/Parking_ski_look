# Use Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    ca-certificates \
    unzip \
    xvfb \
    libnss3 \
    libfontconfig1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libnspr4 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome for Testing (v144) to ensure compatibility
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/144.0.7559.133/linux64/chrome-linux64.zip \
    && unzip chrome-linux64.zip \
    && mv chrome-linux64 /opt/chrome-for-testing \
    && ln -s /opt/chrome-for-testing/chrome /usr/bin/google-chrome \
    && rm chrome-linux64.zip

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy application code
COPY . .

# Create directory for database, logs, and Chrome profile with proper permissions
RUN mkdir -p data logs chrome_profile && \
    chmod -R 777 chrome_profile data logs

# Expose port
EXPOSE 5000

# Default command (can be overridden)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "webapp.app:create_app()"]
