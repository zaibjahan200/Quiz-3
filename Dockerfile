# ─────────────────────────────────────────────────────────────────
# Aaj TV News Scraper – Docker Image
# Base: Python 3.11 slim (Debian Bookworm)
# Includes: Google Chrome stable + matching ChromeDriver + Flask app
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# ── System deps: Chrome prerequisites ────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gnupg \
    ca-certificates \
    unzip \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxkbcommon0 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# ── Install Google Chrome stable ─────────────────────────────────
RUN wget -q -O /tmp/chrome.deb \
    https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
 && apt-get update \
 && apt-get install -y --no-install-recommends /tmp/chrome.deb \
 && rm /tmp/chrome.deb \
 && rm -rf /var/lib/apt/lists/*

# ── Install matching ChromeDriver via helper script ───────────────
COPY get_chromedriver_url.py /tmp/get_chromedriver_url.py

RUN CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+\.\d+') \
 && echo "Detected Chrome: $CHROME_VERSION" \
 && DRIVER_URL=$(python3 /tmp/get_chromedriver_url.py "$CHROME_VERSION") \
 && echo "Downloading ChromeDriver from: $DRIVER_URL" \
 && wget -q -O /tmp/chromedriver.zip "$DRIVER_URL" \
 && unzip -q /tmp/chromedriver.zip -d /tmp/chromedriver_extracted \
 && find /tmp/chromedriver_extracted -name "chromedriver" -exec mv {} /usr/local/bin/chromedriver \; \
 && chmod +x /usr/local/bin/chromedriver \
 && rm -rf /tmp/chromedriver.zip /tmp/chromedriver_extracted /tmp/get_chromedriver_url.py \
 && chromedriver --version

# ── App working directory ─────────────────────────────────────────
WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────
COPY server.py .

# ── Runtime environment ───────────────────────────────────────────
ENV GEMINI_API_KEY=""
ENV PYTHONUNBUFFERED=1

EXPOSE 7000

CMD ["python", "server.py"]
