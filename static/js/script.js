document.documentElement.classList.add('js-enabled');

let focusDueToValidation = false;
let suppressEvents = false;
let trainData = [];
let trainDataFull = [];

function loadTrains() {
    return new Promise((resolve) => {
        const cachedTrains = localStorage.getItem('railwayTrains');
        const trainsElement = document.getElementById('trains-data');
        let serverTrains, serverVersion;

        if (trainsElement) {
            const data = JSON.parse(trainsElement.textContent);
            serverTrains = data.trains;
            trainDataFull = data.trains_full || [];
            serverVersion = data.version || "1.0.0";
        } else {
            serverTrains = [];
            trainDataFull = [];
            serverVersion = "1.0.0";
        }

        if (cachedTrains) {
            const cachedData = JSON.parse(cachedTrains);
            const cachedVersion = cachedData.version || "0.0.0";
            if (cachedVersion === serverVersion) {
                trainData = cachedData.trains;
                resolve();
            } else {
                trainData = serverTrains;
                localStorage.setItem('railwayTrains', JSON.stringify({
                    trains: serverTrains,
                    version: serverVersion
                }));
                resolve();
            }
        } else {
            trainData = serverTrains;
            localStorage.setItem('railwayTrains', JSON.stringify({
                trains: serverTrains,
                version: serverVersion
            }));
            resolve();
        }
    });
}

function validateForm(event) {
    const text = document.getElementById('train-model-input').value.trim();
    document.getElementById('train_model').value = text;

    let isValid = true;
    let firstEmptyField = null;
    const validations = [
        { id: 'train_model', errorId: 'train_model-error', message: 'Train Name is required' },
        { id: 'date', errorId: 'date-error', message: 'Date of Journey is required' }
    ];

    validations.forEach(validation => {
        const inputField = document.getElementById(validation.id);
        const errorField = document.getElementById(validation.errorId);
        const textInput = validation.id === 'train_model' ? document.getElementById('train-model-input') : null;
        if (inputField && errorField && inputField.value.trim() === "") {
            errorField.textContent = validation.message;
            errorField.style.display = "block";
            errorField.classList.remove('hide');
            errorField.classList.add('show');
            (textInput || inputField).classList.add('error-input');
            if (!firstEmptyField) firstEmptyField = textInput || inputField;
            isValid = false;
        } else if (inputField && errorField) {
            errorField.classList.remove('show');
            errorField.classList.add('hide');
            (textInput || inputField).classList.remove('error-input');
        }
    });

    if (firstEmptyField) {
        focusDueToValidation = true;
        firstEmptyField.focus();
        const rect = firstEmptyField.getBoundingClientRect();
        if (rect.top < 0 || rect.bottom > window.innerHeight) {
            setTimeout(() => {
                firstEmptyField.scrollIntoView({ block: 'center' });
            }, 150);
        }
    }

    if (isValid) showLoaderAndSubmit(event);
    else event.preventDefault();
}

function focusNextUnfilledField(currentField) {
    const fields = [
        document.getElementById('train-model-input'),
        document.getElementById('date')
    ];

    const currentIndex = fields.indexOf(currentField);
    if (currentIndex === -1) return;

    for (let i = currentIndex + 1; i < fields.length; i++) {
        const nextField = fields[i];
        if (nextField && nextField.value.trim() === "") {
            suppressEvents = true;
            nextField.focus();
            if (nextField.id === 'date') openMaterialCalendar();
            setTimeout(() => suppressEvents = false, 300);
            break;
        }
    }

    if (currentIndex === 1) {
        const prevField = fields[0];
        if (prevField && prevField.value.trim() === "") {
            suppressEvents = true;
            prevField.focus();
            const dropdownMenu = document.getElementById('train-model-menu');
            if (dropdownMenu) {
                dropdownMenu.style.display = 'block';
                filterOptions(prevField.value);
            }
            setTimeout(() => suppressEvents = false, 300);
        }
    }
}

