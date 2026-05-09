# ─────────────────────────────────────────────────────────────────
# Aaj TV News Scraper – Docker Image
# Base: Python 3.11 slim (Debian Bookworm)
# Includes: Google Chrome stable + matching ChromeDriver + Flask app
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

# Prevent interactive prompts during apt installs
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

# ── Install ChromeDriver that matches the installed Chrome ────────
# Uses the Chrome for Testing JSON endpoint to fetch the right version
RUN CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+\.\d+') \
 && CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d. -f1) \
 && echo "Chrome version: $CHROME_VERSION (major: $CHROME_MAJOR)" \
 && DRIVER_URL=$(curl -sS \
      "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json" \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
versions = data['versions']
target = '$CHROME_VERSION'
major  = '$CHROME_MAJOR'
# Try exact match first, then latest of same major
match = None
for v in reversed(versions):
    ver = v['version']
    dls = v.get('downloads', {}).get('chromedriver', [])
    linux = [d['url'] for d in dls if d['platform'] == 'linux64']
    if not linux:
        continue
    if ver == target:
        match = linux[0]
        break
    if ver.split('.')[0] == major and match is None:
        match = linux[0]
print(match or '')
") \
 && echo "ChromeDriver URL: $DRIVER_URL" \
 && wget -q -O /tmp/chromedriver.zip "$DRIVER_URL" \
 && unzip -q /tmp/chromedriver.zip -d /tmp/chromedriver_extracted \
 && find /tmp/chromedriver_extracted -name "chromedriver" -exec mv {} /usr/local/bin/chromedriver \; \
 && chmod +x /usr/local/bin/chromedriver \
 && rm -rf /tmp/chromedriver.zip /tmp/chromedriver_extracted \
 && chromedriver --version

# ── App working directory ─────────────────────────────────────────
WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────
COPY server.py .

# ── Runtime environment ───────────────────────────────────────────
# GEMINI_API_KEY must be supplied at `docker run` time via -e
ENV GEMINI_API_KEY=""
ENV PYTHONUNBUFFERED=1

# Expose Flask port
EXPOSE 7000

# ── Entrypoint ────────────────────────────────────────────────────
CMD ["python", "server.py"]
