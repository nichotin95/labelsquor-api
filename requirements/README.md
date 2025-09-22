# Requirements Structure

This directory contains modular requirement files for different components of the LabelSquor API.

## Files

- **base.txt** - Core API dependencies (FastAPI, database, auth)
- **crawler.txt** - Web scraping dependencies (Scrapy, Playwright)
- **ml.txt** - Machine Learning dependencies (PyTorch, Transformers)
- **dev.txt** - Development tools (testing, linting, debugging)
- **production.txt** - Production-specific dependencies (monitoring, APM)

## Installation

### For API development (minimal):
```bash
pip install -r base.txt
```

### For crawler development:
```bash
pip install -r base.txt -r crawler.txt
```

### For ML development:
```bash
pip install -r base.txt -r ml.txt
```

### For full development environment:
```bash
pip install -r dev.txt -r ../requirements.txt
```

### For production deployment:
```bash
pip install -r base.txt -r production.txt
```

## Notes

- The main `requirements.txt` in the parent directory includes base + crawler + ml
- Use modular installations to reduce Docker image size and deployment time
- ML dependencies add ~2.5GB due to PyTorch
- Base API needs only ~150MB