function setupTrainDropdown() {
    const dropdown = document.getElementById('train-model-dropdown');
    const textInput = document.getElementById('train-model-input');
    const dropdownMenu = document.getElementById('train-model-menu');
    const optionsContainer = document.getElementById('train-model-options');
    const hiddenInput = document.getElementById('train_model');
    const errorField = document.getElementById('train_model-error');
    let allOptions = [];
    let focusedOptionIndex = -1;

    function populateTrainOptions() {
        optionsContainer.innerHTML = '';
        trainDataFull.forEach(train => {
            const option = document.createElement('div');
            option.className = 'dropdown-option';
            option.setAttribute('data-value', train.train_name);
            option.setAttribute('data-origin', train.origin_city);
            option.setAttribute('data-destination', train.destination_city);
            option.setAttribute('data-zone', train.zone);
            option.innerHTML = `
                <div class="train-info">
                    <div class="train-name">${train.train_name}</div>
                    <div class="train-route-container">
                        <div class="train-route">${train.origin_city} → ${train.destination_city}</div>
                        <div class="train-zone">${train.zone}</div>
                    </div>
                </div>
            `;
            optionsContainer.appendChild(option);
        });
        allOptions = Array.from(optionsContainer.querySelectorAll('.dropdown-option'));
        setupOptionEventListeners();
    } function openDropdown() {
        const isInCollapsible = dropdown.closest('.collapsible-content') !== null;

        if (isInCollapsible) {
            const inputRect = textInput.getBoundingClientRect();
            dropdownMenu.style.position = 'fixed';
            dropdownMenu.style.top = (inputRect.bottom + 6) + 'px';
            dropdownMenu.style.left = inputRect.left + 'px';
            dropdownMenu.style.width = inputRect.width + 'px';
        } else {
            dropdownMenu.style.position = '';
            dropdownMenu.style.top = '';
            dropdownMenu.style.left = '';
            dropdownMenu.style.width = '';
        }

        const visibleOptions = filterOptions(textInput.value);
        focusedOptionIndex = -1;
        
        if (visibleOptions.length > 0) {
            dropdownMenu.style.display = 'block';
        } else {
            dropdownMenu.style.display = 'none';
        }
    }

    function closeDropdown() {
        dropdownMenu.classList.add('fade-out');
        setTimeout(() => {
            dropdownMenu.style.display = 'none';
            dropdownMenu.classList.remove('fade-out');
            focusedOptionIndex = -1;
            updateFocusedOption();
        }, 200);
    }

    function filterOptions(query) {
        const lowerQuery = query.toLowerCase();
        let visibleOptions = [];
        allOptions.forEach(option => {
            const trainName = option.dataset.value.toLowerCase();
            const origin = option.dataset.origin.toLowerCase();
            const destination = option.dataset.destination.toLowerCase();
            const zone = option.dataset.zone.toLowerCase();

            const isVisible = trainName.includes(lowerQuery) ||
                origin.includes(lowerQuery) ||
                destination.includes(lowerQuery) ||
                zone.includes(lowerQuery);

            option.style.display = isVisible ? 'block' : 'none';
            if (isVisible) visibleOptions.push(option);
        });
        focusedOptionIndex = -1;
        updateFocusedOption();
        return visibleOptions;
    }

    function selectOption(option) {
        const value = option.dataset.value;
        textInput.value = value;
        hiddenInput.value = value;
        allOptions.forEach(opt => opt.classList.remove('selected'));
        option.classList.add('selected');
        closeDropdown();

        if (errorField.classList.contains('show')) {
            errorField.classList.remove('show');
            errorField.classList.add('hide');
            textInput.classList.remove('error-input');
        }

        const clearButton = document.getElementById('train-model-clear');
        if (clearButton) {
            updateClearButtonVisibility(textInput, clearButton);
        }

        setTimeout(() => {
            focusNextUnfilledField(textInput);
        }, 400);
    }

    function updateFocusedOption() {
        allOptions.forEach(opt => opt.classList.remove('selected'));
        const visibleOptions = allOptions.filter(opt => opt.style.display !== 'none');
        if (focusedOptionIndex >= 0 && focusedOptionIndex < visibleOptions.length) {
            visibleOptions[focusedOptionIndex].classList.add('selected');
            visibleOptions[focusedOptionIndex].scrollIntoView({ block: 'nearest' });
        }
    }

    textInput.addEventListener('input', () => {
        hiddenInput.value = textInput.value;
        if (textInput.value.trim() === "") {
            hiddenInput.value = "";
            if (document.activeElement === textInput) {
                openDropdown();
            }
            return;
        }
        openDropdown();
    });

    textInput.addEventListener('focus', () => {
        if (!focusDueToValidation) openDropdown();
        focusDueToValidation = false;
    });

    textInput.addEventListener('keydown', (e) => {
        const visibleOptions = allOptions.filter(opt => opt.style.display !== 'none');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (focusedOptionIndex < visibleOptions.length - 1) {
                focusedOptionIndex++;
                updateFocusedOption();
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (focusedOptionIndex > 0) {
                focusedOptionIndex--;
                updateFocusedOption();
            }
        } else if (e.key === 'Enter' && focusedOptionIndex >= 0) {
            e.preventDefault();
            selectOption(visibleOptions[focusedOptionIndex]);
        } else if (e.key === 'Escape') {
            e.preventDefault();
            closeDropdown();
        }
    }); allOptions.forEach(option => {
        option.addEventListener('click', () => {
            selectOption(option);
        });
    });

    function setupOptionEventListeners() {
        allOptions.forEach(option => {
            option.addEventListener('click', () => {
                selectOption(option);
            });
        });
    }

    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target)) closeDropdown();
    });

    if (hiddenInput.value) {
        textInput.value = hiddenInput.value;
        const selectedOption = allOptions.find(opt => opt.dataset.value === hiddenInput.value);
        if (selectedOption) selectedOption.classList.add('selected');
    } if (trainDataFull.length > 0) {
        populateTrainOptions();
    }
}

const DATE_LIMIT_DAYS = 11;
const input = document.getElementById("date");

let calendarCurrentMonth;
let calendarMinDate;
let calendarMaxDate;

function getBSTDate() {
    const inputElement = document.getElementById('date');
    const bstMidnightUtc = inputElement?.dataset.bstMidnightUtc || '2025-04-03T18:00:00Z';
    const bstMidnight = new Date(bstMidnightUtc);

    const now = new Date();
    const utcOffset = now.getTimezoneOffset() * 60000;
    const bstOffset = 6 * 60 * 60 * 1000;
    const localMidnight = new Date(now.setUTCHours(0, 0, 0, 0) - utcOffset + bstOffset);

    if (localMidnight > bstMidnight) {
        const daysDiff = Math.floor((localMidnight - bstMidnight) / (24 * 60 * 60 * 1000));
        bstMidnight.setUTCDate(bstMidnight.getUTCDate() + daysDiff);
    }
    return bstMidnight;
}

function formatDate(date) {
    const monthAbbr = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ];
    
    const day = String(date.getDate()).padStart(2, '0');
    const month = monthAbbr[date.getMonth()];
    const year = date.getFullYear();
    
    return `${day}-${month}-${year}`;
}

function parseDate(dateStr) {
    const [day, monthStr, year] = dateStr.split("-");
    const monthIndex = new Date(`${monthStr} 1, ${year}`).getMonth();
    return new Date(year, monthIndex, parseInt(day, 10));
}

function isSameDate(d1, d2) {
    return d1.getDate() === d2.getDate() &&
        d1.getMonth() === d2.getMonth() &&
        d1.getFullYear() === d2.getFullYear();
}

