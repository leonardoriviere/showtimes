// Function to reorganize the data by date
function reorganizeDataByDate(movies) {
    const dataByDate = {};

    movies.forEach(movie => {
        movie.showing_days.forEach(day => {
            if (!dataByDate[day]) {
                dataByDate[day] = [];
            }
            dataByDate[day].push(movie);
        });
    });

    // Create an object from entries sorted by date
    const sortedDataByDate = Object.fromEntries(
        Object.entries(dataByDate).sort((a, b) => new Date(a[0]) - new Date(b[0]))
    );

    return sortedDataByDate;
}

function displayMoviesByDate(data) {
    const container = document.getElementById('movies');
    if (!container) {
        console.error('Movies container not found!');
        return;
    }

    // Clear existing content
    container.innerHTML = '';

    // Iterate over each date in the data
    Object.keys(data).forEach(date => {
        // Create a section for each date
        const dateSection = document.createElement('div');
        dateSection.setAttribute('value', date);

        // Container for movies
        const movieList = document.createElement('div');
        movieList.className = 'movie-list';

        // Iterate over movies for this date
        data[date].forEach(movie => {
            // Parent div
            let movieDiv = document.createElement('div');
            movieDiv.className = 'movie';

            // First child div
            let firstChildDiv = document.createElement('div');

            // Image of the movie
            let img = document.createElement('img');
            img.src = movie.poster_url;
            firstChildDiv.appendChild(img);

            let infoDiv = document.createElement('div');

            function toTitleCase(str) {
                return str.replace(/\w\S*/g, function(txt) {
                    return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
                });
            }

            let movieTitle = document.createElement('h1');
            movieTitle.textContent = toTitleCase(movie.title);
            infoDiv.appendChild(movieTitle);

            function convertDuration(duration) {
              // Extract the duration in minutes
              const minutes = parseInt(duration.split(' ')[0]);

              // Calculate hours and remaining minutes
              const hours = Math.floor(minutes / 60);
              const remainingMinutes = minutes % 60;

              return `${hours}h ${remainingMinutes}min`;
            }

            let duration = document.createElement('div');
            duration.textContent = convertDuration(movie.duration);
            infoDiv.appendChild(duration);
            infoDiv.className = 'movie-info';

            let movieLinks = document.createElement('div');

            let imdbLink = document.createElement('a');
            imdbLink.href = movie.imdb_url;

            if (movie.imdb_rating !== 'N/A' && movie.metascore !== 'N/A') {
                imdbLink.textContent = 'IMDb ' + movie.imdb_rating + ' / ' + movie.metascore;
            } else if (movie.imdb_rating !== 'N/A') {
                imdbLink.textContent = 'IMDb ' + movie.imdb_rating;
            } else {
                imdbLink.textContent = 'IMDb';
            }

            movieLinks.appendChild(imdbLink);

            infoDiv.appendChild(movieLinks);

            firstChildDiv.appendChild(infoDiv);
            movieDiv.appendChild(firstChildDiv);

            // second child div
            let showtimesDiv = document.createElement('div');
            showtimesDiv.className = 'showtimes';
            Object.entries(movie.showtimes[date]).forEach(([format, times]) => {
                let formatDiv = document.createElement('div');
                let formatNameDiv = document.createElement('div');
                formatNameDiv.textContent = format;
                formatDiv.appendChild(formatNameDiv);
                formatDiv.className = 'format';

                let timesDiv = document.createElement('div');
                times.forEach(time => {
                    let timeLink = document.createElement('a');
                    timeLink.href = movie.href;
                    timeLink.textContent = time;
                    timesDiv.appendChild(timeLink);
                });

                formatDiv.appendChild(timesDiv);
                showtimesDiv.appendChild(formatDiv);
            });
            movieDiv.appendChild(showtimesDiv);
            movieList.appendChild(movieDiv);
        });

        dateSection.appendChild(movieList);
        container.appendChild(dateSection);
    });
}

