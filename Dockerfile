# Use Python 3.9 slim image
FROM python:3.9-slim

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
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
# Use wget to download key, verify it exists, then process
RUN mkdir -p /usr/share/keyrings \
    && (wget -q --timeout=10 --tries=3 -O /tmp/chrome-key.pub https://dl-ssl.google.com/linux/linux_signing_key.pub \
        || wget -q --timeout=10 --tries=3 -O /tmp/chrome-key.pub https://dl.google.com/linux/linux_signing_key.pub) \
    && test -s /tmp/chrome-key.pub \
    && gpg --dearmor < /tmp/chrome-key.pub > /usr/share/keyrings/google-chrome.gpg \
    && rm -f /tmp/chrome-key.pub \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy application code
COPY . .

# Create directory for database and logs
RUN mkdir -p data logs

# Expose port
EXPOSE 5000

# Default command (can be overridden)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "webapp.app:create_app()"]
