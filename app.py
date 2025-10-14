from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from datetime import datetime, timedelta
import json, pytz, os, re, uuid, base64, requests, logging, sys
from matrixCalculator import compute_matrix
from request_queue import RequestQueue

app = Flask(__name__)
app.secret_key = "super_secret_key"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

RESULT_CACHE = {}

@app.before_request
def redirect_to_new_site():
    return redirect('https://trainseat.onrender.com/sunset', code=302)

def is_android_device():
    # user_agent = request.headers.get('User-Agent', '').lower()
    
    # if any(ios_pattern in user_agent for ios_pattern in ['iphone', 'ipad', 'ipod', 'ios']):
    #     return False
    
    # if 'android' in user_agent:
    #     logger.info(f"Android detected via User-Agent: {request.headers.get('User-Agent', '')}")
    #     return True
    
    # if ('mobile' in user_agent or 'tablet' in user_agent) and 'safari' not in user_agent:
    #     logger.info(f"Android detected via User-Agent (mobile/tablet): {request.headers.get('User-Agent', '')}")
    #     return True
    
    # ua_platform = request.headers.get('Sec-CH-UA-Platform', '').lower()
    # ua_mobile = request.headers.get('Sec-CH-UA-Mobile', '').lower()
    
    # if 'android' in ua_platform:
    #     logger.info(f"Android detected via Client Hints - Platform: {ua_platform}, Mobile: {ua_mobile}")
    #     return True
    
    # if ua_mobile == '?1' and 'ios' not in ua_platform and 'safari' not in user_agent:
    #     logger.info(f"Android detected via Client Hints - Mobile: {ua_mobile}")
    #     return True
    
    # mobile_headers = [
    #     'X-Requested-With',
    #     'X-WAP-Profile',
    # ]
    
    # for header in mobile_headers:
    #     header_value = request.headers.get(header, '').lower()
    #     if 'android' in header_value or 'mobile' in header_value:
    #         logger.info(f"Android detected via {header} header: {header_value}")
    #         return True
    
    # accept_header = request.headers.get('Accept', '').lower()
    # if 'wap' in accept_header or 'mobile' in accept_header:
    #     logger.info(f"Android detected via Accept header: {accept_header}")
    #     return True
    
    # client_detection = request.headers.get('X-Client-Android-Detection', '')
    # if client_detection == 'true':
    #     touch_points = request.headers.get('X-Client-Touch-Points', '0')
    #     screen_size = request.headers.get('X-Client-Screen-Size', 'unknown')
    #     pixel_ratio = request.headers.get('X-Client-Pixel-Ratio', '1')
    #     logger.info(f"Android detected via client-side JS - Touch: {touch_points}, Screen: {screen_size}, DPI: {pixel_ratio}")
    #     return True
    
    # if 'firefox' in user_agent:
    #     session_android_detected = session.get('confirmed_android_device', False)
    #     if session_android_detected:
    #         logger.info("Android detected via session memory (Firefox desktop mode bypass detected)")
    #         return True
    
    # if 'chrome' in user_agent and 'linux' in user_agent:
    #     session_android_detected = session.get('confirmed_android_device', False)
    #     if session_android_detected:
    #         logger.info("Android detected via session memory (desktop mode bypass detected)")
    #         return True
    
    return False

def get_user_device_info():
    user_agent = request.headers.get('User-Agent', '')
    
    if any(mobile in user_agent.lower() for mobile in ['mobile', 'android', 'iphone', 'ipad', 'tablet']):
        device_type = 'Mobile'
    else:
        device_type = 'PC'
    
    browser = 'Unknown'
    user_agent_lower = user_agent.lower()
    
    if 'chrome' in user_agent_lower and 'edge' not in user_agent_lower and 'opr' not in user_agent_lower:
        browser = 'Chrome'
    elif 'firefox' in user_agent_lower:
        browser = 'Firefox'
    elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower:
        browser = 'Safari'
    elif 'edge' in user_agent_lower:
        browser = 'Edge'
    elif 'opera' in user_agent_lower or 'opr' in user_agent_lower:
        browser = 'Opera'
    elif 'msie' in user_agent_lower or 'trident' in user_agent_lower:
        browser = 'Internet Explorer'
    
    return device_type, browser

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

