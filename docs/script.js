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

            // parent div
            let movieDiv = document.createElement('div');
            movieDiv.className = 'movie';

            // first child div
            let firstChildDiv = document.createElement('div');

            let img = document.createElement('img');
            img.src = movie.poster_url;
            let imageUrl = document.createElement('a');
            imageUrl.href = movie.href;
            imageUrl.appendChild(img);
            firstChildDiv.appendChild(imageUrl);

            let imdbRating = document.createElement('a');
            imdbRating.href = movie.imdb_url;
            imdbRating.textContent = movie.imdb_rating;
            firstChildDiv.appendChild(imdbRating);

            let metascore = document.createElement('label');
            metascore.textContent = movie.metascore;
            firstChildDiv.appendChild(metascore);

            movieDiv.appendChild(firstChildDiv);

            // second child div
            let secondChildDiv = document.createElement('div');

            let originalTitle = document.createElement('h1');
            originalTitle.textContent = movie.original_title;
            secondChildDiv.appendChild(originalTitle);

            let duration = document.createElement('div');
            duration.textContent = movie.duration;
            secondChildDiv.appendChild(duration);

            let showtimes = document.createElement('div');
            showtimes.textContent = JSON.stringify(movie.showtimes[date]);
            secondChildDiv.appendChild(showtimes);

            movieDiv.appendChild(secondChildDiv);

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

            const dayPart = date.toLocaleDateString('en-US', { weekday: 'short' });
            const datePart = date.toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' });
            const dayName = `${dayPart} ${datePart}`;

            const isToday = date.getTime() === today.getTime();
            const displayText = (isToday) ? 'Today' : dayName;

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

