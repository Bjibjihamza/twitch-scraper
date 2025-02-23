import os
import pandas as pd
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ✅ Paths for Data Storage
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
STREAMS_CSV = os.path.join(DATA_DIR, "twitch_streams.csv")
LAST_STREAMS_CSV = os.path.join(DATA_DIR, "last_streams.csv")
LAST_CATEGORIES_CSV = os.path.join(DATA_DIR, "last_categories.csv")  # Path for last_categories.csv

# ✅ Twitch Directory URL for streamers (to be dynamically replaced)
BASE_URL = "https://www.twitch.tv/directory/category/{category}?sort=VIEWER_COUNT"

# ✅ Load Categories from `last_categories.csv`
if not os.path.exists(LAST_CATEGORIES_CSV):
    print("⚠️ No `last_categories.csv` found. Please run the categories scraper first.")
    exit()

try:
    categories_df = pd.read_csv(LAST_CATEGORIES_CSV)
    categories = categories_df['Category'].dropna().unique().tolist()
except Exception as e:
    print(f"❌ Error reading `last_categories.csv`: {e}")
    exit()

# ✅ Create category URLs with lowercase and dashes instead of spaces
category_urls = {
    category.lower().replace(' ', '-') : f"https://www.twitch.tv/directory/category/{category.lower().replace(' ', '-')}?sort=VIEWER_COUNT"
    for category in categories
}

# ✅ WebDriver Setup
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ✅ Helper Functions
def scroll_to_load_more():
    """Scroll down the page to load more streamers."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(5):  # Scroll 5 times to load more content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def convert_viewers_count(viewers_text):
    """Convert Twitch viewers count from '299K' or '20.7000' format to an integer."""
    viewers_text = viewers_text.replace(" viewers", "").replace(",", "").strip()  # Clean text
    if "K" in viewers_text:
        return int(float(viewers_text.replace("K", "")) * 1000)  # Convert '299K' to 299000
    if "." in viewers_text:  # Handle formats like '20.7000'
        return int(float(viewers_text) * 1000)
    return int(viewers_text) if viewers_text.isdigit() else 0

def save_to_csv(data, file_path, overwrite=False):
    """Save data to CSV, overwriting or appending."""
    df = pd.DataFrame(data, columns=['Timestamp', 'Category', 'Stream Title', 'Channel', 'Viewers', 'Tags'])
    mode = 'w' if overwrite else 'a'
    header = overwrite or not os.path.exists(file_path)
    df.to_csv(file_path, mode=mode, header=header, index=False, encoding="utf-8")
    print(f"✅ Data saved to `{file_path}`.")

# ✅ Scraper Function for streamers
def scrape_twitch_category(category, url):
    """Scrape streamers from a Twitch category page and store the data."""
    print(f"📡 Scraping {category} - {url}")
    driver.get(url)
    time.sleep(3)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//h3[contains(@class, "CoreText")]'))
        )

        # ✅ Scrape Streamers
        streamers = driver.find_elements(By.XPATH, '//h3[contains(@class, "CoreText")]')
        streamer_names = [s.text for s in streamers if s.text.strip()]

        channels = driver.find_elements(By.XPATH, '//div[contains(@class, "Layout-sc-1xcs6mc-0 bQImNn")]')
        channel_names = [c.text for c in channels if c.text.strip()]

        viewers = driver.find_elements(By.XPATH, '//div[contains(@class, "ScMediaCardStatWrapper")]')
        viewers_counts = [convert_viewers_count(v.text) for v in viewers if v.text.strip()]

        tags = driver.find_elements(By.XPATH, '//button[contains(@class, "ScTag")]')
        tags_list = [t.text for t in tags if t.text.strip()]

        # ✅ Ensure Minimum Length
        min_length = min(len(streamer_names), len(channel_names), len(viewers_counts), len(tags_list))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ✅ Structure Data
        data = [{
            "Timestamp": timestamp,
            "Category": category,
            "Stream Title": streamer_names[i],
            "Channel": channel_names[i],
            "Viewers": viewers_counts[i],
            "Tags": tags_list[i]
        } for i in range(min_length)]

        print(f"✅ Data scraped for category: {category}")
        return data

    except Exception as e:
        print(f"❌ Error scraping {category}: {e}")
        return []

# ✅ Scrape All Categories from `last_categories.csv`
all_last_streams = []
for category in categories:
    category_url = BASE_URL.format(category=category.lower().replace(' ', '-'))  # Construct the URL for each category
    all_last_streams.extend(scrape_twitch_category(category, category_url))

# ✅ Store All Scraped Data to `last_streams.csv`
save_to_csv(all_last_streams, LAST_STREAMS_CSV, overwrite=True)  # Overwrite `last_streams.csv` with all data

# ✅ Append All Scraped Data to `twitch_streams.csv`
save_to_csv(all_last_streams, STREAMS_CSV, overwrite=False)  # Append all data to `twitch_streams.csv`

# 🔴 Close WebDriver
driver.quit()
print("✅ Streamers extraction completed!")
