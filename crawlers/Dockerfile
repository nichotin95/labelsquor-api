# Crawler service with anti-blocking for GCP
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy crawler requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy crawler code
COPY . .

# Set environment variables for GCP
ENV SCRAPY_SETTINGS_MODULE=labelsquor_crawlers.settings_gcp
ENV PYTHONPATH=/app

# Health check endpoint
EXPOSE 8080

# Run the crawler service
CMD ["python", "crawler_service.py"]