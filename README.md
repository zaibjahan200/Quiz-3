# Selenium Aaj News summarizer (Docker)

This container runs a Flask API that searches Aaj News for a keyword, fetches the first article, summarizes it, and returns JSON on `/get` port `7000`.

Build:

```bash
docker build -t aaj-summarizer:latest .
```

Run (replace REGISTRATION env):

```bash
docker run -e REGISTRATION="YOUR_REG" -p 7000:7000 --shm-size=1g aaj-summarizer:latest
```

Example:

```
http://localhost:7000/get?keyword=election
```

Notes:
- The container installs Google Chrome and uses `webdriver-manager` to obtain a matching chromedriver at runtime.
- Set `REGISTRATION` env var to your registration string before running so API returns correct value.