function addDays(date, days) {
    const newDate = new Date(date);
    newDate.setUTCDate(newDate.getUTCDate() + days);
    return newDate;
}

function generateMaterialCalendar() {
    const calendarDays = document.getElementById("calendarDays");
    const calendarTitle = document.getElementById("calendarTitle");
    if (!calendarDays || !calendarTitle) return;

    calendarDays.innerHTML = "";
    calendarTitle.textContent = calendarCurrentMonth.toLocaleDateString("en-US", { month: "long", year: "numeric" });

    const prevBtn = document.getElementById("prevMonthBtn");
    const nextBtn = document.getElementById("nextMonthBtn");
    if (!prevBtn || !nextBtn) return;

    const minMonth = new Date(calendarMinDate.getFullYear(), calendarMinDate.getMonth(), 1);
    const maxMonth = new Date(calendarMaxDate.getFullYear(), calendarMaxDate.getMonth(), 1);

    prevBtn.disabled = calendarCurrentMonth <= minMonth;
    nextBtn.disabled = calendarCurrentMonth >= maxMonth;

    const monthStart = new Date(calendarCurrentMonth.getFullYear(), calendarCurrentMonth.getMonth(), 1);
    const monthEnd = new Date(calendarCurrentMonth.getFullYear(), calendarCurrentMonth.getMonth() + 1, 0);
    const startWeekday = monthStart.getDay();

    for (let i = 0; i < startWeekday; i++) {
        const spacer = document.createElement("div");
        spacer.className = "calendar-day-spacer";
        calendarDays.appendChild(spacer);
    }

    const selectedDate = input.value ? parseDate(input.value) : null;
    let current = new Date(monthStart);

    while (current <= monthEnd) {
        const dayBtn = document.createElement("button");
        dayBtn.className = "calendar-day";
        dayBtn.textContent = current.getDate();

        const currentClone = new Date(current);
        const inRange = currentClone >= calendarMinDate && currentClone <= calendarMaxDate;

        if (!inRange) {
            dayBtn.classList.add("disabled");
            dayBtn.disabled = true;
        }

        if (selectedDate && isSameDate(currentClone, selectedDate)) {
            dayBtn.classList.add("selected");
        }

        if (isSameDate(currentClone, calendarMinDate)) {
            dayBtn.classList.add("today");
        }

        dayBtn.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (inRange) {
                input.value = formatDate(currentClone);
                closeMaterialCalendar();
                const dateError = document.getElementById('date-error');
                if (dateError.classList.contains('show')) {
                    dateError.classList.remove('show');
                    dateError.classList.add('hide');
                    input.classList.remove('error-input');
                }

                setTimeout(() => {
                    focusNextUnfilledField(input);
                }, 400);
            }
        });

        calendarDays.appendChild(dayBtn);
        current.setUTCDate(current.getUTCDate() + 1);
    }
}

let calendarClickHandlerAdded = false;

function openMaterialCalendar() {
    const calendar = document.getElementById("materialCalendar");
    if (!calendar) return;

    if (calendar.style.display === "block") return;

    updateCalendarDates();
    calendar.style.display = "block";
    generateMaterialCalendar();

    suppressEvents = true;

    if (!calendarClickHandlerAdded) {
        calendar.addEventListener("mousedown", (e) => {
            e.stopPropagation();
        });
        calendar.addEventListener("click", (e) => {
            e.stopPropagation();
        });
        calendarClickHandlerAdded = true;
    }

    setTimeout(() => {
        suppressEvents = false;
    }, 200);
}

function closeMaterialCalendar() {
    const calendar = document.getElementById("materialCalendar");
    if (calendar) {
        calendar.classList.add('fade-out');
        setTimeout(() => {
            calendar.style.display = "none";
            calendar.classList.remove('fade-out');
        }, 200);
    }
}

function updateCalendarDates() {
    const todayBST = getBSTDate();
    calendarMinDate = new Date(todayBST);
    calendarMaxDate = addDays(todayBST, DATE_LIMIT_DAYS - 1);

    const selectedDate = input.value ? parseDate(input.value) : null;
    if (selectedDate && selectedDate >= calendarMinDate && selectedDate <= calendarMaxDate) {
        calendarCurrentMonth = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1);
    } else {
        calendarCurrentMonth = new Date(calendarMinDate.getFullYear(), calendarMinDate.getMonth(), 1);
    }

    const calendar = document.getElementById("materialCalendar");
    if (calendar && calendar.style.display === "block") {
        generateMaterialCalendar();
    }
}

function initMaterialCalendar() {
    if (!input) return;
    updateCalendarDates();

    input.addEventListener("focus", () => {
        if (!focusDueToValidation) openMaterialCalendar();
        focusDueToValidation = false;
    });

    input.addEventListener("click", openMaterialCalendar);

    const prevBtn = document.getElementById("prevMonthBtn");
    const nextBtn = document.getElementById("nextMonthBtn"); if (prevBtn) {
        ['mousedown', 'mouseup', 'click'].forEach(eventType => {
            prevBtn.addEventListener(eventType, (e) => {
                e.preventDefault();
                e.stopPropagation();

                if (eventType === 'click') {
                    const prevMonth = new Date(calendarCurrentMonth.getFullYear(), calendarCurrentMonth.getMonth() - 1, 1);
                    if (prevMonth >= new Date(calendarMinDate.getFullYear(), calendarMinDate.getMonth(), 1)) {
                        calendarCurrentMonth = prevMonth;
                        generateMaterialCalendar();
                    }
                }

                setTimeout(() => {
                    const calendar = document.getElementById("materialCalendar");
                    if (calendar) calendar.focus();
                }, 10);
            });
        });
    }

    if (nextBtn) {
        ['mousedown', 'mouseup', 'click'].forEach(eventType => {
            nextBtn.addEventListener(eventType, (e) => {
                e.preventDefault();
                e.stopPropagation();

                if (eventType === 'click') {
                    const nextMonth = new Date(calendarCurrentMonth.getFullYear(), calendarCurrentMonth.getMonth() + 1, 1);
                    if (nextMonth <= new Date(calendarMaxDate.getFullYear(), calendarMaxDate.getMonth(), 1)) {
                        calendarCurrentMonth = nextMonth;
                        generateMaterialCalendar();
                    }
                }

                setTimeout(() => {
                    const calendar = document.getElementById("materialCalendar");
                    if (calendar) calendar.focus();
                }, 10);
            });
        });
    }

    setInterval(() => {
        const nowBST = getBSTDate();
        if (!isSameDate(nowBST, calendarMinDate)) {
            updateCalendarDates();
        }
    }, 60000);
}

