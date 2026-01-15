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

const STORAGE_KEY = 'dismissedMovies';

let organizedDataCache = {};

function makeMovieId(date, movie) {
    return `${date}|${movie.title}|${movie.href}`;
}

const TIME_STEP_MINUTES = 30;
let timeFilterAccordionId = 0;

function parseTimeToMinutes(time) {
    if (typeof time !== 'string') {
        return Number.NaN;
    }

    const match = time.trim().match(/^(\d{1,2}):(\d{2})$/);
    if (!match) {
        return Number.NaN;
    }

    const hours = Number.parseInt(match[1], 10);
    const minutes = Number.parseInt(match[2], 10);

    if (Number.isNaN(hours) || Number.isNaN(minutes)) {
        return Number.NaN;
    }

    return hours * 60 + minutes;
}

function formatMinutesToTime(totalMinutes) {
    const normalizedMinutes = Math.max(0, Number(totalMinutes) || 0);
    const hours = Math.floor(normalizedMinutes / 60);
    const minutes = normalizedMinutes % 60;

    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}

function createTimeRangeFilter({ min, max, step }) {
    const container = document.createElement('div');
    container.className = 'time-filter';

    const contentId = `time-filter-${timeFilterAccordionId += 1}`;

    const summaryButton = document.createElement('button');
    summaryButton.type = 'button';
    summaryButton.className = 'time-filter__summary';
    summaryButton.setAttribute('aria-expanded', 'false');
    summaryButton.setAttribute('aria-controls', contentId);

    const summaryLabel = document.createElement('span');
    summaryLabel.className = 'time-filter__summary-label';
    const defaultSummaryLabel = 'Filtrar Hora';
    summaryLabel.textContent = defaultSummaryLabel;
    summaryButton.appendChild(summaryLabel);

    const summaryIcon = document.createElement('span');
    summaryIcon.className = 'time-filter__summary-icon';
    summaryIcon.innerHTML = `
        <svg class="time-filter__chevron" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>
        </svg>
    `;
    summaryButton.appendChild(summaryIcon);

    container.appendChild(summaryButton);

    const content = document.createElement('div');
    content.className = 'time-filter__content';
    content.id = contentId;
    content.hidden = true;

    const labels = document.createElement('div');
    labels.className = 'time-filter__labels';

    const startLabel = document.createElement('div');
    startLabel.className = 'time-filter__label';
    startLabel.innerHTML = '<span>Desde</span><strong></strong>';

    const endLabel = document.createElement('div');
    endLabel.className = 'time-filter__label';
    endLabel.innerHTML = '<span>Hasta</span><strong></strong>';

    labels.appendChild(startLabel);
    labels.appendChild(endLabel);
    content.appendChild(labels);

    const slider = document.createElement('div');
    slider.className = 'time-filter__slider';
    slider.style.setProperty('--range-start', '0%');
    slider.style.setProperty('--range-end', '100%');

    const lowerInput = document.createElement('input');
    lowerInput.type = 'range';
    lowerInput.min = min;
    lowerInput.max = max;
    lowerInput.step = step;
    lowerInput.value = min;
    lowerInput.setAttribute('aria-label', 'Hora inicial');

    const upperInput = document.createElement('input');
    upperInput.type = 'range';
    upperInput.min = min;
    upperInput.max = max;
    upperInput.step = step;
    upperInput.value = max;
    upperInput.setAttribute('aria-label', 'Hora final');

    if (min === max) {
        lowerInput.disabled = true;
        upperInput.disabled = true;
        container.classList.add('time-filter--disabled');
    }

    slider.appendChild(lowerInput);
    slider.appendChild(upperInput);
    content.appendChild(slider);

    container.appendChild(content);

    let isOpen = false;
    const setOpen = (value) => {
        isOpen = Boolean(value);
        container.classList.toggle('time-filter--open', isOpen);
        summaryButton.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        content.hidden = !isOpen;
    };

    summaryButton.addEventListener('click', () => {
        setOpen(!isOpen);
    });

    const changeHandlers = [];

    const emitChange = () => {
        const start = Number(lowerInput.value);
        const end = Number(upperInput.value);
        changeHandlers.forEach(handler => handler({ start, end }));
    };

    const updateSummaryLabel = () => {
        const start = Number(lowerInput.value);
        const end = Number(upperInput.value);
        const stepValue = Math.max(Number(step) || 0, 0);
        const tolerance = stepValue ? stepValue / 2 : 0;
        const isAtMin = Math.abs(start - min) <= tolerance;
        const isAtMax = Math.abs(end - max) <= tolerance;
        const coversFullRange = min === max || (isAtMin && isAtMax);

        if (coversFullRange) {
            summaryLabel.textContent = defaultSummaryLabel;
        } else {
            summaryLabel.textContent = `${formatMinutesToTime(start)} a ${formatMinutesToTime(end)}`;
        }
    };

    const updateSliderVisuals = () => {
        const start = Number(lowerInput.value);
        const end = Number(upperInput.value);
        const range = Math.max(max - min, 1);

        const startRatio = max === min ? 0 : ((start - min) / range) * 100;
        const endRatio = max === min ? 100 : ((end - min) / range) * 100;

        slider.style.setProperty('--range-start', `${Math.max(0, Math.min(startRatio, 100))}%`);
        slider.style.setProperty('--range-end', `${Math.max(0, Math.min(endRatio, 100))}%`);

        const formattedStart = formatMinutesToTime(start);
        const formattedEnd = formatMinutesToTime(end);
        startLabel.querySelector('strong').textContent = formattedStart;
        endLabel.querySelector('strong').textContent = formattedEnd;
        lowerInput.setAttribute('aria-valuetext', formattedStart);
        upperInput.setAttribute('aria-valuetext', formattedEnd);

        updateSummaryLabel();
    };

    const handleInput = (event) => {
        if (lowerInput.disabled || upperInput.disabled) {
            return;
        }

        const isLowerHandle = event.target === lowerInput;
        let start = Number(lowerInput.value);
        let end = Number(upperInput.value);

        if (isLowerHandle && start > end) {
            end = start;
            upperInput.value = end;
        } else if (!isLowerHandle && end < start) {
            start = end;
            lowerInput.value = start;
        }

        updateSliderVisuals();
        emitChange();
    };

    lowerInput.addEventListener('input', handleInput);
    upperInput.addEventListener('input', handleInput);

    const onChange = (handler) => {
        if (typeof handler === 'function') {
            changeHandlers.push(handler);
        }
    };

    const getValues = () => ({
        start: Number(lowerInput.value),
        end: Number(upperInput.value)
    });

    const setValues = ({ start, end }) => {
        if (typeof start === 'number') {
            lowerInput.value = Math.max(min, Math.min(start, max));
        }
        if (typeof end === 'number') {
            upperInput.value = Math.max(min, Math.min(end, max));
        }
        updateSliderVisuals();
        emitChange();
    };

    const refresh = () => {
        updateSliderVisuals();
    };

    refresh();

    return {
        element: container,
        onChange,
        getValues,
        setValues,
        refresh
    };
}

