from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime, timedelta
import json, pytz, os, re, uuid
from matrixCalculator import compute_matrix
from request_queue import request_queue, RequestQueue

app = Flask(__name__)
app.secret_key = "super_secret_key"

RESULT_CACHE = {}

with open('trains_en.json', 'r') as f:
    trains_data = json.load(f)
    trains = trains_data['trains']

# Configure the request queue based on settings in config.json
def configure_request_queue():
    with open('config.json', 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
    max_concurrent = config.get("queue_max_concurrent", 1)
    cooldown_period = config.get("queue_cooldown_period", 3)
    
    # Create a new global request queue with these settings
    global request_queue
    request_queue = RequestQueue(max_concurrent=max_concurrent, cooldown_period=cooldown_period)
    
    print(f"[INFO] Configured request queue with max_concurrent={max_concurrent}, cooldown_period={cooldown_period}")

# Initialize request queue with config settings
configure_request_queue()

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
    error = session.pop('error', None)

    with open('config.json', 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)

    banner_image = config.get("image_link", "")

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
        app_version=config.get("version", "1.0.0"),
        CONFIG=config,
        banner_image=banner_image,
        min_date=min_date.strftime("%Y-%m-%d"),
        max_date=max_date.strftime("%Y-%m-%d"),
        bst_midnight_utc=bst_midnight_utc,
        show_disclaimer=True,
        form_values=form_values,
        trains=trains
    )

def process_matrix_request(train_model, journey_date_str, api_date_format):
    """Process the matrix request in the queue"""
    try:
        result = compute_matrix(train_model, journey_date_str, api_date_format)
        return {"success": True, "result": result}
    except Exception as e:
        return {"error": str(e)}

@app.route('/matrix', methods=['POST'])
def matrix():
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
        session['form_values'] = {
            'train_model': train_model_full,
            'date': journey_date_str
        }
        session['form_submitted'] = True

        with open('config.json', 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)

        # Check if queueing is enabled in config
        if config.get("queue_enabled", True):
            # Add the request to the queue system
            request_id = request_queue.add_request(
                process_matrix_request,
                {
                    'train_model': train_model,
                    'journey_date_str': journey_date_str,
                    'api_date_format': api_date_format
                }
            )
            
            # Store the request ID in the session
            session['queue_request_id'] = request_id
            
            # Redirect to the queue waiting page
            return redirect(url_for('queue_wait'))
        else:
            # Process request immediately (legacy behavior)
            result = compute_matrix(train_model, journey_date_str, api_date_format)
            if not result or 'stations' not in result:
                session['error'] = "No data received. Please try a different train or date."
                return redirect(url_for('home'))
            
            result_id = str(uuid.uuid4())
            RESULT_CACHE[result_id] = result
            session['result_id'] = result_id
            return redirect(url_for('matrix_result', request_id=result_id))

    except Exception as e:
        session['error'] = f"{str(e)}"
        return redirect(url_for('home'))

@app.route('/queue_wait')
def queue_wait():
    """Show waiting page for queued requests"""
    with open('config.json', 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
    
    request_id = session.get('queue_request_id')
    if not request_id:
        session['error'] = "Your request session has expired. Please search again."
        return redirect(url_for('home'))
    
    # Get the current status of the request
    status = request_queue.get_request_status(request_id)
    if not status:
        session['error'] = "Your request could not be found. Please search again."
        return redirect(url_for('home'))
    
    form_values = session.get('form_values', {})
    
    return render_template(
        'queue.html',
        request_id=request_id,
        status=status,
        form_values=form_values,
        CONFIG=config
    )

@app.route('/queue_status/<request_id>')
def queue_status(request_id):
    """API endpoint to get the current status of a queued request"""
    status = request_queue.get_request_status(request_id)
    if not status:
        return jsonify({"error": "Request not found"}), 404
    
    # Check if the request failed and include error message
    if status["status"] == "failed":
        result = request_queue.get_request_result(request_id)
        if result and "error" in result:
            status["errorMessage"] = result["error"]
    
    return jsonify(status)

@app.route('/matrix_result/<request_id>')
def matrix_result(request_id):
    # Handle queued requests
    queue_result = request_queue.get_request_result(request_id)
    
    # Fallback to legacy result_id in cache if queue result not found
    if not queue_result and request_id in RESULT_CACHE:
        result = RESULT_CACHE.pop(request_id, None)
        form_values = session.get('form_values', None)
        if not result:
            session['error'] = "Your request has expired or could not be found. Please search again."
            return redirect(url_for('home'))
        return render_template('matrix.html', **result, form_values=form_values)
    
    # Handle queue-based results
    if not queue_result:
        session['error'] = "Your request has expired or could not be found. Please search again."
        return redirect(url_for('home'))
    
    if "error" in queue_result:
        session['error'] = queue_result["error"]
        return redirect(url_for('home'))
    
    if not queue_result.get("success"):
        session['error'] = "An error occurred while processing your request. Please try again."
        return redirect(url_for('home'))
    
    # Extract the actual result data
    result = queue_result.get("result", {})
    form_values = session.get('form_values', None)
    if not result or 'stations' not in result:
        session['error'] = "No data received. Please try a different train or date."
        return redirect(url_for('home'))

    return render_template('matrix.html', **result, form_values=form_values)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))