# Multi-stage build for Scrapy crawlers
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libxml2-dev \
    libxslt1-dev \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libxml2 \
    libxslt1.1 \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Chromium for Playwright
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set up the application
WORKDIR /app
COPY . .

# Create non-root user
RUN useradd -m -u 1000 scrapy && chown -R scrapy:scrapy /app
USER scrapy

# Install Playwright browsers
RUN playwright install chromium

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV SCRAPY_SETTINGS_MODULE=labelsquor_crawlers.settings

# Expose Scrapyd port (if using Scrapyd)
EXPOSE 6800

# Default command - can be overridden
CMD ["scrapy", "list"]
