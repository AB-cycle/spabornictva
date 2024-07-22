from flask import Flask, request, jsonify, render_template
import gpxpy
from geopy.distance import great_circle
import json
import os
from datetime import datetime

app = Flask(__name__)

# Path to the JSON file where data will be stored
DATA_FILE = 'data.json'

# Helper function to load data from the JSON file
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {'users': {}}

# Helper function to save data to the JSON file
def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    name = request.form.get('name')
    
    if not name:
        return 'Name is required'
    
    if file.filename == '':
        return 'No selected file'
    
    if file and allowed_file(file.filename):
        gpx = gpxpy.parse(file.stream)
        
        if not gpx.tracks:
            return 'This is a route, not a track. Please upload a track.'

        if not any(point.time for track in gpx.tracks for segment in track.segments for point in segment.points):
            return 'This track lacks time information. Please upload a track with time data.'

        result = process_gpx(gpx)
        
        data = load_data()
        
        if name not in data['users']:
            data['users'][name] = {
                'total_distance_km': 0.0,
                'tracks': []
            }
        
        user = data['users'][name]
        user['total_distance_km'] += result['total_distance_km']
        user['tracks'].append({
            'filename': file.filename,
            'distance_km': result['total_distance_km'],
            'duration': result['duration'],
            'upload_time': datetime.now().strftime('%d %B %Y')  # Updated format
        })
        
        save_data(data)
        
        return render_template('results.html', 
                               name=name,
                               total_distance=user['total_distance_km'],
                               tracks=user['tracks'])
    return 'Invalid file format'

@app.route('/statistics')
def statistics():
    data = load_data()
    users = data['users']
    total_distance_all_users = sum(user['total_distance_km'] for user in users.values())
    target_distance = 10000  # Целевая дистанция в км
    total_percentage = min((total_distance_all_users / target_distance) * 100, 100)  # Процент выполнения цели
    return render_template('statistics.html', 
                           users=users,
                           total_distance_all_users=round(total_distance_all_users, 2),
                           total_percentage=round(total_percentage, 2))

@app.route('/user/<username>')
def user_tracks(username):
    data = load_data()
    user = data['users'].get(username)

    if not user:
        return 'User not found', 404

    return render_template('user_tracks.html', 
                           username=username,
                           tracks=user['tracks'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'gpx'}

def process_gpx(gpx):
    data = []
    total_distance = 0.0
    previous_point = None
    start_time = None
    end_time = None

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                point_data = {
                    'latitude': point.latitude,
                    'longitude': point.longitude,
                    'elevation': point.elevation,
                    'time': point.time.isoformat() if point.time else None
                }
                data.append(point_data)

                if previous_point:
                    distance = great_circle(
                        (previous_point['latitude'], previous_point['longitude']),
                        (point.latitude, point.longitude)
                    ).kilometers
                    total_distance += distance

                previous_point = {
                    'latitude': point.latitude,
                    'longitude': point.longitude
                }

                if not start_time:
                    start_time = point.time
                end_time = point.time

    duration = None
    if start_time and end_time:
        duration = format_duration(end_time - start_time)

    result = {
        'data': data,
        'total_distance_km': round(total_distance, 2),
        'duration': duration,
        'start_time': start_time.strftime('%d %B %Y') if start_time else None
    }

    return result

def format_duration(delta):
    """Format timedelta into hours:minutes:seconds."""
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"

if __name__ == '__main__':
    app.run(debug=True)
















