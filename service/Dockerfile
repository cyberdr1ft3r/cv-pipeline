FROM python:3.11-slim

ENV PYTHONDONTWRITEBUFFERED=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Update package lists and install essential system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    file \
    wget \
    gnupg \
    libnss3 \
    libxss1 \
    fonts-liberation \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libasound2 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libcairo2 \
    libffi-dev \
    libjpeg-dev \
    libpng-dev \
    libxslt1.1 \
    libxml2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY service/requirements.txt /app/service/requirements.txt
COPY script/requirements.txt /app/script/requirements.txt

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /app/service/requirements.txt -r /app/script/requirements.txt

# Install Playwright browsers
RUN python -m playwright install chromium

# Keep application changes after dependency/browser layers for repeatable fast rebuilds.
COPY . /app

EXPOSE 8000

CMD ["uvicorn", "service.api:app", "--host", "0.0.0.0", "--port", "8000"]
