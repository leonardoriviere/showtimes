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


# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
CONSECUTIVE_FAILURES_BEFORE_RESTART = 3

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
        self.logger = logging.getLogger(__name__)
        self.chromedriver_path = chromedriver_path
        self.consecutive_failures = 0
        self._init_driver()

    def _get_chrome_options(self):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        return chrome_options

    def _init_driver(self):
        """Initialize or reinitialize the WebDriver."""
        try:
            self.logger.info("Initializing WebDriver...")
            if self.chromedriver_path:
                self.logger.info(f"Using ChromeDriver from path: {self.chromedriver_path}")
                service = Service(executable_path=self.chromedriver_path)
            else:
                self.logger.info("Using ChromeDriver managed by ChromeDriverManager.")
                service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=self._get_chrome_options())
            self.driver.set_page_load_timeout(60)
            self.logger.info("WebDriver initialized successfully.")
        except Exception as e:
            self.logger.error(f"Error initializing WebDriver: {e}")
            raise

    def _restart_driver(self):
        """Restart the WebDriver after consecutive failures."""
        self.logger.warning("Restarting WebDriver due to consecutive failures...")
        try:
            self.driver.quit()
        except Exception:
            pass
        time.sleep(RETRY_DELAY_SECONDS)
        self._init_driver()
        self.consecutive_failures = 0

    def scrape_movie_data(self, base_url):
        self.driver.get(base_url)
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#cartelera_cine_40212 > .boxfilm > .afiche-pelicula > a'))
        )
        movies_links = self.driver.find_elements(By.CSS_SELECTOR, '#cartelera_cine_40212 > .boxfilm > '
                                                                  '.afiche-pelicula > a')
        movie_hrefs = [link.get_attribute('href') for link in movies_links]
        return movie_hrefs

    def scrape_movie_hrefs_only(self, base_url):
        """Light scraping: only extract movie hrefs from the main page (fast check)."""
        # Reuse exact same logic as scrape_movie_data for reliability
        return sorted(self.scrape_movie_data(base_url))

    def scrape_movie_details_with_retry(self, href):
        """Scrape movie details with retry logic and driver restart on consecutive failures."""
        last_error = None
        
        for attempt in range(MAX_RETRIES):
            try:
                result = self.scrape_movie_details(href)
                self.consecutive_failures = 0  # Reset on success
                return result
            except Exception as e:
                last_error = e
                self.consecutive_failures += 1
                self.logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES} failed for {href}: {e}")
                
                # Restart driver if too many consecutive failures
                if self.consecutive_failures >= CONSECUTIVE_FAILURES_BEFORE_RESTART:
                    self._restart_driver()
                elif attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS)
        
        # All retries failed
        raise last_error

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

        # Extract director from side info box
        director = ''
        for li in self.driver.find_elements(By.CSS_SELECTOR, '.movie-side-info-box ul > li'):
            if 'Director:' in li.text:
                director = li.text.replace('Director:', '').strip()
                break

        movie_info = {
            'title': title,
            'href': href,
            'original_title': original_title,
            'poster_url': poster_url,
            'duration': duration,
            'showing_days': showing_days,
            'showtimes': showtimes_by_format
        }

        # Fetch the IMDb URL using the original title and director for disambiguation
        imdb_url = self.get_imdb_url(original_title, director=director)
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

        return "https://www.imdb.com/find/?q=" + quote_plus(query) + "&s=tt&ttype=ft"

    def _extract_imdb_id_url(self, href):
        """Extract a clean IMDb title URL from a raw href."""
        match = re.search(r'/title/(tt\d+)', href)
        if match:
            return f"https://www.imdb.com/title/{match.group(1)}/"
        return None

    def _verify_imdb_director(self, imdb_url, director):
        """Visit an IMDb title page and check if the director matches."""
        try:
            self.driver.get(imdb_url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="hero__pageTitle"]'))
            )
            # The principal credits section lists Director, Writer, Stars
            credits_text = self.driver.find_element(By.CSS_SELECTOR, 'main').text
            # Compare using the director's last name to handle minor differences
            director_parts = director.strip().split()
            last_name = director_parts[-1] if director_parts else ''
            return last_name.lower() in credits_text.lower() if last_name else False
        except Exception as exc:
            self.logger.warning("Director verification failed for %s: %s", imdb_url, exc)
            return False

    def get_imdb_url(self, original_title, director='', max_retries=2):
        search_url = self._build_imdb_search_url(original_title)
        if search_url == "IMDb URL not found":
            return search_url

        for attempt in range(max_retries):
            try:
                self.driver.get(search_url)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="find-results-section-title"]'))
                )

                item_selector = '[data-testid="find-results-section-title"] .ipc-metadata-list-summary-item'
                results = self.driver.find_elements(By.CSS_SELECTOR, item_selector)

                fallback_href = None
                exact_matches = []
                query_lower = original_title.strip().lower()

                for result in results:
                    try:
                        link = result.find_element(By.CSS_SELECTOR, 'a[href*="/title/tt"]')
                        href = link.get_attribute('href')
                        if not href or '/title/tt' not in href:
                            continue

                        if fallback_href is None:
                            fallback_href = href

                        title_el = result.find_element(By.CSS_SELECTOR, 'h3')
                        if title_el.text.strip().lower() == query_lower:
                            exact_matches.append(href)
                    except Exception:
                        continue

                # Single exact match or no director to verify: use first exact match
                if exact_matches and (len(exact_matches) == 1 or not director):
                    url = self._extract_imdb_id_url(exact_matches[0])
                    if url:
                        return url

                # Multiple exact matches with director: verify each candidate
                if len(exact_matches) > 1 and director:
                    self.logger.info(
                        "Multiple exact matches for '%s', verifying director '%s'",
                        original_title, director
                    )
                    for href in exact_matches:
                        candidate_url = self._extract_imdb_id_url(href)
                        if candidate_url and self._verify_imdb_director(candidate_url, director):
                            self.logger.info("Director match found: %s", candidate_url)
                            return candidate_url
                    # No director match — fall back to first exact match
                    url = self._extract_imdb_id_url(exact_matches[0])
                    if url:
                        return url

                # No exact match — use first result
                if fallback_href:
                    url = self._extract_imdb_id_url(fallback_href)
                    if url:
                        return url

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

    @staticmethod
    def get_existing_hrefs():
        """Load existing movie hrefs from data.json."""
        base_dir = Path(__file__).resolve().parent
        json_path = base_dir / ".." / "docs" / "data.json"
        
        if not json_path.exists():
            return []
        
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            return sorted([movie.get('href', '') for movie in data])
        except (json.JSONDecodeError, KeyError):
            return []


