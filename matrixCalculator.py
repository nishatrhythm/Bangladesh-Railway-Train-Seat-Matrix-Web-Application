import requests
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

SEAT_TYPES = [
    "S_CHAIR", "SHOVAN", "SNIGDHA", "F_SEAT", "F_CHAIR", "AC_S", "F_BERTH", "AC_B", "SHULOV", "AC_CHAIR"
]

def fetch_train_data(model: str, api_date: str) -> dict:
    url = "https://railspaapi.shohoz.com/v1.0/web/train-routes"
    payload = {
        "model": model,
        "departure_date_time": api_date
    }
    headers = {'Content-Type': 'application/json'}

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json().get("data")

def get_seat_availability(train_model: str, journey_date: str, from_city: str, to_city: str) -> tuple:
    url = "https://railspaapi.shohoz.com/v1.0/web/bookings/search-trips-v2"
    params = {
        "from_city": from_city,
        "to_city": to_city,
        "date_of_journey": journey_date,
        "seat_class": "SHULOV"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        trains = response.json().get("data", {}).get("trains", [])

        for train in trains:
            if train.get("train_model") == train_model:
                seat_info = {stype: {"online": 0, "offline": 0, "fare": 0, "vat_amount": 0} for stype in SEAT_TYPES}
                for seat in train.get("seat_types", []):
                    stype = seat["type"]
                    if stype in seat_info:
                        fare = float(seat["fare"])
                        vat_amount = float(seat["vat_amount"])
                        if stype in ["AC_B", "F_BERTH"]:
                            fare += 50
                        seat_info[stype] = {
                            "online": seat["seat_counts"]["online"],
                            "offline": seat["seat_counts"]["offline"],
                            "fare": fare,
                            "vat_amount": vat_amount
                        }
                return (from_city, to_city, seat_info)

        return (from_city, to_city, None)

    except requests.RequestException:
        return (from_city, to_city, None)

def compute_matrix(train_model: str, journey_date_str: str, api_date_format: str) -> dict:
    train_data = fetch_train_data(train_model, api_date_format)
    if not train_data or not train_data.get("train_name") or not train_data.get("routes"):
        raise Exception("No information found for this train. Please try another train or date.")

    stations = [r['city'] for r in train_data['routes']]
    days = train_data['days']
    train_name = train_data['train_name']
    routes = train_data['routes']
    base_date = datetime.strptime(journey_date_str, "%d-%b-%Y")
    current_date = base_date
    previous_time = None

    MAX_REASONABLE_GAP_HOURS = 12

    station_dates = {}
    for i, stop in enumerate(routes):
        stop["display_date"] = None
        time_str = stop.get("departure_time") or stop.get("arrival_time")

        if time_str and "BST" in time_str:
            time_clean = time_str.replace(" BST", "").strip()
            try:
                hour_min, am_pm = time_clean.split(' ')
                hour, minute = map(int, hour_min.split(':'))
                am_pm = am_pm.lower()

                if am_pm == "pm" and hour != 12:
                    hour += 12
                elif am_pm == "am" and hour == 12:
                    hour = 0

                current_time = timedelta(hours=hour, minutes=minute)

                if previous_time is not None:
                    time_diff = (current_time - previous_time).total_seconds() / 3600
                    if current_time < previous_time:
                        time_diff = ((current_time + timedelta(days=1)) - previous_time).total_seconds() / 3600
                        if time_diff < MAX_REASONABLE_GAP_HOURS:
                            routes[i - 1]["display_date"] = current_date.strftime("%d %b")
                            current_date += timedelta(days=1)
                            stop["display_date"] = current_date.strftime("%d %b")
                        else:
                            hours = int(time_diff)
                            minutes = int((time_diff - hours) * 60)

                previous_time = current_time
            except Exception:
                continue

        station_dates[stop['city']] = current_date.strftime("%Y-%m-%d")

    total_duration = train_data.get('total_duration', 'N/A')

    weekday_short = datetime.strptime(journey_date_str, "%d-%b-%Y").strftime("%a")
    weekday_full = datetime.strptime(journey_date_str, "%d-%b-%Y").strftime("%A")
    if weekday_short not in days:
        raise Exception(f"{train_name} does not run on {weekday_full}.")

    fare_matrices = {
        seat_type: {from_city: {} for from_city in stations} for seat_type in SEAT_TYPES
    }

    seat_type_has_data = {seat_type: False for seat_type in SEAT_TYPES}

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(
                get_seat_availability,
                train_model,
                datetime.strptime(station_dates[from_city], "%Y-%m-%d").strftime("%d-%b-%Y"),
                from_city,
                to_city
            )
            for i, from_city in enumerate(stations)
            for j, to_city in enumerate(stations)
            if i < j
        ]
        for future in as_completed(futures):
            from_city, to_city, seat_info = future.result()
            for seat_type in SEAT_TYPES:
                fare_matrices[seat_type][from_city][to_city] = (
                    seat_info.get(seat_type, {"online": 0, "offline": 0, "fare": 0})
                    if seat_info else {"online": 0, "offline": 0, "fare": 0}
                )
                if seat_info:
                    for seat_type in SEAT_TYPES:
                        if seat_info[seat_type]["online"] + seat_info[seat_type]["offline"] > 0:
                            seat_type_has_data[seat_type] = True

    if not any(seat_type_has_data.values()):
        raise Exception("No seats available for the selected train and date. Please try a different date or train.")
    
    station_dates_formatted = {
        station: datetime.strptime(date_str, "%Y-%m-%d").strftime("%d-%b-%Y")
        for station, date_str in station_dates.items()
    }

    unique_dates = set(station_dates.values())
    has_segmented_dates = len(unique_dates) > 1
    next_day_str = ""
    prev_day_str = ""
    if has_segmented_dates:
        date_obj = datetime.strptime(journey_date_str, "%d-%b-%Y")
        next_day_obj = date_obj + timedelta(days=1)
        prev_day_obj = date_obj - timedelta(days=1)
        next_day_str = next_day_obj.strftime("%d-%b-%Y")
        prev_day_str = prev_day_obj.strftime("%d-%b-%Y")

    return {
        "train_model": train_model,
        "train_name": train_name,
        "date": journey_date_str,
        "stations": stations,
        "seat_types": SEAT_TYPES,
        "fare_matrices": fare_matrices,
        "has_data_map": seat_type_has_data,
        "routes": routes,
        "days": days,
        "total_duration": total_duration,
        "station_dates": station_dates,
        "station_dates_formatted": station_dates_formatted,
        "has_segmented_dates": has_segmented_dates,
        "next_day_str": next_day_str,
        "prev_day_str": prev_day_str,
    }