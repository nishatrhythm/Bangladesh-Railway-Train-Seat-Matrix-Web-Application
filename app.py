from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from datetime import datetime, timedelta
import json, pytz, os, re, uuid, base64, requests
from matrixCalculator import compute_matrix
from request_queue import RequestQueue

app = Flask(__name__)
app.secret_key = "super_secret_key"

RESULT_CACHE = {}
STATION_NAME_MAPPING = {"Coxs Bazar": "Cox's Bazar"}

with open('config.json', 'r', encoding='utf-8') as config_file:
    CONFIG = json.load(config_file)

with open('static/js/script.js', 'r', encoding='utf-8') as js_file:
    SCRIPT_JS_CONTENT = js_file.read()
with open('static/css/styles.css', 'r', encoding='utf-8') as css_file:
    STYLES_CSS_CONTENT = css_file.read()

default_banner_path = 'static/images/sample_banner.png'
DEFAULT_BANNER_IMAGE = ""
if os.path.exists(default_banner_path):
    try:
        with open(default_banner_path, 'rb') as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
            DEFAULT_BANNER_IMAGE = f"data:image/png;base64,{encoded_image}"
    except Exception:
        pass

def configure_request_queue():
    max_concurrent = CONFIG.get("queue_max_concurrent", 1)
    cooldown_period = CONFIG.get("queue_cooldown_period", 3)
    batch_cleanup_threshold = CONFIG.get("queue_batch_cleanup_threshold", 10)
    cleanup_interval = CONFIG.get("queue_cleanup_interval", 30)
    heartbeat_timeout = CONFIG.get("queue_heartbeat_timeout", 90)
    
    return RequestQueue(
        max_concurrent=max_concurrent, 
        cooldown_period=cooldown_period,
        batch_cleanup_threshold=batch_cleanup_threshold,
        cleanup_interval=cleanup_interval,
        heartbeat_timeout=heartbeat_timeout
    )

request_queue = configure_request_queue()

with open('trains_en.json', 'r') as f:
    trains_data = json.load(f)
    trains_full = trains_data['trains']
    trains = [train['train_name'] for train in trains_data['trains']]

with open('stations_en.json', 'r') as f:
    stations_data = json.load(f)
    stations = stations_data['stations']

def check_maintenance():
    if CONFIG.get("is_maintenance", 0):
        return render_template(
            'notice.html',
            message=CONFIG.get("maintenance_message", ""),
            styles_css=STYLES_CSS_CONTENT,
            script_js=SCRIPT_JS_CONTENT
        )
    return None

@app.before_request
def block_cloudflare_noise():
    if request.path.startswith('/cdn-cgi/'):
        return '', 404

@app.after_request
def set_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def home():
    maintenance_response = check_maintenance()
    if maintenance_response:
        return maintenance_response

    error = session.pop('error', None)

    app_version = CONFIG.get("version", "1.0.0")
    config = CONFIG.copy()
    
    banner_image = CONFIG.get("image_link") or DEFAULT_BANNER_IMAGE
    if not banner_image:
        banner_image = ""

    bst_tz = pytz.timezone('Asia/Dhaka')
    bst_now = datetime.now(bst_tz)
    min_date = bst_now.replace(hour=0, minute=0, second=0, microsecond=0)
    max_date = min_date + timedelta(days=10)
    bst_midnight_utc = min_date.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

    if request.method == 'GET' and not session.get('form_submitted', False):
        session.pop('form_values', None)
    else:
        session['form_submitted'] = False

    form_values = session.get('form_values', {})
    if not form_values:
        form_values = None

    return render_template(
        'index.html',
        error=error,
        app_version=app_version,
        CONFIG=config,
        is_banner_enabled=CONFIG.get("is_banner_enabled", 0),
        banner_image=banner_image,
        min_date=min_date.strftime("%Y-%m-%d"),
        max_date=max_date.strftime("%Y-%m-%d"),
        bst_midnight_utc=bst_midnight_utc,
        show_disclaimer=True,
        form_values=form_values,
        trains=trains,
        trains_full=trains_full,
        stations=stations,
        styles_css=STYLES_CSS_CONTENT,
        script_js=SCRIPT_JS_CONTENT
    )