MIN_SUCCESS_RATE = 0.5  # Don't save if less than 50% of movies scraped successfully

def run_heavy_scraping(scraper, base_url, logger):
    """Run full scraping: titles, details, showtimes, and IMDb data."""
    movie_hrefs = scraper.scrape_movie_data(base_url)
    all_movies_details = []

    for idx, href in enumerate(movie_hrefs, 1):
        try:
            logger.info(f"Scraping movie {idx}/{len(movie_hrefs)}: {href}")
            movie_details = scraper.scrape_movie_details_with_retry(href)
            all_movies_details.append(movie_details)
            print(movie_details)
        except Exception as e:
            logger.error(f"Failed to scrape movie {href}: {e}")
            continue

    success_rate = len(all_movies_details) / len(movie_hrefs) if movie_hrefs else 0
    logger.info(f"Scraping completed. {len(all_movies_details)}/{len(movie_hrefs)} movies scraped successfully ({success_rate:.0%}).")
    
    if success_rate < MIN_SUCCESS_RATE:
        logger.error(f"ABORTING SAVE: Success rate {success_rate:.0%} is below minimum {MIN_SUCCESS_RATE:.0%}. Data.json NOT updated to prevent data loss.")
        return False
    
    scraper.save_data_to_json(all_movies_details)
    logger.info("Data saved successfully.")
    return True


def run_light_scraping(scraper, base_url, logger):
    """Light scraping: check if movie hrefs have changed. Returns True if heavy scraping is needed."""
    logger.info("Running light scraping - checking for changes...")
    
    current_hrefs = scraper.scrape_movie_hrefs_only(base_url)
    existing_hrefs = MovieScraper.get_existing_hrefs()
    
    logger.info(f"Current movies: {len(current_hrefs)}")
    logger.info(f"Existing movies: {len(existing_hrefs)}")
    
    if current_hrefs != existing_hrefs:
        added = set(current_hrefs) - set(existing_hrefs)
        removed = set(existing_hrefs) - set(current_hrefs)
        
        if added:
            logger.info(f"New movies detected: {len(added)} new")
        if removed:
            logger.info(f"Movies removed: {len(removed)} removed")
        
        logger.info("Changes detected! Heavy scraping needed.")
        return True
    else:
        logger.info("No changes detected. Skipping heavy scraping.")
        return False


if __name__ == "__main__":
    # Argument parser setup
    parser = argparse.ArgumentParser(description='Scrape movie showtimes.')
    parser.add_argument('--chromedriver-path', type=str, help='Path to the ChromeDriver executable')
    parser.add_argument('--light', action='store_true', help='Run light scraping (titles only). Triggers heavy scraping if changes detected.')
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

    logger = logging.getLogger(__name__)
    scraper = MovieScraper(chromedriver_path=args.chromedriver_path)
    base_url = 'https://www.todoshowcase.com/'

    try:
        if args.light:
            needs_heavy = run_light_scraping(scraper, base_url, logger)
            if needs_heavy:
                run_heavy_scraping(scraper, base_url, logger)
        else:
            run_heavy_scraping(scraper, base_url, logger)
    finally:
        scraper.close()
