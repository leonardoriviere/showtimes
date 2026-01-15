from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import quote_plus
import json
import sys
from pathlib import Path
import logging
import argparse
import time
import re
import unicodedata


WORD_PATTERN = re.compile(r"([^\W\d_]+(?:['’][^\W\d_]+)*)", re.UNICODE)


def _strip_accents(text: str) -> str:
    """Remove diacritics from a piece of text."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _capitalize_word(word: str) -> str:
    """Capitalize the first alphabetical character in a word."""
    for index, char in enumerate(word):
        if char.isalpha():
            return word[:index] + char.upper() + word[index + 1:]
    return word


def _normalize_word(token: str) -> str:
    """Normalize an individual token that represents a word."""
    if token.isupper() and len(token) > 1:
        # Preserve acronyms such as IMAX or BTS.
        return token

    letters = [(index, char) for index, char in enumerate(token) if char.isalpha()]
    candidate = token

    if letters:
        has_internal_uppercase = any(char.isupper() for _, char in letters[1:])

        # If there are uppercase letters beyond the first alphabetical character
        # the word was likely scraped with inconsistent casing (e.g. "ÁNgelo").
        # Strip accents so the normalized capitalization does not keep stray
        # diacritics in these situations.
        if has_internal_uppercase:
            candidate = _strip_accents(candidate)

    candidate = candidate.lower()
    return _capitalize_word(candidate)


def normalize_movie_title(title: str) -> str:
    """Normalize movie titles by fixing inconsistent casing automatically."""

    def replace(match: re.Match) -> str:
        return _normalize_word(match.group(0))

    stripped = title.strip()
    return WORD_PATTERN.sub(replace, stripped)

def convert_showcase_duration_to_minutes(duration_str):
    """Converts a duration string from '170 minutos' to an integer representing total minutes."""
    minutes = int(duration_str.split()[0])  # Split the string and convert the first part to an integer
    return minutes


def convert_imdb_duration_to_minutes(duration_str):
    """Converts a duration string from '2h 50m' to an integer representing total minutes."""
    parts = duration_str.split()
    minutes = 0
    for part in parts:
        if 'h' in part:
            minutes += int(part.replace('h', '')) * 60
        elif 'm' in part:
            minutes += int(part.replace('m', ''))
    return minutes


class MovieScraper:
    def __init__(self, chromedriver_path=None):
        # Configure logging
        self.logger = logging.getLogger(__name__)

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument("--headless=new")  # Run headless (modern flag)
        chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration (for headless)
        chrome_options.add_argument("--no-sandbox")  # Bypass OS security model
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems

        # Initialize WebDriver
        try:
            self.logger.info("Initializing WebDriver...")
            if chromedriver_path:
                self.logger.info(f"Using ChromeDriver from path: {chromedriver_path}")
                service = Service(executable_path=chromedriver_path)
            else:
                self.logger.info("Using ChromeDriver managed by ChromeDriverManager.")
                service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(600000)
            self.logger.info("WebDriver initialized successfully.")
        except Exception as e:
            self.logger.error(f"Error initializing WebDriver: {e}")
            raise

    def scrape_movie_data(self, base_url):
        self.driver.get(base_url)
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#cartelera_cine_40212 > .boxfilm > .afiche-pelicula > a'))
        )
        movies_links = self.driver.find_elements(By.CSS_SELECTOR, '#cartelera_cine_40212 > .boxfilm > '
                                                                  '.afiche-pelicula > a')
        movie_hrefs = [link.get_attribute('href') for link in movies_links]
        return movie_hrefs

    def scrape_movie_details(self, href):
        self.driver.get(href)
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.op_format'))
        )
        title = self.driver.find_element(By.CSS_SELECTOR, '.movie-info-box .name > strong').text
        title = normalize_movie_title(title)
        poster_url = self.driver.find_element(By.CSS_SELECTOR, '.movie-side-info-box figure > img').get_attribute('src')
        original_title = self.driver.find_element(By.CSS_SELECTOR, '.movie-side-info-box ul > li:first-of-type').text
        original_title = original_title.replace('Título Original: ', '')  # Remove the prefix
        duration = self.driver.find_element(By.CSS_SELECTOR, '.movie-info-box ul.features .year').text
        showing_days = [button.get_attribute('value') for button in
                        self.driver.find_elements(By.CSS_SELECTOR, '.movie-info-box .op_days > button')]

        showtimes_by_format = self.extract_showtimes()

        movie_info = {
            'title': title,
            'href': href,
            'original_title': original_title,
            'poster_url': poster_url,
            'duration': duration,
            'showing_days': showing_days,
            'showtimes': showtimes_by_format
        }

        # Fetch the IMDb URL using the original title
        imdb_url = self.get_imdb_url(original_title)
        # Fetch additional IMDb information (rating and votes)
        imdb_info = self.scrape_imdb_info(imdb_url, movie_info['duration'])

        # Update movie_info dictionary to include the IMDb URL and additional IMDb information
        movie_info.update({
            'imdb_url': imdb_url,
            **imdb_info  # This unpacks the imdb_info dictionary and adds its keys and values to movie_info
        })

        return movie_info

    @staticmethod
    def _build_imdb_search_url(original_title: str) -> str:
        query = original_title.strip()
        if not query:
            return "IMDb URL not found"

        return "https://www.imdb.com/find/?q=" + quote_plus(query)

    def get_imdb_url(self, original_title, max_retries=2):
        search_url = self._build_imdb_search_url(original_title)
        if search_url == "IMDb URL not found":
            return search_url

        for attempt in range(max_retries):
            try:
                self.driver.get(search_url)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="find-results-section-title"]'))
                )
                first_result = self.driver.find_element(
                    By.CSS_SELECTOR,
                    '[data-testid="find-results-section-title"] .ipc-metadata-list-summary-item a'
                )
                href = first_result.get_attribute('href')
                if href and '/title/tt' in href:
                    match = re.search(r'/title/(tt\d+)', href)
                    if match:
                        return f"https://www.imdb.com/title/{match.group(1)}/"
                return search_url
            except Exception as exc:
                self.logger.warning(
                    "IMDb search attempt %d/%d failed for '%s': %s",
                    attempt + 1, max_retries, original_title, exc
                )
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
        return search_url

    def scrape_imdb_info(self, imdb_url, showcase_duration):
        """Scrape IMDb rating and metascore for a movie.
        
        Duration validation: accepts if within 5 minutes tolerance.
        This helps match movies where Showcase/IMDb have slight duration differences.
        """
        if not imdb_url.startswith('https://www.imdb.com/title/tt'):
            if imdb_url.startswith('https://www.imdb.com/find/?q='):
                self.logger.info("Skipping IMDb scraping for search URL: %s", imdb_url)
            else:
                self.logger.error("Invalid IMDb URL: %s", imdb_url)
            return {'imdb_rating': 'N/A', 'metascore': 'N/A', 'imdb_duration': 'N/A'}
        
        self.driver.get(imdb_url)
        imdb_info = {'imdb_rating': 'N/A', 'metascore': 'N/A', 'imdb_duration': 'N/A'}

        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="hero__pageTitle"]'))
            )
            
            # Get IMDb duration
            try:
                imdb_duration_str = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    '[data-testid="hero__pageTitle"] ~ ul[role="presentation"] > li:last-of-type'
                ).text
            except Exception:
                self.logger.warning("Duration not found for: %s", imdb_url)
                return imdb_info

            imdb_info['imdb_duration'] = imdb_duration_str
            
            # Parse durations for comparison
            try:
                imdb_minutes = convert_imdb_duration_to_minutes(imdb_duration_str)
                showcase_minutes = convert_showcase_duration_to_minutes(showcase_duration)
                duration_diff = abs(imdb_minutes - showcase_minutes)
            except (ValueError, AttributeError) as e:
                self.logger.warning("Could not parse duration: %s", e)
                duration_diff = 999  # Force mismatch
            
            # Accept if durations are within 10 minutes (accounts for credits, regional cuts, etc.)
            if duration_diff <= 10:
                self._scrape_ratings(imdb_info)
            else:
                self.logger.warning(
                    "Duration mismatch: IMDb=%s (%dm) vs Showcase=%s (%dm), diff=%dm - skipping ratings",
                    imdb_duration_str, imdb_minutes, showcase_duration, showcase_minutes, duration_diff
                )
                
        except Exception as e:
            self.logger.error("Error scraping IMDb info: %s", e)

        return imdb_info
    
    def _scrape_ratings(self, imdb_info):
        """Extract IMDb rating and Metascore from current page."""
        try:
            rating_element = self.driver.find_element(
                By.CSS_SELECTOR,
                'div[data-testid="hero-rating-bar__aggregate-rating__score"] > span:first-of-type'
            )
            imdb_info['imdb_rating'] = rating_element.get_attribute('innerHTML')
        except Exception:
            pass
        
        try:
            metascore_element = self.driver.find_element(
                By.CSS_SELECTOR, 'span.metacritic-score-box'
            )
            imdb_info['metascore'] = metascore_element.text
        except Exception:
            pass

    def extract_showtimes(self):
        showtimes = {}
        # Find all day selectors and iterate through them
        day_selectors = self.driver.find_elements(By.CSS_SELECTOR, '.movie-info-box #op_container .op_days .op_day')
        for day_selector in day_selectors:
            # Extract the date from the day_selector, assuming it's in a format you can use directly
            date = day_selector.get_attribute('value')  # Adjust attribute name as necessary

            # Click the day selector to load the showtimes for that day
            self.driver.execute_script("arguments[0].click();", day_selector)

            # Wait for the showtimes to be loaded. Adjust the wait condition as needed.
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.op_format'))
            )

            # Now, extract the showtimes for this day. This part depends on your page structure.
            # You might need to first group by format, then extract times.
            showtimes_for_day = {}
            format_elements = self.driver.find_elements(By.CSS_SELECTOR, '.op_format')
            for format_element in format_elements:
                format_type = format_element.get_attribute('innerHTML').strip()
                time_container = format_element.find_element(By.XPATH, './following-sibling::div')
                time_elements = time_container.find_elements(By.CSS_SELECTOR, 'button.op_perf')
                times = [time_element.get_attribute('innerHTML').strip() for time_element in time_elements]
                showtimes_for_day[format_type] = times

            # Add the showtimes for the day to the main dictionary
            showtimes[date] = showtimes_for_day

            # Add any necessary logic to handle navigation or refresh issues between clicks

        return showtimes

    def close(self):
        self.driver.quit()

    def save_data_to_json(self, data):
        """Saves the scraped data to a JSON file."""
        base_dir = Path(__file__).resolve().parent  # Get the directory of the current script
        json_path = base_dir / ".." / "docs" / "data.json"  # Construct the dynamic path to data.json

        with open(json_path, 'w') as jsonfile:
            json.dump(data, jsonfile, indent=4)


if __name__ == "__main__":
    # Argument parser setup
    parser = argparse.ArgumentParser(description='Scrape movie showtimes.')
    parser.add_argument('--chromedriver-path', type=str, help='Path to the ChromeDriver executable')
    args = parser.parse_args()

    # Configure logging to both file and stdout (useful for CI)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scraper.log', mode='a'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    scraper = MovieScraper(chromedriver_path=args.chromedriver_path)
    base_url = 'https://www.todoshowcase.com/'
    movie_hrefs = scraper.scrape_movie_data(base_url)

    all_movies_details = []  # List to store details of all movies
    logger = logging.getLogger(__name__)

    # Loop through all movie URLs and scrape their details
    for idx, href in enumerate(movie_hrefs, 1):
        try:
            logger.info(f"Scraping movie {idx}/{len(movie_hrefs)}: {href}")
            movie_details = scraper.scrape_movie_details(href)
            all_movies_details.append(movie_details)
            print(movie_details)
        except Exception as e:
            logger.error(f"Failed to scrape movie {href}: {e}")
            continue  # Skip this movie and continue with the next

    scraper.save_data_to_json(all_movies_details)
    scraper.close()
    logger.info(f"Scraping completed. {len(all_movies_details)}/{len(movie_hrefs)} movies scraped successfully.")