function setupCalendarBlurClose() {
    const calendar = document.getElementById("materialCalendar");
    const dateInput = document.getElementById("date");
    const prevBtn = document.getElementById("prevMonthBtn");
    const nextBtn = document.getElementById("nextMonthBtn");

    if (!calendar || !dateInput) return;

    let isInteractingWithCalendar = false;

    if (prevBtn) {
        prevBtn.addEventListener("mousedown", () => {
            isInteractingWithCalendar = true;
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener("mousedown", () => {
            isInteractingWithCalendar = true;
        });
    }

    calendar.addEventListener("mousedown", () => {
        isInteractingWithCalendar = true;
    });

    document.addEventListener("mouseup", () => {
        setTimeout(() => {
            isInteractingWithCalendar = false;
        }, 100);
    }); function handleFocusOut(e) {
        if (calendarJustOpened) return;

        setTimeout(() => {
            if (calendarJustOpened || isInteractingWithCalendar) return;

            if (!calendar.contains(document.activeElement) && document.activeElement !== dateInput) {
                closeMaterialCalendar();
            }
        }, 200);
    }
    dateInput.addEventListener("blur", handleFocusOut);
}

function setupCalendarClickOutside() {
    const calendar = document.getElementById("materialCalendar");
    const dateInput = document.getElementById("date");

    document.addEventListener("mousedown", (e) => {
        if (suppressEvents) {
            return;
        }

        if (calendar &&
            calendar.style.display === "block" &&
            !calendar.contains(e.target) &&
            e.target !== dateInput) {
            closeMaterialCalendar();
        }
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    await loadTrains();
    await loadStations();
    initMaterialCalendar();
    setupCalendarBlurClose();
    setupCalendarClickOutside();
    setupTrainDropdown();
    setupClearButton('train-model-input', 'train-model-clear');
    initializeTrainSearch();
    const matrixForm = document.getElementById("matrixForm");
    if (matrixForm) matrixForm.addEventListener("submit", validateForm);

    const fields = [
        { id: 'train_model', errorId: 'train_model-error' },
        { id: 'date', errorId: 'date-error' }
    ];

    fields.forEach(field => {
        const inputField = document.getElementById(field.id);
        const errorField = document.getElementById(field.errorId);
        const textInput = field.id === 'train_model' ? document.getElementById('train-model-input') : null;
        if (inputField && errorField) {
            const fieldElement = textInput || inputField;
            fieldElement.addEventListener('input', function () {
                if (errorField.classList.contains('show')) {
                    errorField.classList.remove('show');
                    errorField.classList.add('hide');
                    fieldElement.classList.remove('error-input');
                }
            });
            errorField.addEventListener('animationend', function (event) {
                if (event.animationName === 'fadeOutScale') {
                    errorField.style.display = 'none';
                }
            });
        }
    });
});

function showLoaderAndSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const submitButton = form.querySelector('.btn-primary');
    const searchIcon = submitButton.querySelector('.fa-th-list');

    submitButton.disabled = true;
    submitButton.style.opacity = '0.6';
    submitButton.style.cursor = 'not-allowed';

    if (searchIcon) {
        searchIcon.remove();
        const loader = document.createElement('span');
        loader.className = 'button-loader';
        for (let i = 0; i < 8; i++) {
            const segment = document.createElement('span');
            segment.className = 'loader-segment';
            loader.appendChild(segment);
        }
        submitButton.prepend(loader);
        submitButton.innerHTML = loader.outerHTML + ' Generating Matrix...';
    }

    setTimeout(() => form.submit(), 50);
}

function resetSubmitButton() {
    const submitButton = document.querySelector('#matrixForm .btn-primary');
    if (submitButton) {
        submitButton.disabled = false;
        submitButton.style.opacity = '1';
        submitButton.style.cursor = 'pointer';
        const loader = submitButton.querySelector('.button-loader');
        if (loader) {
            loader.remove();
        }
        const existingIcon = submitButton.querySelector('.fa-th-list');
        if (!existingIcon) {
            const calculatorIcon = document.createElement('i');
            calculatorIcon.className = 'fas fa-th-list';
            submitButton.prepend(calculatorIcon);
        }
    }
}

const flyoutNotification = document.getElementById('flyoutNotification');
const flyoutMessage = document.getElementById('flyoutMessage');
const flyoutClose = document.getElementById('flyoutClose');

let isOffline = !navigator.onLine;
let slowConnectionTimeout = null;

function showFlyout(message, type, autoHideDelay = 0) {
    flyoutMessage.textContent = message;
    flyoutNotification.classList.remove('warning', 'success');
    flyoutNotification.classList.add(type, 'active');

    if (autoHideDelay > 0) {
        setTimeout(hideFlyout, autoHideDelay);
    }
}

function hideFlyout() {
    flyoutNotification.classList.remove('active');
}

function checkNetworkStatus() {
    if (!navigator.onLine && !isOffline) {
        isOffline = true;
        showFlyout('No Internet Connection. Please check your network.', 'warning');
    } else if (navigator.onLine && isOffline) {
        isOffline = false;
        showFlyout('Internet Connection Restored!', 'success', 5000);
    }
}

function checkConnectionSpeed() {
    if (isOffline) return;

    const startTime = performance.now();
    fetch('https://www.google.com', { method: 'HEAD', mode: 'no-cors' })
        .then(() => {
            const duration = performance.now() - startTime;
            if (duration > 2000) {
                clearTimeout(slowConnectionTimeout);
                showFlyout('Slow Internet Connection.', 'warning', 7000);
                slowConnectionTimeout = setTimeout(checkConnectionSpeed, 30000);
            } else {
                slowConnectionTimeout = setTimeout(checkConnectionSpeed, 15000);
            }
        })
        .catch(() => {
            if (!isOffline) {
                showFlyout('Network Error. Please check your connection.', 'warning', 7000);
                slowConnectionTimeout = setTimeout(checkConnectionSpeed, 30000);
            }
        });
}

window.addEventListener('online', checkNetworkStatus);
window.addEventListener('offline', checkNetworkStatus);

flyoutClose.addEventListener('click', hideFlyout);

document.addEventListener('DOMContentLoaded', () => {
    checkNetworkStatus();
    if (navigator.onLine) {
        checkConnectionSpeed();
    }
});

window.addEventListener('pageshow', function (event) {
    if (document.getElementById('matrixForm')) {
        resetSubmitButton();
    }
});

function loadBannerImage() {
    return new Promise((resolve) => {
        const bannerContainer = document.getElementById('bannerImageContainer');
        if (!bannerContainer) {
            resolve();
            return;
        }

        const configData = JSON.parse(document.getElementById('app-config').textContent);
        const appVersion = configData.version || "1.0.0";
        const currentImageUrl = window.bannerImageUrl;

        if (!currentImageUrl) {
            resolve();
            return;
        }

        const cachedImageData = localStorage.getItem('bannerImageData');
        const img = document.createElement('img');
        img.alt = 'Banner';
        img.className = 'banner-image animated-zoom-in';

        if (cachedImageData) {
            const parsedCache = JSON.parse(cachedImageData);
            if (parsedCache.url === currentImageUrl && parsedCache.version === appVersion) {
                img.src = parsedCache.base64;
                bannerContainer.appendChild(img);
                resolve();
                return;
            }
        }

        img.src = currentImageUrl;
        bannerContainer.appendChild(img);

        localStorage.setItem('bannerImageData', JSON.stringify({
            url: currentImageUrl,
            base64: currentImageUrl,
            version: appVersion
        }));

        img.onload = () => resolve();
        img.onerror = () => {
            bannerContainer.removeChild(img);
            resolve();
        };
    });
}

document.addEventListener('DOMContentLoaded', async function () {
    if (document.getElementById('bannerModal')) {
        await loadBannerImage();

        const configData = JSON.parse(document.getElementById('app-config').textContent);
        const forceBanner = configData.force_banner || 0;
        const appVersion = configData.version || "1.0.0";

        const modal = document.getElementById('bannerModal');
        const closeModal = document.querySelector('.close-modal-text');
        const dontShowAgainCheckbox = document.getElementById('dontShowAgain');
        const storedData = JSON.parse(localStorage.getItem('bannerState') || '{}');
        const dontShowAgain = storedData.dontShowAgain === true;
        const storedVersion = storedData.version || "0.0.0";

        if (modal) {
            if (forceBanner === 1 && (!dontShowAgain || storedVersion !== appVersion)) {
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            } else if (forceBanner !== 1 && !dontShowAgain) {
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }

            if (closeModal) {
                closeModal.addEventListener('click', function () {
                    modal.classList.remove('active');
                    document.body.style.overflow = 'auto';
                    if (dontShowAgainCheckbox && dontShowAgainCheckbox.checked) {
                        localStorage.setItem('bannerState', JSON.stringify({
                            dontShowAgain: true,
                            version: appVersion
                        }));
                    }
                });
            }
        }
    }
});

function openModal(modalId, event) {
    if (event) {
        event.preventDefault();
    }
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

document.addEventListener('click', function (event) {
    if (event.target.classList.contains('legal-modal')) {
        const modalId = event.target.id;
        closeModal(modalId);
    }
});

document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
        const activeModals = document.querySelectorAll('.legal-modal[style*="display: block"]');
        activeModals.forEach(modal => {
            closeModal(modal.id);
        });
    }
});

