"""
Aaj TV News Scraper + Gemini Summarizer
API: GET http://127.0.0.1:7000/get?keyword=pakistan%20army
"""

from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import google.generativeai as genai
import requests
import time
import re
import os

app = Flask(__name__)

# ──────────────────────────────────────────────
# CONFIG  –  set your keys here OR via env vars
# ──────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
REGISTRATION   = "AajTV-Scraper-v1"
NEWS_SOURCE    = "english.aaj.tv"

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")


# ──────────────────────────────────────────────
# SELENIUM  –  headless Chrome driver
# ──────────────────────────────────────────────
def get_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(30)
    return driver


# ──────────────────────────────────────────────
# STEP 1 – Search and extract first valid URL
# ──────────────────────────────────────────────
def search_and_get_url(keyword: str) -> str | None:
    """
    Opens the Aaj TV search page for `keyword`,
    waits for GSC results, then walks through result
    divs until it finds one whose link starts with
    https://english.aaj.tv/news/amp/
    Returns the URL or None.
    """
    query = keyword.replace(" ", "+")
    search_url = (
        f"https://english.aaj.tv/search"
        f"?cx=2102e89c2490c42a7&cof=FORID%3A10&ie=UTF-8&q={query}"
    )

    driver = get_driver()
    try:
        driver.get(search_url)

        # Wait for the GSC results wrapper to appear (up to 15 s)
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "div.gsc-results-wrapper-nooverlay, div.gsc-results-wrapper-visible"
        )))

        # Extra pause so lazy-loaded results finish rendering
        time.sleep(3)

        # Grab every anchor inside the results wrapper
        wrapper = driver.find_element(
            By.CSS_SELECTOR,
            "div.gsc-results-wrapper-nooverlay, div.gsc-results-wrapper-visible"
        )
        anchors = wrapper.find_elements(By.TAG_NAME, "a")

        for anchor in anchors:
            href = anchor.get_attribute("href") or ""
            if href.startswith("https://english.aaj.tv/news/amp/"):
                return href

        return None

    finally:
        driver.quit()


# ──────────────────────────────────────────────
# STEP 2 – Scrape article body text
# ──────────────────────────────────────────────
def scrape_article_text(url: str) -> str:
    """
    Fetches the AMP article page with requests (faster than Selenium
    for a clean AMP page), strips tags, and returns plain text.
    Falls back to Selenium if requests fails.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception:
        # Fallback: use Selenium
        driver = get_driver()
        try:
            driver.get(url)
            time.sleep(3)
            html = driver.page_source
        finally:
            driver.quit()

    # Basic tag stripper (no BeautifulSoup dependency required)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Keep only meaningful characters
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)
    return text[:12000]   # cap at ~12k chars to stay within Gemini limits


# ──────────────────────────────────────────────
# STEP 3 – Summarise with Gemini
# ──────────────────────────────────────────────
def summarise_with_gemini(article_text: str, keyword: str) -> str:
    prompt = (
        f"You are a professional news summarizer. "
        f"The user searched for the keyword: '{keyword}'.\n\n"
        f"Below is the scraped text of a news article from Aaj TV English. "
        f"Write a concise, factual summary of this article in 3-5 sentences. "
        f"Focus only on the key facts and avoid any filler phrases.\n\n"
        f"Article text:\n{article_text}"
    )
    response = gemini_model.generate_content(prompt)
    return response.text.strip()


# ──────────────────────────────────────────────
# FLASK ROUTE
# ──────────────────────────────────────────────
@app.route("/get", methods=["GET"])
def get_news():
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify({"error": "Missing 'keyword' query parameter"}), 400

    try:
        # 1. Search
        article_url = search_and_get_url(keyword)
        if not article_url:
            return jsonify({
                "error": "No matching article found (https://english.aaj.tv/news/amp/…)"
            }), 404

        # 2. Scrape
        article_text = scrape_article_text(article_url)
        if not article_text:
            return jsonify({"error": "Could not extract article text"}), 500

        # 3. Summarise
        summary = summarise_with_gemini(article_text, keyword)

        return jsonify({
            "registration": REGISTRATION,
            "newssource":   NEWS_SOURCE,
            "keyword":      keyword,
            "url":          article_url,
            "summary":      summary,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
if __name__ == "__main__":
    # 0.0.0.0 is required inside Docker so the port is reachable from the host
    app.run(host="0.0.0.0", port=7000, debug=False)
