import json
import time
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

CONFIG_FILE = 'config.json'
STATE_FILE = 'state.json'

class StravaClient:
    def __init__(self):
        self.load_config()
        self.load_state()

    def load_config(self):
        with open(CONFIG_FILE, 'r') as f:
            self.config = json.load(f)

    def load_state(self):
        try:
            with open(STATE_FILE, 'r') as f:
                self.state = json.load(f)
        except FileNotFoundError:
            self.state = {"strava_tokens": {}, "devices": {}}

    def save_state(self):
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)

    def get_auth_url(self):
        client_id = self.config['strava_client_id']
        redirect_uri = 'http://localhost:5001/callback'
        scope = 'activity:read_all,profile:read_all'
        return f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&approval_prompt=force&scope={scope}"

    def exchange_token(self, code):
        url = "https://www.strava.com/oauth/token"
        payload = {
            'client_id': self.config['strava_client_id'],
            'client_secret': self.config['strava_client_secret'],
            'code': code,
            'grant_type': 'authorization_code'
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            tokens = response.json()
            self.state['strava_tokens'] = {
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'expires_at': tokens['expires_at']
            }
            self.save_state()
            return True
        return False

    def refresh_token_if_needed(self):
        tokens = self.state.get('strava_tokens', {})
        if not tokens.get('refresh_token'):
            return False
        
        if time.time() < tokens.get('expires_at', 0):
            return True

        url = "https://www.strava.com/oauth/token"
        payload = {
            'client_id': self.config['strava_client_id'],
            'client_secret': self.config['strava_client_secret'],
            'grant_type': 'refresh_token',
            'refresh_token': tokens['refresh_token']
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            new_tokens = response.json()
            self.state['strava_tokens']['access_token'] = new_tokens['access_token']
            self.state['strava_tokens']['refresh_token'] = new_tokens['refresh_token']
            self.state['strava_tokens']['expires_at'] = new_tokens['expires_at']
            self.save_state()
            return True
        return False

    def fetch_bikes(self):
        """Fetch user's bikes from Strava"""
        if not self.refresh_token_if_needed():
            return []
        
        access_token = self.state['strava_tokens']['access_token']
        headers = {'Authorization': f"Bearer {access_token}"}
        
        url = "https://www.strava.com/api/v3/athlete"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            athlete = response.json()
            return athlete.get('bikes', [])
        return []

    def fetch_activities_since(self, timestamp_str, activity_types=None, gear_ids=None):
        if not self.refresh_token_if_needed():
            print("Error: Could not refresh token.")
            return []
        
        access_token = self.state['strava_tokens']['access_token']
        headers = {'Authorization': f"Bearer {access_token}"}
        
        # Convert timestamp string to epoch
        try:
            dt = datetime.fromisoformat(timestamp_str)
            after_epoch = int(dt.timestamp())
        except ValueError:
            after_epoch = 0

        activities = []
        page = 1
        while True:
            url = f"https://www.strava.com/api/v3/athlete/activities?after={after_epoch}&page={page}&per_page=200"
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                break
            batch = response.json()
            if not batch:
                break
            
            # Filter activities
            for activity in batch:
                # Filter out Hike, Walk, Run
                if activity.get('type') in ['Hike', 'Walk', 'Run']:
                    continue
                
                # Filter by gear_id if specified (only if gear_ids list is not empty)
                if gear_ids and len(gear_ids) > 0:
                    activity_gear_id = activity.get('gear_id')
                    if activity_gear_id:
                        # Convert both to strings for comparison (Strava returns gear_id as string)
                        gear_id_str = str(activity_gear_id)
                        gear_ids_str = [str(gid) for gid in gear_ids]
                        if gear_id_str not in gear_ids_str:
                            continue
                    else:
                        # Activity has no gear_id, skip if we're filtering by gear
                        continue
                
                # Filter by activity types if specified
                if activity_types:
                    if activity.get('type') not in activity_types:
                        continue
                
                activities.append(activity)
            
            page += 1
        return activities

class BatteryMonitor:
    def __init__(self):
        self.strava = StravaClient()

    def check_and_update(self):
        devices = self.strava.state.get('devices', {})
        updated = False
        
        reminder_settings = self.strava.config.get('reminder_settings', {})
        days_to_remind = reminder_settings.get('days_to_remind', 30)
        
        for device_id, device in devices.items():
            last_charged = device.get('last_charged')
            if not last_charged:
                continue

            # Get device-specific filters
            gear_ids = device.get('gear_ids', [])  # List of bike gear_ids
            activity_types = device.get('activity_types', ['Ride', 'VirtualRide', 'EBikeRide'])  # Default cycling activities
            
            activities = self.strava.fetch_activities_since(
                last_charged, 
                activity_types=activity_types if activity_types else None,
                gear_ids=gear_ids if gear_ids and len(gear_ids) > 0 else None
            )
            
            total_distance_meters = sum(a.get('distance', 0) for a in activities)
            total_time_seconds = sum(a.get('moving_time', 0) for a in activities)
            
            # Update usage based on unit
            if device['threshold_unit'] == 'miles':
                device['current_usage'] = total_distance_meters * 0.000621371
            elif device['threshold_unit'] == 'km':
                device['current_usage'] = total_distance_meters / 1000.0
            elif device['threshold_unit'] == 'hours':
                device['current_usage'] = total_time_seconds / 3600.0
            
            device['last_sync_time'] = datetime.now().isoformat()
            updated = True
            
            # Check threshold or days reminder
            should_alert = False
            if device['current_usage'] >= device['threshold_value']:
                should_alert = True
            else:
                # Check days since last charged
                try:
                    last_charged_dt = datetime.fromisoformat(last_charged)
                    days_since = (datetime.now() - last_charged_dt).days
                    if days_since >= days_to_remind:
                        should_alert = True
                except (ValueError, TypeError):
                    pass
            
            if should_alert:
                self.send_alert(device)

        if updated:
            self.strava.save_state()

    def send_alert(self, device):
        email_settings = self.strava.config.get('email_settings', {})
        if not email_settings:
            print("No email settings found.")
            return

        reminder_settings = self.strava.config.get('reminder_settings', {})
        message_template = reminder_settings.get('email_message_template', 
            "Your {device_name} has exceeded its threshold.\n\nCurrent Usage: {current_usage:.2f} {unit}\nThreshold: {threshold_value} {unit}\nLast Charged: {last_charged}\n\nPlease charge it soon!")
        
        # Format the message template
        try:
            last_charged_dt = datetime.fromisoformat(device.get('last_charged', ''))
            last_charged_str = last_charged_dt.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            last_charged_str = device.get('last_charged', 'Unknown')
        
        message_body = message_template.format(
            device_name=device['name'],
            current_usage=device['current_usage'],
            unit=device['threshold_unit'],
            threshold_value=device['threshold_value'],
            last_charged=last_charged_str
        )
        
        msg = MIMEText(message_body)
        msg['Subject'] = f"Battery Alert: {device['name']}"
        msg['From'] = email_settings['sender_email']
        msg['To'] = email_settings['recipient_email']

        try:
            with smtplib.SMTP(email_settings['smtp_server'], email_settings['smtp_port']) as server:
                server.starttls()
                server.login(email_settings['sender_email'], email_settings['sender_password'])
                server.send_message(msg)
                print(f"Sent alert for {device['name']}")
        except Exception as e:
            print(f"Failed to send email: {e}")
    
    def send_test_email(self):
        """Send a test email to verify email settings"""
        email_settings = self.strava.config.get('email_settings', {})
        if not email_settings:
            return False, "No email settings found."

        msg = MIMEText("This is a test email from Battery Reminder. Your email settings are configured correctly!")
        msg['Subject'] = "Battery Reminder - Test Email"
        msg['From'] = email_settings['sender_email']
        msg['To'] = email_settings['recipient_email']

        try:
            with smtplib.SMTP(email_settings['smtp_server'], email_settings['smtp_port']) as server:
                server.starttls()
                server.login(email_settings['sender_email'], email_settings['sender_password'])
                server.send_message(msg)
                return True, "Test email sent successfully!"
        except Exception as e:
            return False, f"Failed to send test email: {str(e)}"

if __name__ == "__main__":
    monitor = BatteryMonitor()
    monitor.check_and_update()