let stationData = [];
let trainSearchSuppressDropdown = false;
let trainHighlightTimeout = null;
let originalTrainInputBg = null;

function loadStations() {
    return new Promise((resolve) => {
        const cachedStations = localStorage.getItem('railwayStations');
        const stationsElement = document.getElementById('stations-data');
        let serverStations, serverVersion;

        if (stationsElement) {
            try {
                const data = JSON.parse(stationsElement.textContent);
                serverStations = data.stations;
                serverVersion = data.version || "1.0.0";
            } catch (e) {
                serverStations = [];
                serverVersion = "1.0.0";
            }
        } else {
            serverStations = [];
            serverVersion = "1.0.0";
        }

        if (cachedStations) {
            const cachedData = JSON.parse(cachedStations);
            const cachedVersion = cachedData.version || "0.0.0";
            if (cachedVersion === serverVersion) {
                stationData = cachedData.stations;
                resolve();
            } else {
                stationData = serverStations;
                localStorage.setItem('railwayStations', JSON.stringify({
                    stations: serverStations,
                    version: serverVersion
                }));
                resolve();
            }
        } else {
            stationData = serverStations;
            localStorage.setItem('railwayStations', JSON.stringify({
                stations: serverStations,
                version: serverVersion
            }));
            resolve();
        }
    });
}