function getDismissedMovies() {
    try {
        const stored = sessionStorage.getItem(STORAGE_KEY);
        return stored ? JSON.parse(stored) : [];
    } catch (error) {
        console.error('Error reading dismissed movies from sessionStorage:', error);
        return [];
    }
}

function saveDismissedMovies(movies) {
    try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(movies));
    } catch (error) {
        console.error('Error saving dismissed movies to sessionStorage:', error);
    }
}

function setupSwipeToRemove(card, onRemove) {
    const SWIPE_THRESHOLD = 80; // pixels needed to trigger removal
    const VELOCITY_THRESHOLD = 0.4; // px/ms for fast swipes
    
    let startX = 0;
    let startY = 0;
    let currentX = 0;
    let isSwiping = false;
    let startTime = 0;

    const resetCard = () => {
        card.style.transform = '';
        card.style.opacity = '';
        card.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
        card.classList.remove('movie--swiping', 'movie--swiping-left', 'movie--swiping-right');
    };

    const removeCard = (direction) => {
        card.classList.add('movie--removing');
        const offset = card.offsetWidth + 100;
        card.style.transition = 'transform 0.25s ease, opacity 0.25s ease';
        card.style.transform = `translateX(${direction * offset}px)`;
        card.style.opacity = '0';
        
        setTimeout(() => onRemove(), 250);
    };

    const onTouchStart = (e) => {
        const touch = e.touches[0];
        startX = touch.clientX;
        startY = touch.clientY;
        currentX = 0;
        isSwiping = false;
        startTime = Date.now();
        card.style.transition = 'none';
    };

    const onTouchMove = (e) => {
        if (!startX) return;
        
        const touch = e.touches[0];
        const deltaX = touch.clientX - startX;
        const deltaY = touch.clientY - startY;

        // Only start swiping if horizontal movement > vertical
        if (!isSwiping && Math.abs(deltaX) > 10) {
            if (Math.abs(deltaX) > Math.abs(deltaY)) {
                isSwiping = true;
                card.classList.add('movie--swiping');
            } else {
                startX = 0; // Cancel - user is scrolling vertically
                return;
            }
        }

        if (!isSwiping) return;
        
        e.preventDefault();
        currentX = deltaX;
        
        const progress = Math.min(1, Math.abs(currentX) / (SWIPE_THRESHOLD * 2));
        card.style.transform = `translateX(${currentX}px)`;
        card.style.opacity = `${1 - progress * 0.5}`;
        card.classList.toggle('movie--swiping-left', currentX < 0);
        card.classList.toggle('movie--swiping-right', currentX > 0);
    };

    const onTouchEnd = () => {
        if (!isSwiping) {
            startX = 0;
            return;
        }

        const elapsed = Date.now() - startTime;
        const velocity = Math.abs(currentX) / elapsed;
        const direction = currentX > 0 ? 1 : -1;

        // Remove if: swiped far enough OR swiped fast enough
        if (Math.abs(currentX) > SWIPE_THRESHOLD || velocity > VELOCITY_THRESHOLD) {
            removeCard(direction);
        } else {
            resetCard();
        }

        startX = 0;
        isSwiping = false;
    };

    card.addEventListener('touchstart', onTouchStart, { passive: true });
    card.addEventListener('touchmove', onTouchMove, { passive: false });
    card.addEventListener('touchend', onTouchEnd);
    card.addEventListener('touchcancel', () => { resetCard(); startX = 0; isSwiping = false; });
}

