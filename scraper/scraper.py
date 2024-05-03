from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from imdb import IMDb
import json  # Import the JSON module


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
    def __init__(self, chromedriver_path):
        chrome_options = webdriver.ChromeOptions()
        service = Service(chromedriver_path)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def scrape_movie_data(self, base_url):
        self.driver.get(base_url)
        WebDriverWait(self.driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#cartelera_cine_40212 > .boxfilm > .afiche-pelicula > a'))
        )
        movies_links = self.driver.find_elements(By.CSS_SELECTOR, '#cartelera_cine_40212 > .boxfilm > '
                                                                  '.afiche-pelicula > a')
        movie_hrefs = [link.get_attribute('href') for link in movies_links]
        return movie_hrefs

    def scrape_movie_details(self, href):
        self.driver.get(href)
        WebDriverWait(self.driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.op_format'))
        )
        title = self.driver.find_element(By.CSS_SELECTOR, '.movie-info-box .name > strong').text
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

    def get_imdb_url(self, original_title):
        ia = IMDb()
        search_results = ia.search_movie(original_title)

        if search_results:
            first_result = search_results[0]  # Assuming the first result is the correct movie
            movie_id = first_result.movieID
            imdb_url = f"https://www.imdb.com/title/tt{movie_id}/"
            return imdb_url
        else:
            return "IMDb URL not found"

    def scrape_imdb_info(self, imdb_url, showcase_duration):
        self.driver.get(imdb_url)
        imdb_info = {'imdb_rating': 'N/A', 'metascore': 'N/A', 'imdb_duration': 'N/A'}

        try:
            # Attempt to find the IMDb duration on the page
            imdb_duration_str = self.driver.find_element(By.CSS_SELECTOR,
                                                         '[data-testid="hero__pageTitle"] ~ ul[role="presentation"] > '
                                                         'li:last-of-type').text
            imdb_duration_minutes = convert_imdb_duration_to_minutes(imdb_duration_str)

            # Convert Showcase duration to minutes for comparison
            showcase_duration_minutes = convert_showcase_duration_to_minutes(showcase_duration)

            # If durations are within two minutes of each other, proceed to scrape ratings
            if abs(imdb_duration_minutes - showcase_duration_minutes) <= 2:
                # Existing code to scrape ratings if condition is met
                try:
                    imdb_rating = self.driver.find_element(By.CSS_SELECTOR,
                                                           'div[data-testid="hero-rating-bar__aggregate-rating__score'
                                                           '"] > span').text
                    imdb_info['imdb_rating'] = imdb_rating
                except Exception:
                    pass  # IMDb rating remains "N/A" if not found

                try:
                    metascore = self.driver.find_element(By.CSS_SELECTOR, 'span.metacritic-score-box').text
                    imdb_info['metascore'] = metascore
                except Exception:
                    pass  # Metascore remains "N/A" if not found

            imdb_info['imdb_duration'] = imdb_duration_str  # Keep the original IMDb duration string for reference
        except Exception as e:
            print(f"Error scraping IMDb info: {e}")

        return imdb_info

    def extract_showtimes(self):
        showtimes = {}
        # Find all day selectors and iterate through them
        day_selectors = self.driver.find_elements(By.CSS_SELECTOR, '.movie-info-box #op_container .op_days .op_day')
        for day_selector in day_selectors:
            # Extract the date from the day_selector, assuming it's in a format you can use directly
            date = day_selector.get_attribute('value')  # Adjust attribute name as necessary

            # Click the day selector to load the showtimes for that day
            day_selector.click()

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
        with open('../docs/data.json', 'w') as jsonfile:  # Make sure the 'docs' folder exists
            json.dump(data, jsonfile, indent=4)


if __name__ == "__main__":
    scraper = MovieScraper(chromedriver_path='/usr/local/bin/chromedriver')
    base_url = 'https://www.todoshowcase.com/'
    movie_hrefs = scraper.scrape_movie_data(base_url)

    all_movies_details = []  # List to store details of all movies

    # Loop through all movie URLs and scrape their details
    for href in movie_hrefs:
        movie_details = scraper.scrape_movie_details(href)
        all_movies_details.append(movie_details)  # Append movie details regardless of showtimes
        print(movie_details)  # Print details of each movie

    scraper.save_data_to_json(all_movies_details)
    scraper.close()
