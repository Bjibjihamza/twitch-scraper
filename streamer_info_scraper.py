import os
import re
import pandas as pd
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ✅ Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ✅ Define correct paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LAST_STREAMS_FILE = os.path.join(DATA_DIR, "last_streams.csv")  # Input Data
STREAMERS_DATA_DIR = os.path.join(DATA_DIR, "streamers_data")  # Individual files per streamer
FINAL_STREAMERS_FILE = os.path.join(DATA_DIR, "final_streamers_data.csv")  # Output Data

os.makedirs(STREAMERS_DATA_DIR, exist_ok=True)  # Ensure folder exists

# ✅ Load last_streams.csv
if not os.path.exists(LAST_STREAMS_FILE):
    logging.error(f"⚠️ '{LAST_STREAMS_FILE}' not found! Run the streamers scraper first.")
    exit()

df_last_streams = pd.read_csv(LAST_STREAMS_FILE).drop(columns=["Viewers"], errors="ignore")  # Remove old "Viewers"
logging.info(f"✅ Loaded {len(df_last_streams)} streamers from {LAST_STREAMS_FILE}.")

# ✅ Initialize WebDriver
def init_driver():
    """Initialize a new WebDriver instance."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--mute-audio")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ✅ Scrape Streamer Data
def scrape_streamer(streamer_name):
    """Scrape Goals (Followers & Subs) including current numbers, total followers, and tags."""
    driver = init_driver()
    streamer_url = f"https://www.twitch.tv/{streamer_name}"
    
    logging.info(f"🔗 Visiting URL: {streamer_url}")
    
    driver.get(streamer_url)
    time.sleep(3)  # Ensure page loads properly

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # ✅ Extract scraped timestamp
        scraped_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ✅ Extract Total Followers
        try:
            followers_element = driver.find_element(By.XPATH, '//div[contains(@class, "Layout-sc-1xcs6mc-0 hsXgFK")]/span')
            total_followers = followers_element.text.strip()
            logging.info(f"✅ Extracted Total Followers: {total_followers}")
        except:
            total_followers = "Unknown"

        # ✅ Extract All Tags (Fixed)
        try:
            # ✅ Scroll down to trigger Twitch to load all elements
            driver.execute_script("window.scrollBy(0, 600);")
            time.sleep(2)  # Give time for lazy-loading

            # ✅ Wait longer for tags (15 sec max)
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.XPATH, '//a[contains(@class, "tw-tag")]/div/span'))
            )

            # ✅ Find all tags
            tag_elements = driver.find_elements(By.XPATH, '//a[contains(@class, "tw-tag")]/div/span')

            if not tag_elements:
                logging.warning(f"⚠️ No tags found for {streamer_name}. Debugging...")

                # ✅ Save page source for debugging
                with open(f"debug_{streamer_name}.html", "w", encoding="utf-8") as debug_file:
                    debug_file.write(driver.page_source)

                logging.info(f"🔍 Page source saved to debug_{streamer_name}.html. Check for missing elements.")

            # ✅ Extract tag text
            tags = [tag.text.strip() for tag in tag_elements if tag.text.strip()]
            tags_string = ", ".join(tags) if tags else "No Tags"

            logging.info(f"✅ Extracted Tags: {tags_string}")

        except Exception as e:
            logging.warning(f"⚠️ Could not extract tags for {streamer_name}: {e}")
            tags_string = "No Tags"

        # ✅ Detect Goals Sections
        goals_sections = driver.find_elements(By.XPATH, '//div[@aria-label="Follower Goal" or @aria-label="Sub Goal"]')
        num_goals = len(goals_sections)

        logging.info(f"🔍 Detected {num_goals} goal sections for {streamer_name}.")

        followers_goal = "No Goal"
        subs_goal = "No Goal"
        current_subscribers = "Unknown"

        for section in goals_sections:
            try:
                goal_type = section.get_attribute("aria-label")  # "Follower Goal" or "Sub Goal"
                goal_text_element = section.find_element(By.XPATH, './/p[contains(@class, "CoreText-sc-1txzju1-0 hpgLVq")]')

                # ✅ Extract both numbers (current & goal)
                spans = goal_text_element.find_elements(By.TAG_NAME, "span")

                if len(spans) >= 2:
                    current_number = spans[0].text.strip()  # First span = current number
                    goal_number = spans[1].text.strip().split(" ")[0]  # Second span = goal number (remove 'Subs' text)

                # ✅ Assign to the correct field
                if goal_type == "Follower Goal":
                    followers_goal = f"{current_number}/{goal_number}"
                elif goal_type == "Sub Goal":
                    subs_goal = goal_number
                    current_subscribers = current_number

                logging.info(f"✅ Extracted {goal_type}: {current_number}/{goal_number}")

            except Exception as e:
                logging.warning(f"⚠️ Could not extract goal text: {e}")

        driver.quit()

        # ✅ Format Data
        streamer_data = {
            "Timestamp": scraped_timestamp,
            "Channel": streamer_name,
            "Total Followers": total_followers,
            "Tags": tags_string,  # ✅ Correctly extracted as a list
            "Followers Goal": followers_goal,
            "Subs Goal": subs_goal,
            "Current Subscribers": current_subscribers
        }

        return streamer_data

    except Exception as e:
        logging.error(f"⚠️ Error scraping {streamer_name}: {e}")
        driver.quit()
        return None

# ✅ Scrape all streamers & save individual files
scraped_data = []

for index, row in df_last_streams.iterrows():
    streamer_name = row['Channel']
    streamer_file = os.path.join(STREAMERS_DATA_DIR, f"{streamer_name}.csv")

    streamer_data = scrape_streamer(streamer_name)

    if streamer_data:
        scraped_data.append(streamer_data)

        # ✅ Merge Streamer Metadata (Category, Stream Title, Tags)
        streamer_metadata = df_last_streams[df_last_streams["Channel"] == streamer_name].iloc[0].to_dict()
        merged_streamer_data = {**streamer_metadata, **streamer_data}  # Combine metadata + scraped data

        # ✅ Ensure all columns match final_streamers_data.csv
        file_exists = os.path.exists(streamer_file)
        pd.DataFrame([merged_streamer_data]).to_csv(
            streamer_file, mode='a', header=not file_exists, index=False, encoding="utf-8"
        )
        logging.info(f"✅ Data saved for {streamer_name} in {streamer_file}")

# ✅ Convert scraped data to DataFrame
df_scraped = pd.DataFrame(scraped_data)

# ✅ Merge Scraped Data with last_streams.csv
df_final = df_last_streams.merge(df_scraped, on="Channel", how="left")

# ✅ Save final merged data
df_final.to_csv(FINAL_STREAMERS_FILE, index=False, encoding="utf-8")
logging.info(f"📁 Final merged data saved to {FINAL_STREAMERS_FILE}.")

logging.info("✅ Streamer data extraction & merging completed!")