function dismissMovie(movieId) {
    const dismissed = getDismissedMovies();
    if (!dismissed.includes(movieId)) {
        dismissed.push(movieId);
        saveDismissedMovies(dismissed);
    }
}

function filterDismissedMovies(data) {
    const dismissedSet = new Set(getDismissedMovies());
    const filteredEntries = Object.entries(data)
        .map(([date, movies]) => {
            const availableMovies = movies.filter(movie => !dismissedSet.has(makeMovieId(date, movie)));
            return [date, availableMovies];
        })
        .filter(([, movies]) => movies.length > 0);

    return Object.fromEntries(filteredEntries);
}

function getCurrentSelectedDay() {
    const selectedLink = document.querySelector('#day-links a.selected');
    return selectedLink ? selectedLink.getAttribute('data-day') : null;
}

function displayMoviesByDate(data) {
    const container = document.getElementById('movies');
    if (!container) {
        console.error('Movies container not found!');
        return;
    }

    // Clear existing content
    container.innerHTML = '';

    const availableDates = [];

    // Iterate over each date in the data
    Object.keys(data).forEach(date => {
        const moviesForDate = data[date];
        if (!moviesForDate || moviesForDate.length === 0) {
            return;
        }

        const allShowtimeMinutes = [];
        moviesForDate.forEach(movie => {
            const dailyShowtimes = movie.showtimes?.[date] || {};
            Object.values(dailyShowtimes).forEach(times => {
                times.forEach(time => {
                    const minutes = parseTimeToMinutes(time);
                    if (!Number.isNaN(minutes)) {
                        allShowtimeMinutes.push(minutes);
                    }
                });
            });
        });

        if (!allShowtimeMinutes.length) {
            return;
        }

        // Create a section for each date
        const dateSection = document.createElement('div');
        dateSection.setAttribute('value', date);
        dateSection.className = 'day-section';

        const filterContainer = document.createElement('div');
        filterContainer.className = 'day-filter';

        const minTime = Math.min(...allShowtimeMinutes);
        const maxTime = Math.max(...allShowtimeMinutes);
        
        // Round min down and max up to step multiples so slider reaches extremes
        const roundedMin = Math.floor(minTime / TIME_STEP_MINUTES) * TIME_STEP_MINUTES;
        const roundedMax = Math.ceil(maxTime / TIME_STEP_MINUTES) * TIME_STEP_MINUTES;

        const timeFilter = createTimeRangeFilter({
            min: roundedMin,
            max: roundedMax,
            step: TIME_STEP_MINUTES
        });

        filterContainer.appendChild(timeFilter.element);

        const noResultsMessage = document.createElement('p');
        noResultsMessage.className = 'day-no-results';
        noResultsMessage.textContent = 'No hay funciones en el rango seleccionado.';

        // Container for movies
        const movieList = document.createElement('div');
        movieList.className = 'movie-list';

        const applyTimeFilter = ({ start, end } = timeFilter.getValues()) => {
            let visibleMovies = 0;

            movieList.querySelectorAll('.movie').forEach(movieCard => {
                let movieHasVisibleTimes = false;

                movieCard.querySelectorAll('.format').forEach(formatDiv => {
                    let formatHasVisibleTimes = false;

                    formatDiv.querySelectorAll('.format__time').forEach(timeLink => {
                        const minutesValue = Number(timeLink.dataset.minutes);
                        const isValidTime = !Number.isNaN(minutesValue);
                        const isVisible = !isValidTime || (minutesValue >= start && minutesValue <= end);
                        timeLink.style.display = isVisible ? '' : 'none';

                        if (isVisible) {
                            formatHasVisibleTimes = true;
                        }
                    });

                    formatDiv.style.display = formatHasVisibleTimes ? '' : 'none';

                    if (formatHasVisibleTimes) {
                        movieHasVisibleTimes = true;
                    }
                });

                movieCard.style.display = movieHasVisibleTimes ? '' : 'none';

                if (movieHasVisibleTimes) {
                    visibleMovies += 1;
                }
            });

            noResultsMessage.style.display = visibleMovies ? 'none' : 'block';
        };

        // Iterate over movies for this date
        moviesForDate.forEach(movie => {
            const movieId = makeMovieId(date, movie);

            // Parent div
            let movieDiv = document.createElement('div');
            movieDiv.className = 'movie';
            movieDiv.setAttribute('data-movie-id', movieId);

            // First child div
            let firstChildDiv = document.createElement('div');

            // Image of the movie
            let img = document.createElement('img');
            img.src = movie.poster_url;
            firstChildDiv.appendChild(img);

            let infoDiv = document.createElement('div');

            function toTitleCase(str) {
                // Unicode-aware title case that handles accented characters
                return str.toLowerCase().replace(/(?:^|\s)\S/g, function(char) {
                    return char.toUpperCase();
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

            const imdbUrl = movie.imdb_url;
            if (typeof imdbUrl === 'string' && imdbUrl.startsWith('https://www.imdb.com/')) {
                let imdbLink = document.createElement('a');
                
                // Try to open IMDb app on mobile, fallback to web only if app didn't open
                const titleMatch = imdbUrl.match(/\/title\/(tt\d+)/);
                if (titleMatch) {
                    const imdbId = titleMatch[1];
                    imdbLink.href = `imdb:///title/${imdbId}/`;
                    imdbLink.addEventListener('click', (e) => {
                        let appOpened = false;
                        const onBlur = () => { appOpened = true; };
                        window.addEventListener('blur', onBlur, { once: true });
                        
                        // Fallback: only open web if app didn't open (page still visible)
                        setTimeout(() => {
                            window.removeEventListener('blur', onBlur);
                            if (!appOpened && !document.hidden) {
                                window.location.href = imdbUrl;
                            }
                        }, 800);
                    });
                } else {
                    imdbLink.href = imdbUrl;
                    imdbLink.target = "_blank";
                    imdbLink.rel = "noopener noreferrer";
                }

                if (imdbUrl.startsWith('https://www.imdb.com/title/tt')) {
                    if (movie.imdb_rating !== 'N/A' && movie.metascore !== 'N/A') {
                        imdbLink.textContent = 'IMDb ' + movie.imdb_rating + ' / ' + movie.metascore;
                    } else if (movie.imdb_rating !== 'N/A') {
                        imdbLink.textContent = 'IMDb ' + movie.imdb_rating;
                    } else {
                        imdbLink.textContent = 'IMDb';
                    }
                } else {
                    imdbLink.textContent = 'Buscar en IMDb';
                }

                movieLinks.appendChild(imdbLink);
            }

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
                    timeLink.target = "_blank";
                    timeLink.rel = "noopener noreferrer";
                    timeLink.classList.add('format__time');

                    const timeMinutes = parseTimeToMinutes(time);
                    if (!Number.isNaN(timeMinutes)) {
                        timeLink.dataset.minutes = timeMinutes;
                    }

                    timesDiv.appendChild(timeLink);
                });

                formatDiv.appendChild(timesDiv);
                showtimesDiv.appendChild(formatDiv);
            });
            movieDiv.appendChild(showtimesDiv);
            movieList.appendChild(movieDiv);

            setupSwipeToRemove(movieDiv, () => {
                dismissMovie(movieId);
                renderApp(getCurrentSelectedDay(), { preserveScrollPosition: true });
            });
        });

        if (movieList.children.length > 0) {
            dateSection.appendChild(filterContainer);
            dateSection.appendChild(noResultsMessage);
            dateSection.appendChild(movieList);
            container.appendChild(dateSection);
            availableDates.push(date);

            timeFilter.onChange(applyTimeFilter);
            timeFilter.refresh();
            applyTimeFilter();
        }
    });

    if (!availableDates.length) {
        const emptyState = document.createElement('p');
        emptyState.className = 'empty-state';
        emptyState.textContent = 'No movies to show right now. Refresh the page to restore the list.';
        container.appendChild(emptyState);
    }

    return availableDates;
}

