from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
import json, pytz, os, re, uuid
from matrixCalculator import compute_matrix

app = Flask(__name__)
app.secret_key = "super_secret_key"

RESULT_CACHE = {}

with open('trains_en.json', 'r') as f:
    trains_data = json.load(f)
    trains = trains_data['trains']

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

    app_version = "1.0.0"
    config = {
        "version": app_version,
        "force_banner": 0
    }
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
        banner_image=banner_image,
        min_date=min_date.strftime("%Y-%m-%d"),
        max_date=max_date.strftime("%Y-%m-%d"),
        bst_midnight_utc=bst_midnight_utc,
        show_disclaimer=True,
        form_values=form_values,
        trains=trains
    )

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

        result = compute_matrix(train_model, journey_date_str, api_date_format)
        if not result or 'stations' not in result:
            session['error'] = "No data received. Please try a different train or date."
            return redirect(url_for('home'))
        session['form_values'] = {
            'train_model': train_model_full,
            'date': journey_date_str
        }
        session['form_submitted'] = True
        result_id = str(uuid.uuid4())
        RESULT_CACHE[result_id] = result
        session['result_id'] = result_id
        return redirect(url_for('matrix_result'))
    except Exception as e:
        session['error'] = f"{str(e)}"
        return redirect(url_for('home'))

@app.route('/matrix_result')
def matrix_result():
    result_id = session.pop('result_id', None)
    result = RESULT_CACHE.pop(result_id, None) if result_id else None
    form_values = session.get('form_values', None)

    if not result:
        return redirect(url_for('home'))

    return render_template('matrix.html', **result, form_values=form_values)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))