instruction_image_path = 'static/images/instruction.png'
DEFAULT_INSTRUCTION_IMAGE = ""
if os.path.exists(instruction_image_path):
    try:
        with open(instruction_image_path, 'rb') as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
            DEFAULT_INSTRUCTION_IMAGE = f"data:image/png;base64,{encoded_image}"
    except Exception:
        pass

mobile_instruction_image_path = 'static/images/mobile_instruction.png'
DEFAULT_MOBILE_INSTRUCTION_IMAGE = ""
if os.path.exists(mobile_instruction_image_path):
    try:
        with open(mobile_instruction_image_path, 'rb') as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
            DEFAULT_MOBILE_INSTRUCTION_IMAGE = f"data:image/png;base64,{encoded_image}"
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

def block_android_from_route():
    blocked_routes = ['/', '/matrix', '/queue_wait', '/show_results', '/matrix_result', '/search_trains']
    
    if request.endpoint and request.path in blocked_routes:
        if is_android_device():
            admin_bypass = session.get('isAdmin', False)
            if not admin_bypass:
                return True
    return False

@app.before_request
def android_route_blocker():
    
    allowed_paths = ['/android', '/ads.txt', '/queue_status', '/cancel_request', 
                     '/cancel_request_beacon', '/queue_heartbeat', '/queue_cleanup', '/queue_stats',
                     '/test-android-detection', '/clear-android-session', '/admin']
    
    path_allowed = any(request.path.startswith(path) for path in allowed_paths)
    
    if not path_allowed and block_android_from_route():
        redirect_attempted = session.get('android_redirect_attempted', False)
        if not redirect_attempted:
            session['android_redirect_attempted'] = True
            return redirect(url_for('android'))
        else:
            logger.warning(f"Android device accessing {request.path} after redirect attempt - allowing to prevent infinite loop")
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

@app.route('/ads.txt')
def ads_txt():
    try:
        with open('ads.txt', 'r') as f:
            content = f.read()
        return app.response_class(
            response=content,
            mimetype='text/plain'
        )
    except FileNotFoundError:
        abort(404)

@app.route('/android')
def android():
    maintenance_response = check_maintenance()
    if maintenance_response:
        return maintenance_response

    if not is_android_device():
        return redirect(url_for('home'))
    
    admin_bypass = session.get('isAdmin', False)
    if admin_bypass:
        return redirect(url_for('home'))
    
    session['confirmed_android_device'] = True
    session.pop('android_redirect_attempted', None)
    
    app_version = CONFIG.get("version", "1.0.0")
    config = CONFIG.copy()
    
    android_message = ("Sorry, this service is currently not available for Android devices. "
                      "Please use a desktop or laptop computer to access our train seat matrix service. "
                      "We apologize for any inconvenience.")
    
    return render_template(
        'android.html',
        message=android_message,
        app_version=app_version,
        CONFIG=config,
        styles_css=STYLES_CSS_CONTENT,
        script_js=SCRIPT_JS_CONTENT
    )

@app.route('/test-android-detection')
def test_android_detection():
    android_detected = is_android_device()
    user_agent = request.headers.get('User-Agent', '')
    
    detection_info = {
        'android_detected': android_detected,
        'user_agent': user_agent,
        'headers': dict(request.headers),
        'would_be_blocked': block_android_from_route() if request.path in ['/', '/matrix'] else False,
        'blocking_always_enabled': True
    }
    
    return jsonify(detection_info)

@app.route('/clear-android-session')
def clear_android_session():
    session.pop('android_redirect_attempted', None)
    session.pop('confirmed_android_device', None)
    
    return jsonify({
        'message': 'Android session flags cleared',
        'cleared_flags': ['android_redirect_attempted', 'confirmed_android_device']
    })

@app.route('/admin')
def admin():
    maintenance_response = check_maintenance()
    if maintenance_response:
        return maintenance_response

    if not is_android_device():
        return redirect(url_for('home'))
    
    app_version = CONFIG.get("version", "1.0.0")
    config = CONFIG.copy()
    
    return render_template(
        'admin.html',
        app_version=app_version,
        CONFIG=config,
        styles_css=STYLES_CSS_CONTENT,
        script_js=SCRIPT_JS_CONTENT
    )