function createDayLinks(data, preferredDay, orderedDates, options = {}) {
    const { preserveScrollPosition = false } = options;
    const linksContainer = document.getElementById('day-links');
    if (!linksContainer) {
        console.error('Day links container not found!');
        return;
    }
    linksContainer.innerHTML = ''; // Clear previous links

    const days = orderedDates && orderedDates.length ? orderedDates : Object.keys(data);
    if (!days.length) {
        return;
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0); // Normalize today's date

    let futureDates = [];
    let pastDates = [];

    days.forEach(day => {
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

    const normalizedPreferred = preferredDay && days.includes(preferredDay) ? preferredDay : null;
    const todayMatch = futureDates.find(day => {
        const utcDate = new Date(day);
        const milisecInMinute = 60000;
        const localDate = new Date(utcDate.getTime() + utcDate.getTimezoneOffset() * milisecInMinute);
        localDate.setHours(0, 0, 0, 0);
        return localDate.getTime() === today.getTime();
    });

    const defaultDay = normalizedPreferred
        || todayMatch
        || (futureDates.length ? futureDates[0] : null)
        || (pastDates.length ? pastDates[pastDates.length - 1] : null);

    let dayToSelect = null;

    // Call the function to create links for both types of dates and add the separator in between
    createLinks(futureDates);
    if (futureDates.length && pastDates.length) {
        addSeparator();
    }
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

            if (day === defaultDay && !dayToSelect) {
                dayToSelect = link;
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

    if (dayToSelect) {
        dayToSelect.classList.add('selected');
        showMoviesForDay(dayToSelect.getAttribute('data-day'), { preserveScrollPosition });
    }
}

function showMoviesForDay(selectedDay, options = {}) {
    const { preserveScrollPosition = false } = options;
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

    const moviesContainer = document.querySelector('#movies');

    if (preserveScrollPosition) {
        moviesContainer.style.overflow = 'auto';
        return;
    }

    // Disabling scroll
    moviesContainer.style.overflow = 'hidden';

    // Apply scrollTop
    moviesContainer.scrollTop = 0;

    // Enabling the scroll
    setTimeout(() => {
        moviesContainer.style.overflow = 'auto';
    }, 100);
}

// Assuming `organizedData` is your data object from the previous example
fetch('data.json')
  .then(response => response.json())
  .then(data => {
    organizedDataCache = reorganizeDataByDate(data);
    renderApp();
  })
  .catch(error => console.error('Error loading the movie data:', error));

function renderApp(preferredDay, options = {}) {
    const { preserveScrollPosition = false } = options;
    const filteredData = filterDismissedMovies(organizedDataCache);
    const availableDates = displayMoviesByDate(filteredData);
    createDayLinks(filteredData, preferredDay, availableDates, { preserveScrollPosition });
}

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