@app.route('/matrix', methods=['GET', 'POST'])
def matrix():
    maintenance_response = check_maintenance()
    if maintenance_response:
        return maintenance_response
    
    if request.method == 'GET':
        abort(404)

    train_model_full = request.form.get('train_model', '').strip()
    journey_date_str = request.form.get('date', '').strip()

    if not train_model_full or not journey_date_str:
        session['error'] = "Both Train Name and Journey Date are required."
        return redirect(url_for('home'))

    try:
        date_obj = datetime.strptime(journey_date_str, '%d-%b-%Y')
        api_date_format = date_obj.strftime('%Y-%m-%d')
    except ValueError:
        session['error'] = "Invalid date format. Use DD-MMM-YYYY (e.g. 15-Nov-2024)."
        return redirect(url_for('home'))

    model_match = re.match(r'.*\((\d+)\)$', train_model_full)
    if model_match:
        train_model = model_match.group(1)
    else:
        train_model = train_model_full.split('(')[0].strip()

    try:
        form_values = {
            'train_model': train_model_full,
            'date': journey_date_str
        }
        session['form_values'] = form_values
        session['form_submitted'] = True

        if CONFIG.get("queue_enabled", True):
            request_id = request_queue.add_request(
                process_matrix_request,
                {
                    'train_model': train_model,
                    'journey_date_str': journey_date_str,
                    'api_date_format': api_date_format,
                    'form_values': form_values
                }
            )
            
            session['queue_request_id'] = request_id
            return redirect(url_for('queue_wait'))
        else:
            result = process_matrix_request(train_model, journey_date_str, api_date_format, form_values)
            
            if "error" in result:
                session['error'] = result["error"]
                return redirect(url_for('home'))
            
            result_id = str(uuid.uuid4())
            RESULT_CACHE[result_id] = result["result"]
            session['result_id'] = result_id
            return redirect(url_for('matrix_result'))
    except Exception as e:
        session['error'] = f"{str(e)}"
        return redirect(url_for('home'))

def process_matrix_request(train_model, journey_date_str, api_date_format, form_values):
    try:
        result = compute_matrix(train_model, journey_date_str, api_date_format)
        if not result or 'stations' not in result:
            return {"error": "No data received. Please try a different train or date."}
        
        return {"success": True, "result": result, "form_values": form_values}
    except Exception as e:
        return {"error": str(e)}

@app.route('/queue_wait')
def queue_wait():
    maintenance_response = check_maintenance()
    if maintenance_response:
        return maintenance_response
    
    request_id = session.get('queue_request_id')
    if not request_id:
        session['error'] = "Your request session has expired. Please search again."
        return redirect(url_for('home'))
    
    status = request_queue.get_request_status(request_id)
    if not status:
        session['error'] = "Your request could not be found. Please search again."
        return redirect(url_for('home'))
    
    if request.args.get('refresh_check') == 'true':
        request_queue.cancel_request(request_id)
        session.pop('queue_request_id', None)
        session['error'] = "Page was refreshed. Please start a new search."
        return redirect(url_for('home'))
    
    form_values = session.get('form_values', {})
    
    return render_template(
        'queue.html',
        request_id=request_id,
        status=status, 
        form_values=form_values,
        styles_css=STYLES_CSS_CONTENT,
        script_js=SCRIPT_JS_CONTENT
    )

@app.route('/queue_status/<request_id>')
def queue_status(request_id):
    status = request_queue.get_request_status(request_id)
    if not status:
        return jsonify({"error": "Request not found"}), 404
    
    if status["status"] == "failed":
        result = request_queue.get_request_result(request_id)
        if result and "error" in result:
            status["errorMessage"] = result["error"]
    
    return jsonify(status)

