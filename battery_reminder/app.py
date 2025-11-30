from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from check_batteries import StravaClient, BatteryMonitor
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# Load secret key from config
with open('config.json', 'r') as f:
    config = json.load(f)
    app.secret_key = config.get('app_secret_key', 'fallback_secret')

strava_client = StravaClient()
monitor = BatteryMonitor()

@app.route('/')
def index():
    strava_client.load_state() # Refresh state
    devices = strava_client.state.get('devices', {})
    tokens = strava_client.state.get('strava_tokens', {})
    authenticated = bool(tokens.get('access_token'))
    
    return render_template('index.html', devices=devices, authenticated=authenticated, request=request)

@app.route('/login')
def login():
    auth_url = strava_client.get_auth_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if code:
        if strava_client.exchange_token(code):
            return redirect(url_for('index'))
    return "Error authenticating with Strava"

@app.route('/mark_charged/<device_id>', methods=['POST'])
def mark_charged(device_id):
    strava_client.load_state()
    if device_id in strava_client.state['devices']:
        device = strava_client.state['devices'][device_id]
        previous_charged = device.get('last_charged')
        current_usage = device.get('current_usage', 0.0)
        
        # Record history entry
        if 'history' not in strava_client.state:
            strava_client.state['history'] = {}
        if device_id not in strava_client.state['history']:
            strava_client.state['history'][device_id] = []
        
        if previous_charged:
            try:
                prev_dt = datetime.fromisoformat(previous_charged)
                days_between = (datetime.now() - prev_dt).days
                strava_client.state['history'][device_id].append({
                    'charged_at': datetime.now().isoformat(),
                    'previous_charged': previous_charged,
                    'days_between': days_between,
                    'usage_at_charge': current_usage,
                    'unit': device.get('threshold_unit', 'miles')
                })
            except (ValueError, TypeError):
                strava_client.state['history'][device_id].append({
                    'charged_at': datetime.now().isoformat(),
                    'previous_charged': previous_charged,
                    'days_between': 0,
                    'usage_at_charge': current_usage,
                    'unit': device.get('threshold_unit', 'miles')
                })
        else:
            strava_client.state['history'][device_id].append({
                'charged_at': datetime.now().isoformat(),
                'previous_charged': None,
                'days_between': 0,
                'usage_at_charge': current_usage,
                'unit': device.get('threshold_unit', 'miles')
            })
        
        # Update device
        device['last_charged'] = datetime.now().isoformat()
        device['current_usage'] = 0.0
        strava_client.save_state()
    return redirect(url_for('index'))

@app.route('/update_thresholds', methods=['POST'])
def update_thresholds():
    strava_client.load_state()
    for device_id in strava_client.state['devices']:
        threshold_val = request.form.get(f'{device_id}_threshold')
        threshold_unit = request.form.get(f'{device_id}_unit')
        
        if threshold_val:
            strava_client.state['devices'][device_id]['threshold_value'] = float(threshold_val)
        if threshold_unit:
            strava_client.state['devices'][device_id]['threshold_unit'] = threshold_unit
            
    strava_client.save_state()
    return redirect(url_for('index'))

@app.route('/sync', methods=['POST'])
def sync():
    try:
        # Reload state before syncing to get latest data
        strava_client.load_state()
        monitor.strava.load_state()
        monitor.check_and_update()
        flash('Sync completed successfully!', 'success')
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        flash(f'Error during sync: {error_msg}', 'error')
        print(f"Sync error: {e}")
    return redirect(url_for('index'))

@app.route('/settings')
def settings():
    strava_client.load_state()
    tokens = strava_client.state.get('strava_tokens', {})
    authenticated = bool(tokens.get('access_token'))
    
    # Load config for settings
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    reminder_settings = config.get('reminder_settings', {})
    days_to_remind = reminder_settings.get('days_to_remind', 30)
    email_message = reminder_settings.get('email_message_template', 
        'Your {device_name} has exceeded its threshold.\n\nCurrent Usage: {current_usage:.2f} {unit}\nThreshold: {threshold_value} {unit}\nLast Charged: {last_charged}\n\nPlease charge it soon!')
    
    # Fetch bikes if authenticated
    bikes = []
    devices = strava_client.state.get('devices', {})
    if authenticated:
        try:
            bikes = strava_client.fetch_bikes()
        except Exception as e:
            flash(f"Error fetching bikes: {str(e)}", 'error')
    
    return render_template('settings.html', 
                         authenticated=authenticated,
                         days_to_remind=days_to_remind,
                         email_message=email_message,
                         devices=devices,
                         bikes=bikes,
                         request=request)

