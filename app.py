from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import quote_plus

app = Flask(__name__)

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=chrome_options)

BASE_URL = "https://english.aaj.tv/search?cx=2102e89c2490c42a7&cof=FORID%3A10&ie=UTF-8&q="


@app.route("/get")
def get_news():

    keyword = request.args.get("keyword", "").strip()

    if not keyword:
        return jsonify({"error": "keyword required"}), 400

    url = BASE_URL + quote_plus(keyword)

    driver.get(url)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".gsc-webResult")
        )
    )

    results = driver.find_elements(By.CSS_SELECTOR, ".gsc-webResult")

    news_url = ""
    summary = ""

    for result in results:

        try:
            link = result.find_element(
                By.CSS_SELECTOR,
                "a.gs-title"
            )

            href = link.get_attribute("href")

            print(href)

            if href and "/news/" in href:

                news_url = href

                try:
                    summary = result.find_element(
                        By.CSS_SELECTOR,
                        ".gs-bidi-start-align.gs-snippet"
                    ).text.strip()

                except:
                    summary = ""

                break

        except Exception as e:
            print(e)

    if not news_url:
        return jsonify({
            "registration": "",
            "newssource": "Aaj English",
            "keyword": keyword,
            "url": "",
            "summary": "No matching news found"
        })

    return jsonify({
        "registration": "",
        "newssource": "Aaj English",
        "keyword": keyword,
        "url": news_url,
        "summary": summary
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)