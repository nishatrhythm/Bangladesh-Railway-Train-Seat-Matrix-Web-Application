document.documentElement.classList.add('js-enabled');

let focusDueToValidation = false;
let suppressEvents = false;

function validateForm(event) {
    const text = document.getElementById('train-model-input').value.trim();
    document.getElementById('train_model').value = text;

    let isValid = true;
    let firstEmptyField = null;
    const validations = [
        { id: 'train_model', errorId: 'train_model-error', message: 'Train Model is required' },
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

    if (!isValid) event.preventDefault();
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
    let allOptions = Array.from(optionsContainer.querySelectorAll('.dropdown-option'));
    let focusedOptionIndex = -1;

    function openDropdown() {
        dropdownMenu.style.display = 'block';
        filterOptions(textInput.value);
        focusedOptionIndex = -1;
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
            const text = option.textContent.toLowerCase();
            const isVisible = text.includes(lowerQuery);
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

        focusNextUnfilledField(textInput);
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
            closeDropdown();
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
    });

    allOptions.forEach(option => {
        option.addEventListener('click', () => {
            selectOption(option);
        });
    });

    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target)) closeDropdown();
    });

    if (hiddenInput.value) {
        textInput.value = hiddenInput.value;
        const selectedOption = allOptions.find(opt => opt.dataset.value === hiddenInput.value);
        if (selectedOption) selectedOption.classList.add('selected');
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
    return date.toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
    }).replace(/ /g, "-");
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
                focusNextUnfilledField(input);
            }
        });

        calendarDays.appendChild(dayBtn);
        current.setUTCDate(current.getUTCDate() + 1);
    }
}

let calendarJustOpened = false;

function openMaterialCalendar() {
    const calendar = document.getElementById("materialCalendar");
    if (!calendar) return;
    
    if (calendar.style.display === "block") return;
    
    updateCalendarDates();
    calendar.style.display = "block";
    generateMaterialCalendar();

    calendarJustOpened = true;
    
    if (window.calendarOpenTimeout) clearTimeout(window.calendarOpenTimeout);
    
    window.calendarOpenTimeout = setTimeout(() => {
        calendarJustOpened = false;
    }, 500);
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
    calendarCurrentMonth = new Date(calendarMinDate.getFullYear(), calendarMinDate.getMonth(), 1);
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
    const nextBtn = document.getElementById("nextMonthBtn");    if (prevBtn) {
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
    });    function handleFocusOut(e) {
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
    
    document.addEventListener('mousedown', (event) => {
        if (calendarJustOpened) return;
        
        if (calendar && 
            calendar.style.display === 'block' && 
            !calendar.contains(event.target) && 
            event.target !== dateInput) {
            closeMaterialCalendar();
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initMaterialCalendar();
    setupCalendarBlurClose();
    setupCalendarClickOutside();
    setupTrainDropdown();
    const matrixForm = document.getElementById("matrixForm");
    if (matrixForm) matrixForm.addEventListener("submit", function (event) {
        validateForm(event);
        if (!event.defaultPrevented) {
            showLoaderAndSubmit(event);
        }
    });

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
    const searchIcon = submitButton.querySelector('.fa-calculator');

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
    }
    
    setTimeout(() => form.submit(), 50);
}