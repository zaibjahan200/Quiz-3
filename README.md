# Aaj TV News Scraper API — Docker Edition

Scrapes `english.aaj.tv` via Selenium (headless Chrome), extracts the first
matching AMP article, summarises it with Gemini 1.5 Flash, and serves the
result over a local HTTP API.

Everything — Python, Chrome, ChromeDriver — runs inside Docker.
No local installs needed beyond Docker itself.

---

## Project layout

```
aaj_news_api/
├── Dockerfile          ← builds the image (Chrome + Python + app)
├── docker-compose.yml  ← one-command run
├── server.py           ← Flask app
├── requirements.txt    ← Python deps
├── .env.example        ← copy to .env and add your Gemini key
└── .dockerignore
```

---

## Quick Start

### 1. Add your Gemini API key
```bash
cp .env.example .env
# then edit .env and paste your key
# Get one free at https://aistudio.google.com/app/apikey
```

### 2. Build & run
```bash
docker compose up --build
```
First build takes ~3-4 minutes (downloads Chrome). Subsequent starts are instant.

### 3. Test it
```bash
curl "http://127.0.0.1:7000/get?keyword=pakistan%20army"
```

---

## Alternative: plain Docker (no compose)

```bash
# Build
docker build -t aaj-scraper .

# Run
docker run -d \
  -p 7000:7000 \
  --shm-size=256m \
  -e GEMINI_API_KEY=your_key_here \
  --name aaj_news_scraper \
  aaj-scraper
```

---

## API

### GET /get?keyword=<query>

#### Success response 200
```json
{
  "registration": "AajTV-Scraper-v1",
  "newssource":   "english.aaj.tv",
  "keyword":      "pakistan army",
  "url":          "https://english.aaj.tv/news/amp/330012345",
  "summary":      "Pakistan's army conducted a joint operation in..."
}
```

---

## Useful Docker commands

```bash
docker compose logs -f          # live logs
docker compose down             # stop
docker compose up --build       # rebuild after code changes
docker exec -it aaj_news_scraper bash  # shell inside container
```

## Notes
- shm_size 256mb is required — headless Chrome crashes without shared memory.
- Flask binds to 0.0.0.0 inside the container; Docker maps it to localhost:7000.
