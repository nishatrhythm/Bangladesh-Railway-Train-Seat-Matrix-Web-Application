import requests
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

SEAT_TYPES = [
    "AC_B", "AC_S", "SNIGDHA", "F_BERTH", "F_SEAT", "F_CHAIR",
    "S_CHAIR", "SHOVAN", "SHULOV", "AC_CHAIR"
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
                        seat_info[stype] = {
                            "online": seat["seat_counts"]["online"],
                            "offline": seat["seat_counts"]["offline"],
                            "fare": float(seat["fare"]),
                            "vat_amount": float(seat["vat_amount"])
                        }
                return (from_city, to_city, seat_info)

        return (from_city, to_city, None)

    except requests.RequestException:
        return (from_city, to_city, None)

def compute_matrix(train_model: str, journey_date_str: str, api_date_format: str) -> dict:
    train_data = fetch_train_data(train_model, api_date_format)
    if not train_data:
        raise Exception("No train data found.")

    stations = [r['city'] for r in train_data['routes']]
    days = train_data['days']
    train_name = train_data['train_name']

    weekday = datetime.strptime(journey_date_str, "%d-%b-%Y").strftime("%a")
    if weekday not in days:
        raise Exception(f"The train '{train_name}' does not run on {weekday}.")

    # Initialize matrix
    fare_matrices = {
        seat_type: {from_city: {} for from_city in stations} for seat_type in SEAT_TYPES
    }

    seat_type_has_data = {seat_type: False for seat_type in SEAT_TYPES}

    # Multithreaded fetching
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(get_seat_availability, train_model, journey_date_str, from_city, to_city)
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

    return {
        "train_model": train_model,
        "train_name": train_name,
        "date": journey_date_str,
        "stations": stations,
        "seat_types": SEAT_TYPES,
        "fare_matrices": fare_matrices,
        "has_data_map": seat_type_has_data
    }