function initializeTrainSearch() {
    const collapsibleToggle = document.querySelector('.collapsible-toggle');
    const searchOrigin = document.getElementById('searchOrigin');
    const searchDestination = document.getElementById('searchDestination');
    const swapIcon = document.getElementById('trainSearchSwapIcon');
    const seeTrainListBtn = document.getElementById('seeTrainListBtn');

    if (collapsibleToggle) {
        collapsibleToggle.addEventListener('click', () => {
            const targetId = collapsibleToggle.getAttribute('data-target');
            const content = document.getElementById(targetId);
            const icon = collapsibleToggle.querySelector('i');

            if (!content.style.maxHeight || content.style.maxHeight === "0px") {
                content.style.display = "block";
                setTimeout(() => {
                    content.style.marginTop = "10px";
                    const targetHeight = content.scrollHeight;
                    content.style.maxHeight = targetHeight + "px";
                }, 10);
                collapsibleToggle.innerHTML = `<i class="fas fa-chevron-up"></i> Collapse to hide Train Search`;
            } else {
                content.style.maxHeight = "0px";
                content.style.marginTop = "0px";
                collapsibleToggle.innerHTML = `<i class="fas fa-chevron-down"></i> Expand to view Train Search`;
                setTimeout(() => {
                    content.style.display = "none";
                }, 300);
            }
        });

        const content = document.getElementById('trainSearchContent'); if (content) {
            let updateInProgress = false;
            const observer = new MutationObserver(() => {
                if (content.style.maxHeight && content.style.maxHeight !== "0px" && !updateInProgress) {
                    updateInProgress = true;
                    updateCollapsibleHeight();
                    setTimeout(() => {
                        updateInProgress = false;
                    }, 10);
                }
            });

            observer.observe(content, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['style']
            });
        }
    } if (searchOrigin) {
        searchOrigin.addEventListener("keyup", () => filterTrainSearchDropdown("searchOrigin", "searchOriginDropdown"));
        searchOrigin.addEventListener("blur", () => setTimeout(() => hideTrainSearchDropdown("searchOriginDropdown"), 200));

        searchOrigin.addEventListener('input', function () {
            const errorField = document.getElementById('searchOrigin-error');
            if (errorField && errorField.classList.contains('show')) {
                errorField.classList.remove('show');
                errorField.classList.add('hide');
                searchOrigin.classList.remove('error-input');
            }
        });

        const searchOriginErrorField = document.getElementById('searchOrigin-error');
        if (searchOriginErrorField) {
            searchOriginErrorField.addEventListener('animationend', function (event) {
                if (event.animationName === 'fadeOutScale') {
                    searchOriginErrorField.style.display = 'none';
                }
            });
        }
    }

    if (searchDestination) {
        searchDestination.addEventListener("keyup", () => filterTrainSearchDropdown("searchDestination", "searchDestinationDropdown"));
        searchDestination.addEventListener("blur", () => setTimeout(() => hideTrainSearchDropdown("searchDestinationDropdown"), 200));

        searchDestination.addEventListener('input', function () {
            const errorField = document.getElementById('searchDestination-error');
            if (errorField && errorField.classList.contains('show')) {
                errorField.classList.remove('show');
                errorField.classList.add('hide');
                searchDestination.classList.remove('error-input');
            }
        });

        const searchDestinationErrorField = document.getElementById('searchDestination-error');
        if (searchDestinationErrorField) {
            searchDestinationErrorField.addEventListener('animationend', function (event) {
                if (event.animationName === 'fadeOutScale') {
                    searchDestinationErrorField.style.display = 'none';
                }
            });
        }
    }

    if (swapIcon) {
        swapIcon.addEventListener("click", function () {
            swapTrainSearchStations();
            swapIcon.classList.add("rotate");
            setTimeout(() => {
                swapIcon.classList.remove("rotate");
            }, 400);
        });
    }

    if (seeTrainListBtn) {
        seeTrainListBtn.addEventListener('click', searchTrainsBetweenStations);
    }

    setupClearButton('searchOrigin', 'searchOriginClear');
    setupClearButton('searchDestination', 'searchDestinationClear');
}

function filterTrainSearchDropdown(inputId, dropdownId) {
    if (trainSearchSuppressDropdown || !stationData) return;
    const input = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);
    if (!input || !dropdown) return;

    const filter = input.value.toLowerCase();
    const otherInputId = inputId === 'searchOrigin' ? 'searchDestination' : 'searchOrigin';
    const otherInput = document.getElementById(otherInputId);
    const excludeStation = otherInput ? otherInput.value.trim() : '';

    dropdown.innerHTML = '';

    if (filter.length < 2 || input !== document.activeElement) {
        dropdown.style.display = "none";
        return;
    } else {
        dropdown.style.display = "block";
    }

    const filteredStations = stationData
        .filter(station => station.toLowerCase().includes(filter) && station !== excludeStation)
        .slice(0, 5);

    filteredStations.forEach(station => {
        const option = document.createElement('div');
        option.textContent = station;
        option.classList.add('dropdown-option');
        option.addEventListener('mousedown', () => selectTrainSearchOption(inputId, dropdownId, station));
        dropdown.appendChild(option);
    });

    if (filteredStations.length === 0) {
        dropdown.style.display = "none";
    }
}