@app.route('/admin/verify', methods=['POST'])
def admin_verify():
    if not is_android_device():
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    admin_code = data.get('code', '').strip()
    
    valid_admin_code = os.environ.get('ADMIN_ACCESS_CODE')
    
    if valid_admin_code and admin_code == valid_admin_code:
        session.permanent = True
        session['isAdmin'] = True
        logger.info("Admin access granted successfully")
        return jsonify({'success': True, 'message': 'Admin access granted'})
    elif not valid_admin_code:
        logger.warning("Admin access verification failed - Admin code not configured")
        return jsonify({'error': 'Admin access is not configured'}), 400
    else:
        logger.warning("Admin access verification failed - Invalid admin code")
        return jsonify({'error': 'Invalid admin code'}), 401

@app.route('/admin/remove', methods=['POST'])
def admin_remove():
    if not is_android_device():
        return jsonify({'error': 'Access denied'}), 403
    
    session.pop('isAdmin', None)
    return jsonify({'success': True, 'message': 'Admin access removed'})

@app.route('/admin/status')
def admin_status():
    if not is_android_device():
        return jsonify({'error': 'Access denied'}), 403
    
    admin_active = session.get('isAdmin', False)
    admin_configured = bool(os.environ.get('ADMIN_ACCESS_CODE'))
    
    return jsonify({
        'admin_active': admin_active,
        'admin_configured': admin_configured
    })

@app.route('/admin/sync', methods=['GET', 'POST'])
def admin_sync():
    if request.method == 'GET':
        abort(404)
    
    if not is_android_device():
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    client_admin_active = data.get('admin_active', False)
    
    server_admin_active = session.get('isAdmin', False)
    
    if client_admin_active and not server_admin_active:
        logger.info("Admin sync rejected - server session expired, client localStorage should be cleared")
        return jsonify({'success': False, 'synced': False, 'session_expired': True})
    elif client_admin_active and server_admin_active:
        session.permanent = True
        session['isAdmin'] = True
        return jsonify({'success': True, 'synced': True})
    else:
        session.pop('isAdmin', None)
        return jsonify({'success': True, 'synced': True})

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
        instruction_image=DEFAULT_INSTRUCTION_IMAGE,
        mobile_instruction_image=DEFAULT_MOBILE_INSTRUCTION_IMAGE,
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
    
    device_type, browser = get_user_device_info()
    logger.info(f"Train Matrix Request - Train: '{train_model_full}', Date: '{journey_date_str}' | Device: {device_type}, Browser: {browser}")

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
                    'form_values': form_values,
                    'auth_token': request.form.get('auth_token', ''),
                    'device_key': request.form.get('device_key', '')
                }
            )
            
            session['queue_request_id'] = request_id
            return redirect(url_for('queue_wait'))
        else:
            auth_token = request.form.get('auth_token', '')
            device_key = request.form.get('device_key', '')
            result = process_matrix_request(train_model, journey_date_str, api_date_format, form_values, auth_token, device_key)
            
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