@app.route('/cancel_request/<request_id>', methods=['POST'])
def cancel_request(request_id):
    try:
        removed = request_queue.cancel_request(request_id)
        
        if session.get('queue_request_id') == request_id:
            session.pop('queue_request_id', None)
        
        stats = request_queue.get_queue_stats()
        if stats.get('cancelled_pending', 0) > 5:
            request_queue.force_cleanup()
        
        return jsonify({"cancelled": removed, "status": "success"})
    except Exception as e:
        return jsonify({"cancelled": False, "status": "error", "error": str(e)}), 500

@app.route('/cancel_request_beacon/<request_id>', methods=['POST'])
def cancel_request_beacon(request_id):
    try:
        request_queue.cancel_request(request_id)
        return '', 204
    except Exception:
        return '', 204

@app.route('/queue_heartbeat/<request_id>', methods=['POST'])
def queue_heartbeat(request_id):
    try:
        updated = request_queue.update_heartbeat(request_id)
        return jsonify({"status": "success", "active": updated})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/show_results')
def show_results():
    maintenance_response = check_maintenance()
    if maintenance_response:
        return maintenance_response

    request_id = session.get('queue_request_id')
    if not request_id:
        session['error'] = "Your request session has expired. Please search again."
        return redirect(url_for('home'))
    return redirect(url_for('show_results_with_id', request_id=request_id))

@app.route('/show_results/<request_id>')
def show_results_with_id(request_id):
    maintenance_response = check_maintenance()
    if maintenance_response:
        return maintenance_response

    queue_result = request_queue.get_request_result(request_id)
    
    if not queue_result:
        session['error'] = "Your request has expired or could not be found. Please search again."
        return redirect(url_for('home'))
    
    if "error" in queue_result:
        session['error'] = queue_result["error"]
        return redirect(url_for('home'))
    
    if not queue_result.get("success"):
        session['error'] = "An error occurred while processing your request. Please try again."
        return redirect(url_for('home'))
    
    result = queue_result.get("result", {})
    form_values = queue_result.get("form_values", {})
    
    if session.get('queue_request_id') == request_id:
        session.pop('queue_request_id', None)
    
    return render_template(
        'matrix.html',
        **result,
        form_values=form_values,
        styles_css=STYLES_CSS_CONTENT,
        script_js=SCRIPT_JS_CONTENT
    )

@app.route('/matrix_result')
def matrix_result():
    maintenance_response = check_maintenance()
    if maintenance_response:
        return maintenance_response

    result_id = session.pop('result_id', None)
    result = RESULT_CACHE.pop(result_id, None) if result_id else None
    form_values = session.get('form_values', None)

    if not result:
        return redirect(url_for('home'))

    return render_template(
        'matrix.html',
        **result,
        form_values=form_values,
        styles_css=STYLES_CSS_CONTENT,
        script_js=SCRIPT_JS_CONTENT
    )

@app.route('/queue_stats')
def queue_stats():
    try:
        stats = request_queue.get_queue_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/queue_cleanup', methods=['POST'])
def queue_cleanup():
    try:
        request_queue.force_cleanup()
        stats = request_queue.get_queue_stats()
        return jsonify({"status": "success", "message": "Cleanup completed", "stats": stats})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/search_trains', methods=['GET', 'POST'])
