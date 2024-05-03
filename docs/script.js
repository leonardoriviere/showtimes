fetch('data.json')
    .then(response => response.json())
    .then(data => {
        const moviesContainer = document.getElementById('movies');
        data.forEach(movie => {
            const movieEl = document.createElement('p');
            movieEl.textContent = `${movie.title} - Showtimes: ${JSON.stringify(movie.showtimes)}`;
            moviesContainer.appendChild(movieEl);
        });
    })
    .catch(error => console.error('Error loading the movie data:', error));