def process_matrix_request(train_model, journey_date_str, api_date_format, form_values, auth_token, device_key):
    try:
        if not auth_token or not device_key:
            return {"error": "AUTH_CREDENTIALS_REQUIRED"}
        
        result = compute_matrix(train_model, journey_date_str, api_date_format, auth_token, device_key)
        if not result or 'stations' not in result:
            return {"error": "No data received. Please try a different train or date."}
        
        return {"success": True, "result": result, "form_values": form_values}
    except Exception as e:
        error_msg = str(e)
        if error_msg in ["AUTH_TOKEN_EXPIRED", "AUTH_DEVICE_KEY_EXPIRED"]:
            return {"error": error_msg}
        return {"error": error_msg}

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
        auth_token = data.get('auth_token', '').strip()
        device_key = data.get('device_key', '').strip()
        
        device_type, browser = get_user_device_info()
        logger.info(f"Train Search Request - From: '{origin}', To: '{destination}' | Device: {device_type}, Browser: {browser}")
        
        if not origin or not destination:
            return jsonify({"error": "Both origin and destination are required"}), 400
        
        if not auth_token or not device_key:
            return jsonify({"error": "AUTH_CREDENTIALS_REQUIRED"}), 401
    
        
        today = datetime.now()
        date1 = today + timedelta(days=8)
        date2 = today + timedelta(days=9)
        
        date1_str = date1.strftime('%d-%b-%Y')
        date2_str = date2.strftime('%d-%b-%Y')
        
        trains_day1 = fetch_trains_for_date(origin, destination, date1_str, auth_token, device_key)
        trains_day2 = fetch_trains_for_date(origin, destination, date2_str, auth_token, device_key)
        
        common_trains = get_common_trains(trains_day1, trains_day2)
        
        return jsonify({
            "success": True,
            "trains": common_trains,
            "dates": [date1_str, date2_str]
        })
        
    except Exception as e:
        error_msg = str(e)
        if error_msg in ["AUTH_TOKEN_EXPIRED", "AUTH_DEVICE_KEY_EXPIRED"]:
            return jsonify({"error": error_msg}), 401
        return jsonify({"error": error_msg}), 500

def fetch_trains_for_date(origin, destination, date_str, auth_token, device_key):
    url = "https://railspaapi.shohoz.com/v1.0/web/bookings/search-trips-v2"
    params = {
        'from_city': origin,
        'to_city': destination,
        'date_of_journey': date_str,
        'seat_class': 'S_CHAIR'
    }
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "x-device-key": device_key
    }
    
    max_retries = 2
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 429:
                try:
                    error_data = response.json()
                    error_messages = error_data.get("error", {}).get("messages", [])
                    if isinstance(error_messages, list) and error_messages:
                        raise Exception(error_messages[0])
                    raise Exception("Too many requests. Please slow down.")
                except ValueError:
                    raise Exception("Too many requests. Please slow down.")
            
            if response.status_code == 401:
                try:
                    error_data = response.json()
                    error_messages = error_data.get("error", {}).get("messages", [])
                    if isinstance(error_messages, list):
                        for msg in error_messages:
                            if "You are not authorized for this request" in msg or "Please login first" in msg:
                                raise Exception("AUTH_DEVICE_KEY_EXPIRED")
                            elif "Invalid User Access Token!" in msg:
                                raise Exception("AUTH_TOKEN_EXPIRED")
                    raise Exception("AUTH_TOKEN_EXPIRED")
                except ValueError:
                    raise Exception("AUTH_TOKEN_EXPIRED")
            
            if response.status_code == 403:
                raise Exception("Currently we are experiencing high traffic. Please try again after some time.")
                
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
            status_code = e.response.status_code if e.response is not None else None
            
            if status_code == 429:
                try:
                    error_data = e.response.json()
                    error_messages = error_data.get("error", {}).get("messages", [])
                    if isinstance(error_messages, list) and error_messages:
                        raise Exception(error_messages[0])
                    raise Exception("Too many requests. Please slow down.")
                except ValueError:
                    raise Exception("Too many requests. Please slow down.")
            
            if status_code == 401:
                try:
                    error_data = e.response.json()
                    error_messages = error_data.get("error", {}).get("messages", [])
                    if isinstance(error_messages, list):
                        for msg in error_messages:
                            if "You are not authorized for this request" in msg or "Please login first" in msg:
                                raise Exception("AUTH_DEVICE_KEY_EXPIRED")
                            elif "Invalid User Access Token!" in msg:
                                raise Exception("AUTH_TOKEN_EXPIRED")
                    raise Exception("AUTH_TOKEN_EXPIRED")
                except ValueError:
                    raise Exception("AUTH_TOKEN_EXPIRED")
                    
            if hasattr(e, 'response') and e.response and e.response.status_code == 403:
                raise Exception("Currently we are experiencing high traffic. Please try again after some time.")
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
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=False)
else:
    if not app.debug:
        app.logger.setLevel(logging.INFO)
        app.logger.addHandler(logging.StreamHandler(sys.stdout))