function selectTrainSearchOption(inputId, dropdownId, value) {
    const input = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);
    if (!input || !dropdown) return;

    input.value = value;
    dropdown.style.display = "none";

    const clearButtonId = inputId === 'searchOrigin' ? 'searchOriginClear' : 'searchDestinationClear';
    const clearButton = document.getElementById(clearButtonId);
    if (clearButton) {
        updateClearButtonVisibility(input, clearButton);
    }

    const errorField = document.getElementById(inputId + '-error');
    if (errorField && errorField.classList.contains('show')) {
        errorField.classList.remove('show');
        errorField.classList.add('hide');
        input.classList.remove('error-input');
    }

    setTimeout(() => {
        focusNextTrainSearchField(inputId);
    }, 100);
}

function focusNextTrainSearchField(currentInputId) {
    const trainSearchFields = [
        'searchOrigin',
        'searchDestination'
    ];

    const currentIndex = trainSearchFields.indexOf(currentInputId);
    if (currentIndex === -1) return;

    if (currentIndex === 0) {
        const nextField = document.getElementById('searchDestination');
        if (nextField && nextField.value.trim() === "") {
            trainSearchSuppressDropdown = true;
            nextField.focus();
            setTimeout(() => trainSearchSuppressDropdown = false, 300);
        }
    }
    else if (currentIndex === 1) {
        const originField = document.getElementById('searchOrigin');

        if (originField && originField.value.trim() === "") {
            trainSearchSuppressDropdown = true;
            originField.focus();
            setTimeout(() => trainSearchSuppressDropdown = false, 300);
        }
    }
}

function hideTrainSearchDropdown(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    if (dropdown) dropdown.style.display = "none";
}

function swapTrainSearchStations() {
    trainSearchSuppressDropdown = true;
    const originInput = document.getElementById('searchOrigin');
    const destinationInput = document.getElementById('searchDestination');
    if (originInput && destinationInput) {
        const tempValue = originInput.value;
        originInput.value = destinationInput.value;
        destinationInput.value = tempValue;
    }
    setTimeout(() => trainSearchSuppressDropdown = false, 300);
}

async function searchTrainsBetweenStations() {
    const origin = document.getElementById('searchOrigin').value.trim();
    const destination = document.getElementById('searchDestination').value.trim();
    const resultsDiv = document.getElementById('trainSearchResults');
    const trainListDiv = document.getElementById('trainList');
    const button = document.getElementById('seeTrainListBtn');

    clearTrainSearchErrors();
    hideTrainSearchNetworkError();

    let hasErrors = false;
    let firstErrorField = null;

    if (!origin) {
        showTrainSearchError('searchOrigin', 'Origin station is required');
        hasErrors = true;
        if (!firstErrorField) firstErrorField = document.getElementById('searchOrigin');
    }

    if (!destination) {
        showTrainSearchError('searchDestination', 'Destination station is required');
        hasErrors = true;
        if (!firstErrorField) firstErrorField = document.getElementById('searchDestination');
    }

    if (origin && destination && origin === destination) {
        showTrainSearchError('searchDestination', 'Origin and destination stations cannot be the same');
        hasErrors = true;
        if (!firstErrorField) firstErrorField = document.getElementById('searchDestination');
    }

    if (hasErrors) {
        if (firstErrorField) {
            firstErrorField.focus();
            firstErrorField.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return;
    }
    button.disabled = true;
    button.style.opacity = '0.6';
    button.style.cursor = 'not-allowed';
    resultsDiv.style.display = 'none';
    const listIcon = button.querySelector('.fa-list');
    if (listIcon) {
        listIcon.remove();
        const loader = document.createElement('span');
        loader.className = 'button-loader';
        for (let i = 0; i < 8; i++) {
            const segment = document.createElement('span');
            segment.className = 'loader-segment';
            loader.appendChild(segment);
        }
        button.prepend(loader);
        button.innerHTML = loader.outerHTML + ' Searching Trains...';
    }

    try {
        const response = await fetch('/search_trains', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                origin: origin,
                destination: destination
            })
        });

        const data = await response.json();

        if (!response.ok) {
            const errorMessage = data.error || `Server error (${response.status})`;
            showTrainSearchNetworkError(errorMessage);
            return;
        } if (data.success && data.trains && data.trains.length > 0) {
            hideTrainSearchNetworkError();
            displayTrainResults(data.trains, origin, destination);
            resultsDiv.style.display = 'block';
            updateCollapsibleHeight();
            setTimeout(() => {
                const rect = resultsDiv.getBoundingClientRect();
                if (rect.top < 0 || rect.bottom > window.innerHeight) {
                    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 100);
        } else if (data.error) {
            showTrainSearchNetworkError(data.error);
        } else {
            showTrainSearchNetworkError('No trains found for this route');
        }
    } catch (error) {
        showTrainSearchNetworkError('Unable to connect to the server. Please check your internet connection and try again.');
    } finally {
        button.disabled = false;
        button.style.opacity = '1';
        button.style.cursor = 'pointer';

        const loader = button.querySelector('.button-loader');
        if (loader) {
            loader.remove();
        }

        const existingIcon = button.querySelector('.fa-list');
        if (!existingIcon) {
            const listIcon = document.createElement('i');
            listIcon.className = 'fas fa-list';
            button.innerHTML = '';
            button.appendChild(listIcon);
            button.appendChild(document.createTextNode(' See Train List'));
        }
    }
}

