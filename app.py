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
import google.generativeai as genai

app = Flask(__name__)

REG = os.getenv('REGISTRATION', 'FA23-BAI-032')
NEWS_SOURCE = "Aaj News"
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyAOu10o81kv9giNXIYwW8lTWs0v8F7dix0')

genai.configure(api_key=GEMINI_API_KEY)


def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--single-process")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
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


def summarize_with_gemini(text, keyword):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""Summarize the following news article in 2-3 sentences. 
Article keyword: {keyword}
Article text:
{text}

Summary:"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error summarizing: {str(e)}"


def build_search_url(keyword):
    encoded = requests.utils.quote(keyword)
    return (
        "https://english.aaj.tv/search?"
        "cx=2102e89c2490c42a7&cof=FORID%3A10&ie=UTF-8"
        f"&q={encoded}"
    )


def find_first_article_link(page_html):
    soup = BeautifulSoup(page_html, 'lxml')
    
    # Save HTML for debugging
    debug_file = os.path.join(os.getcwd(), 'search_results.html')
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(page_html)
    
    print(f"[DEBUG] HTML saved to {debug_file}", flush=True)
    print(f"[DEBUG] HTML length: {len(page_html)}", flush=True)
    
    # Look for Google Custom Search result links (class="gs-title")
    gs_links = soup.find_all('a', class_='gs-title')
    print(f"[DEBUG] Found {len(gs_links)} gs-title links", flush=True)
    
    for i, link in enumerate(gs_links):
        # Try data-ctorig first (original URL)
        href = link.get('data-ctorig', '').strip()
        if not href:
            href = link.get('href', '').strip()
        print(f"[DEBUG] Link {i}: {href[:100] if href else 'EMPTY'}")
        
        if href:
            # Clean up Google redirect URLs if still present
            if 'google.com/url' in href:
                match = re.search(r'q=([^&]+)', href)
                if match:
                    import urllib.parse
                    href = urllib.parse.unquote(match.group(1))
                    print(f"[DEBUG] Cleaned redirect URL: {href[:100]}")
            
            # Make sure it's a valid article URL
            if 'aajenglish.tv' in href or 'aaj.tv' in href:
                # Exclude amp pages and search/archive pages
                if '/amp/' not in href and '/search' not in href:
                    print(f"[DEBUG] Returning article: {href}")
                    return href
    
    # Fallback: look for any news links
    print("[DEBUG] No gs-title found, searching all links...")
    for link in soup.find_all('a'):
        href = link.get('href', '').strip()
        if href and 'aajenglish.tv' in href and '/news/' in href and '/amp/' not in href:
            print(f"[DEBUG] Found fallback link: {href}")
            return href
    
    print("[DEBUG] No article links found!")
    return ''


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

        summary = summarize_with_gemini(text, keyword)

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
