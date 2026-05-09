from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import os
import re
import requests

app = Flask(__name__)

REG = os.getenv('REGISTRATION', 'FA23-BAI-032')
NEWS_SOURCE = "Aaj News"


def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-features=VizDisplayCompositor")
    # Use Selenium Manager (bundled with selenium) to locate/start compatible driver
    # This avoids webdriver-manager network issues fetching an incompatible release.
    try:
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e:
        # Provide a clear error so caller can decide how to proceed.
        raise RuntimeError(
            "Failed to start Chrome via Selenium Manager. \n"
            "Please ensure Chrome is installed and a compatible chromedriver is available, "
            "or run inside the provided Docker image where Chrome+driver are installed. "
            f"Original error: {e}"
        )


def summarize_text(text, max_sentences=3):
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return ' '.join(sentences[:max_sentences]).strip()


def build_search_url(keyword):
    encoded = requests.utils.quote(keyword)
    return (
        "https://english.aaj.tv/search?"
        "cx=2102e89c2490c42a7&cof=FORID%3A10&ie=UTF-8"
        f"&q={encoded}"
    )


def is_article_url(href):
    if not href:
        return False
    if 'english.aaj.tv' not in href and 'aaj.tv' not in href:
        return False
    blocked = ['/search', '/tag/', '/category/', '/author/', '/authors/', '/live', '/video', '/podcasts']
    if any(part in href for part in blocked):
        return False
    return bool(re.search(r'/20\d{2}/', href) or '/news/' in href)


def find_first_article_link(page_html):
    soup = BeautifulSoup(page_html, 'lxml')
    candidates = []
    for a in soup.select('a[href]'):
        href = a.get('href', '').strip()
        text = a.get_text(' ', strip=True)
        if href.startswith('/'):
            href = f"https://english.aaj.tv{href}"
        if is_article_url(href):
            candidates.append((href, text))
    for href, text in candidates:
        if text and len(text) > 20:
            return href
    return candidates[0][0] if candidates else ''


@app.route('/get', methods=['GET'])
def get_article_summary():
    keyword = request.args.get('keyword')
    if not keyword:
        return jsonify({'error': 'keyword query parameter is required'}), 400

    driver = create_driver()
    article_url = ''
    summary = ''
    try:
        # Primary flow: open homepage, click search button, type in textbox, submit.
        driver.get('https://english.aaj.tv')
        wait = WebDriverWait(driver, 10)
        try:
            search_btn = wait.until(EC.element_to_be_clickable((By.ID, 'search-button')))
            search_btn.click()
            input_box = wait.until(EC.presence_of_element_located((By.NAME, 'q')))
            input_box.clear()
            input_box.send_keys(keyword)
            input_box.send_keys(Keys.ENTER)
            time.sleep(2)
        except Exception:
            # Fallback to direct search URL provided by the user.
            driver.get(build_search_url(keyword))
            time.sleep(2)

        article_url = find_first_article_link(driver.page_source)

        if not article_url:
            # Last fallback to WordPress style query on same domain.
            driver.get(f"https://english.aaj.tv/?s={requests.utils.quote(keyword)}")
            time.sleep(2)
            article_url = find_first_article_link(driver.page_source)

        if not article_url:
            return jsonify({'error': 'could not find article for keyword on Aaj News'}), 404

        # Open article and extract text
        driver.get(article_url)
        time.sleep(2)
        title = ''
        try:
            title = driver.find_element(By.TAG_NAME, 'h1').text.strip()
        except Exception:
            title = ''
        paragraphs = driver.find_elements("tag name", "p")
        text = ' '.join([p.text for p in paragraphs if p.text])

        if not text.strip():
            # fallback to requests + BeautifulSoup
            resp = requests.get(article_url, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(resp.text, 'lxml')
            paras = soup.find_all('p')
            text = ' '.join([p.get_text() for p in paras])

        summary_core = summarize_text(text)
        summary = f"{title}. {summary_core}".strip('. ').strip() if title else summary_core

        result = {
            'registration': REG,
            'newssource': NEWS_SOURCE,
            'keyword': keyword,
            'url': article_url,
            'summary': summary
        }

        return jsonify(result)

    except RuntimeError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)