def search_trains():
    maintenance_response = check_maintenance()
    if maintenance_response:
        return jsonify({"error": "Service under maintenance"}), 503
    
    if request.method == 'GET':
        abort(404)
    
    try:
        data = request.get_json()
        origin = data.get('origin', '').strip()
        destination = data.get('destination', '').strip()
        
        if not origin or not destination:
            return jsonify({"error": "Both origin and destination are required"}), 400
        
        origin = STATION_NAME_MAPPING.get(origin, origin)
        destination = STATION_NAME_MAPPING.get(destination, destination)
        
        today = datetime.now()
        date1 = today + timedelta(days=8)
        date2 = today + timedelta(days=9)
        
        date1_str = date1.strftime('%d-%b-%Y')
        date2_str = date2.strftime('%d-%b-%Y')
        
        trains_day1 = fetch_trains_for_date(origin, destination, date1_str)
        trains_day2 = fetch_trains_for_date(origin, destination, date2_str)
        
        common_trains = get_common_trains(trains_day1, trains_day2)
        
        return jsonify({
            "success": True,
            "trains": common_trains,
            "dates": [date1_str, date2_str]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def fetch_trains_for_date(origin, destination, date_str):
    url = "https://railspaapi.shohoz.com/v1.0/web/bookings/search-trips-v2"
    params = {
        'from_city': origin,
        'to_city': destination,
        'date_of_journey': date_str,
        'seat_class': 'S_CHAIR'
    }
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 403:
                raise Exception("Rate limit exceeded. Please try again later.")
                
            if response.status_code >= 500:
                retry_count += 1
                if retry_count == max_retries:
                    raise Exception("We're unable to connect to the Bangladesh Railway website right now. Please try again in a few minutes.")
                continue
                
            response.raise_for_status()
            
            data = response.json()
            trains = data.get('data', {}).get('trains', [])
            
            return trains
            
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response and e.response.status_code == 403:
                raise Exception("Rate limit exceeded. Please try again later.")
            retry_count += 1
            if retry_count == max_retries:
                return []
    
    return []

def get_common_trains(trains_day1, trains_day2):
    all_trains = {}
    
    for train in trains_day1:
        trip_number = train.get('trip_number', '')
        if trip_number and trip_number not in all_trains:
            all_trains[trip_number] = {
                'trip_number': trip_number,
                'departure_time': train.get('departure_date_time', ''),
                'arrival_time': train.get('arrival_date_time', ''),
                'travel_time': train.get('travel_time', ''),
                'origin_city': train.get('origin_city_name', ''),
                'destination_city': train.get('destination_city_name', ''),
                'sort_time': extract_time_for_sorting(train.get('departure_date_time', ''))
            }
    
    for train in trains_day2:
        trip_number = train.get('trip_number', '')
        if trip_number and trip_number not in all_trains:
            all_trains[trip_number] = {
                'trip_number': trip_number,
                'departure_time': train.get('departure_date_time', ''),
                'arrival_time': train.get('arrival_date_time', ''),
                'travel_time': train.get('travel_time', ''),
                'origin_city': train.get('origin_city_name', ''),
                'destination_city': train.get('destination_city_name', ''),
                'sort_time': extract_time_for_sorting(train.get('departure_date_time', ''))
            }
    
    trains_list = list(all_trains.values())
    trains_list.sort(key=lambda x: x.get('sort_time', ''))
    
    for train in trains_list:
        train.pop('sort_time', None)
    
    return trains_list

def extract_time_for_sorting(departure_time_str):
    try:
        if not departure_time_str:
            return "99:99"
            
        time_part = departure_time_str.split(',')[-1].strip()
        
        if 'am' in time_part.lower():
            time_clean = time_part.lower().replace('am', '').strip()
            hour, minute = time_clean.split(':')
            hour = int(hour)
            if hour == 12:
                hour = 0
        elif 'pm' in time_part.lower():
            time_clean = time_part.lower().replace('pm', '').strip()
            hour, minute = time_clean.split(':')
            hour = int(hour)
            if hour != 12:
                hour += 12
        else:
            return "99:99"
            
        return f"{hour:02d}:{minute}"
        
    except Exception:
        return "99:99"

@app.errorhandler(404)
def page_not_found(e):
    maintenance_response = check_maintenance()
    if maintenance_response:
        return maintenance_response
    return render_template('404.html', styles_css=STYLES_CSS_CONTENT, script_js=SCRIPT_JS_CONTENT), 404

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))