function createDayLinks(data) {
    const linksContainer = document.getElementById('day-links');
    if (!linksContainer) {
        console.error('Day links container not found!');
        return;
    }
    linksContainer.innerHTML = ''; // Clear previous links
    const today = new Date();
    today.setHours(0, 0, 0, 0); // Normalize today's date
    console.log(today);

    let futureDates = [];
    let pastDates = [];

    Object.keys(data).forEach(day => {
        const utcDate = new Date(day);
        // Normalize the UTC date
        const milisecInMinute = 60000;
        const date = new Date(utcDate.getTime() + utcDate.getTimezoneOffset() * milisecInMinute);
        date.setHours(0, 0, 0, 0);

        if(today.getTime() <= date.getTime()) {
            futureDates.push(day);
        } else {
            pastDates.push(day);
        }
    });

    // Sorting the dates
    futureDates = futureDates.sort((a, b) => new Date(a) - new Date(b));
    pastDates = pastDates.sort((a, b) => new Date(a) - new Date(b));

    // Call the function to create links for both types of dates and add the separator in between
    createLinks(futureDates);
    addSeparator();
    createLinks(pastDates);

    // Function to create links for a given set of dates
    function createLinks(dates) {
        dates.forEach(day => {
            const utcDate = new Date(day);
            const milisecInMinute = 60000;
            const date = new Date(utcDate.getTime() + utcDate.getTimezoneOffset() * milisecInMinute);

            // Function to remove accents from a string
            function removeAccents(str) {
                return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
            }

            const dayPart = removeAccents(date.toLocaleDateString('es-ES', { weekday: 'short' }));
            const datePart = date.toLocaleDateString('es-ES', { day: 'numeric', month: 'numeric' });

            const dayName = `${dayPart.charAt(0).toUpperCase() + dayPart.slice(1)} ${datePart}`;

            const isToday = date.getTime() === today.getTime();
            const displayText = (isToday) ? 'Hoy' : dayName;

            const link = document.createElement('a');
            link.href = '#';
            link.setAttribute('data-day', day);
            link.textContent = displayText;

            if (isToday) {
                link.classList.add('selected');
                showMoviesForDay(day);
            }

            link.addEventListener('click', (event) => {
                event.preventDefault();
                showMoviesForDay(day);
                // Remove existing 'selected' from all links
                const links = linksContainer.querySelectorAll('a');
                links.forEach(link => link.classList.remove('selected'));
                // Add 'selected' to the clicked link
                event.target.classList.add('selected');
            });

            linksContainer.appendChild(link);
            linksContainer.appendChild(document.createTextNode(' ')); // Adding space instead of '|'
        });
    }

    // Function to add a separator
    function addSeparator() {
        const separator = document.createElement('hr');
        linksContainer.appendChild(separator);
    }
}

function showMoviesForDay(selectedDay) {
    // Find all day sections
    const allDays = document.querySelectorAll('#movies > div');
    allDays.forEach(daySection => {
        // Hide or show based on the match
        if (daySection.getAttribute('value') === selectedDay) {
            daySection.style.display = 'block';
        } else {
            daySection.style.display = 'none';
        }
    });
}

// Assuming `organizedData` is your data object from the previous example
fetch('data.json')
  .then(response => response.json())
  .then(data => {
    const organizedData = reorganizeDataByDate(data);
    displayMoviesByDate(organizedData); // Call the function to display the movies
    createDayLinks(organizedData); // Call to create day links
  })
  .catch(error => console.error('Error loading the movie data:', error));

// Function to set the full height variable
const setFullHeightVariable = () => {
  let vh = window.innerHeight * 0.01;
  document.documentElement.style.setProperty('--vh', `${vh}px`);
};

// Listen for resize events
let resizeTimeout;

// Listen for resize events
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(setFullHeightVariable, 150);
});

// Call the function initially on page load
window.addEventListener('load', setFullHeightVariable);