@app.route('/update_settings', methods=['POST'])
def update_settings():
    days_to_remind = request.form.get('days_to_remind')
    email_message = request.form.get('email_message')
    
    # Load current config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Update reminder settings
    if 'reminder_settings' not in config:
        config['reminder_settings'] = {}
    
    if days_to_remind:
        config['reminder_settings']['days_to_remind'] = int(days_to_remind)
    if email_message:
        config['reminder_settings']['email_message_template'] = email_message
    
    # Save config
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    # Reload config in StravaClient and monitor
    strava_client.load_config()
    monitor.strava.load_config()
    
    flash('Settings updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/test_email', methods=['POST'])
def test_email():
    success, message = monitor.send_test_email()
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('settings'))

@app.route('/api/bikes')
def get_bikes():
    strava_client.load_state()
    tokens = strava_client.state.get('strava_tokens', {})
    authenticated = bool(tokens.get('access_token'))
    
    if not authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    bikes = strava_client.fetch_bikes()
    return jsonify(bikes)

@app.route('/update_device_bikes', methods=['POST'])
def update_device_bikes():
    strava_client.load_state()
    
    for device_id in strava_client.state.get('devices', {}):
        # Get selected bikes for this device
        gear_ids = request.form.getlist(f'{device_id}_bikes')
        activity_types = request.form.getlist(f'{device_id}_activity_types')
        
        if gear_ids:
            # Convert to integers if possible, otherwise keep as strings
            try:
                strava_client.state['devices'][device_id]['gear_ids'] = [int(gid) if gid.isdigit() else gid for gid in gear_ids if gid]
            except:
                strava_client.state['devices'][device_id]['gear_ids'] = [gid for gid in gear_ids if gid]
        else:
            # If no bikes selected, remove the gear_ids key (track all bikes)
            if 'gear_ids' in strava_client.state['devices'][device_id]:
                del strava_client.state['devices'][device_id]['gear_ids']
        
        if activity_types:
            strava_client.state['devices'][device_id]['activity_types'] = activity_types
        else:
            # Default to cycling activities if none selected
            strava_client.state['devices'][device_id]['activity_types'] = ['Ride', 'VirtualRide', 'EBikeRide']
    
    strava_client.save_state()
    flash('Device bike mappings updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/history')
def history():
    strava_client.load_state()
    tokens = strava_client.state.get('strava_tokens', {})
    authenticated = bool(tokens.get('access_token'))
    devices = strava_client.state.get('devices', {})
    history_data = strava_client.state.get('history', {})
    
    return render_template('history.html', 
                         authenticated=authenticated,
                         devices=devices,
                         history=history_data,
                         request=request)

@app.route('/activities')
def activities():
    strava_client.load_state()
    tokens = strava_client.state.get('strava_tokens', {})
    authenticated = bool(tokens.get('access_token'))
    
    if not authenticated:
        return redirect(url_for('login'))
    
    # Fetch recent activities (last 30 days)
    activities = []
    try:
        thirty_days_ago = datetime.now() - timedelta(days=30)
        activities = strava_client.fetch_activities_since(thirty_days_ago.isoformat())
    except Exception as e:
        flash(f"Error fetching activities: {str(e)}", 'error')
    
    devices = strava_client.state.get('devices', {})
    
    # Map activities to devices (simplified - you can enhance this)
    # For now, we'll show all activities and let user see which devices they affect
    return render_template('activities.html',
                         authenticated=authenticated,
                         activities=activities,
                         devices=devices,
                         request=request)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