function displayTrainResults(trains, origin, destination) {
    const trainListDiv = document.getElementById('trainList');

    if (trains.length === 0) {
        showTrainSearchNetworkError('No trains found for this route');
        return;
    }

    const trainElements = trains.map(train => {
        const departureMatch = train.departure_time.match(/(\d{1,2}:\d{2}\s*[ap]m)/i);
        const arrivalMatch = train.arrival_time.match(/(\d{1,2}:\d{2}\s*[ap]m)/i);

        const depTime = departureMatch ? departureMatch[1] : train.departure_time;
        const arrTime = arrivalMatch ? arrivalMatch[1] : train.arrival_time;

        return `
            <div class="train-item" onclick="selectTrainFromList('${train.trip_number}')">
                <div class="train-item-header">${train.trip_number}</div>
                <div class="train-item-details">
                    <div class="train-route"><strong>${origin}&nbsp;&nbsp;→&nbsp;&nbsp;${destination}</strong></div>
                    <div class="train-time"><strong>Dep:</strong> ${depTime} &nbsp;&nbsp;&nbsp;<strong>|</strong>&nbsp;&nbsp;&nbsp; <strong>Arr:</strong> ${arrTime}</div>
                </div>
            </div>
        `;
    }).join(''); trainListDiv.innerHTML = trainElements;

    updateCollapsibleHeight();
    setTimeout(() => {
        const resultsDiv = document.getElementById('trainSearchResults');
        if (resultsDiv) {
            const rect = resultsDiv.getBoundingClientRect();
            if (rect.top < 0 || rect.bottom > window.innerHeight) {
                resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    }, 150);
}

function updateCollapsibleHeight() {
    const content = document.getElementById('trainSearchContent');
    if (content && content.style.maxHeight && content.style.maxHeight !== "0px") {
        const newHeight = content.scrollHeight;
        content.style.maxHeight = newHeight + "px";
    }
}

window.addEventListener('resize', () => {
    const content = document.getElementById('trainSearchContent');
    if (content && content.style.maxHeight && content.style.maxHeight !== "0px") {
        updateCollapsibleHeight();
    }
});

function selectTrainFromList(trainName) {
    const trainModelInput = document.getElementById('train-model-input');
    const trainModelHidden = document.getElementById('train_model');

    if (trainModelInput && trainModelHidden) {
        if (originalTrainInputBg === null) {
            originalTrainInputBg = window.getComputedStyle(trainModelInput).backgroundColor;
        }

        trainModelInput.value = trainName;
        trainModelHidden.value = trainName;

        if (trainHighlightTimeout) {
            clearTimeout(trainHighlightTimeout);
            trainHighlightTimeout = null;
        }

        trainModelInput.style.backgroundColor = originalTrainInputBg;

        setTimeout(() => {
            trainModelInput.style.backgroundColor = '#d4edda';

            trainHighlightTimeout = setTimeout(() => {
                trainModelInput.style.backgroundColor = originalTrainInputBg;
                trainHighlightTimeout = null;
            }, 1000);
        }, 50);

        setTimeout(() => {
            trainModelInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 200);
    }
}

function showTrainSearchError(fieldId, message) {
    const errorField = document.getElementById(fieldId + '-error');
    const inputField = document.getElementById(fieldId);

    if (errorField && inputField) {
        if (!errorField.classList.contains('show') || errorField.textContent !== message) {
            errorField.textContent = message;
            errorField.style.display = 'block';
            errorField.classList.remove('hide');
            errorField.classList.add('show');
            inputField.classList.add('error-input');
        }
    }
}

function clearTrainSearchErrors() {
    const errorFields = ['searchOrigin-error', 'searchDestination-error'];
    const inputFields = ['searchOrigin', 'searchDestination'];

    errorFields.forEach((errorId, index) => {
        const errorField = document.getElementById(errorId);
        const inputField = document.getElementById(inputFields[index]);

        if (errorField && inputField && inputField.value.trim() !== '') {
            errorField.classList.remove('show');
            errorField.classList.add('hide');
            inputField.classList.remove('error-input');
        }
    });
}

function showTrainSearchNetworkError(message) {
    const errorSection = document.getElementById('trainSearchError');
    if (errorSection) {
        errorSection.innerHTML = `<div class="train-search-error-message">
            <i class="fas fa-exclamation-circle error-icon"></i> ${message}
        </div>`;
        errorSection.style.display = 'block';
        updateCollapsibleHeight();
        setTimeout(() => {
            const rect = errorSection.getBoundingClientRect();
            if (rect.top < 0 || rect.bottom > window.innerHeight) {
                errorSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 100);
    }
}

function hideTrainSearchNetworkError() {
    const errorSection = document.getElementById('trainSearchError');
    if (errorSection) {
        errorSection.style.display = 'none';
        errorSection.innerHTML = '';
        updateCollapsibleHeight();
    }
}

function setupClearButton(inputId, clearButtonId) {
    const input = document.getElementById(inputId);
    const clearButton = document.getElementById(clearButtonId);

    if (!input || !clearButton) return;

    updateClearButtonVisibility(input, clearButton);

    input.addEventListener('input', () => {
        updateClearButtonVisibility(input, clearButton);
    });

    clearButton.addEventListener('click', () => {
        input.value = '';
        
        if (inputId === 'searchOrigin') {
            hideTrainSearchDropdown('searchOriginDropdown');
        } else if (inputId === 'searchDestination') {
            hideTrainSearchDropdown('searchDestinationDropdown');
        } else if (inputId === 'train-model-input') {
            const hiddenInput = document.getElementById('train_model');
            if (hiddenInput) hiddenInput.value = '';
            const dropdownMenu = document.getElementById('train-model-menu');
            if (dropdownMenu) dropdownMenu.style.display = 'none';
            
            const errorField = document.getElementById('train_model-error');
            if (errorField && errorField.classList.contains('show')) {
                errorField.classList.remove('show');
                errorField.classList.add('hide');
                input.classList.remove('error-input');
            }
        }
        
        input.focus();
        updateClearButtonVisibility(input, clearButton);

        const inputEvent = new Event('input', { bubbles: true });
        input.dispatchEvent(inputEvent);
    });
}

function updateClearButtonVisibility(input, clearButton) {
    if (input.value.trim() !== '') {
        clearButton.style.display = 'flex';
    } else {
        clearButton.style.display = 'none';
    }
}