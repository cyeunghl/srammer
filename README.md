# Battery Reminder

A web application that monitors battery-powered devices (like AXS or Di2) by tracking usage through Strava activities. It automatically sends email reminders when devices exceed usage thresholds or haven't been charged in a specified number of days.

## Features

- **Strava Integration**: Automatically syncs with your Strava account to track cycling activities
- **Device Management**: Track multiple battery-powered devices with custom thresholds
- **Flexible Tracking**: Monitor usage by distance (miles/km) or time (hours)
- **Bike Filtering**: Associate specific Strava bikes/gear with each device
- **Activity Type Filtering**: Filter activities by type (Ride, VirtualRide, EBikeRide, etc.)
- **Email Alerts**: Receive email notifications when:
  - Device usage exceeds the configured threshold
  - Device hasn't been charged in X days (configurable)
- **Web Interface**: User-friendly dashboard to:
  - View device status and current usage
  - Mark devices as charged
  - Configure thresholds and settings
  - View charging history
  - Browse recent Strava activities
- **Automatic Syncing**: Set up cron jobs for automatic weekly syncs
- **Docker Support**: Easy deployment with Docker

## Prerequisites

- Python 3.11 or higher
- Strava API credentials (Client ID and Client Secret)
- Email account for sending alerts (SMTP access required)
- (Optional) Docker for containerized deployment

## Installation

### 1. Clone the repository

```bash
cd /path/to/your/project
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the application

Edit `config.json` with your settings:

```json
{
  "strava_client_id": "YOUR_STRAVA_CLIENT_ID",
  "strava_client_secret": "YOUR_STRAVA_CLIENT_SECRET",
  "app_secret_key": "YOUR_RANDOM_SECRET_KEY",
  "email_settings": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your-email@gmail.com",
    "sender_password": "your-app-password",
    "recipient_email": "recipient-email@gmail.com"
  },
  "reminder_settings": {
    "days_to_remind": 30,
    "email_message_template": "Your {device_name} has exceeded its threshold.\n\nCurrent Usage: {current_usage:.2f} {unit}\nThreshold: {threshold_value} {unit}\nLast Charged: {last_charged}\n\nPlease charge it soon!"
  }
}
```

**Important Notes:**
- For Gmail, you'll need to use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password
- Generate a random `app_secret_key` for Flask session security
- The `email_message_template` supports placeholders: `{device_name}`, `{current_usage}`, `{unit}`, `{threshold_value}`, `{last_charged}`

### 4. Get Strava API Credentials

1. Go to [Strava Developers](https://www.strava.com/settings/api)
2. Create a new application
3. Set the Authorization Callback Domain to `localhost:5001`
4. Copy your Client ID and Client Secret to `config.json`

## Usage

### Running the Web Application

Start the Flask web server:

```bash
python app.py
```

The application will be available at `http://localhost:5001`

**Default Port**: The app runs on port 5001 by default. You can change this by setting the `PORT` environment variable.

### First-Time Setup

1. **Authenticate with Strava**:
   - Navigate to `http://localhost:5001`
   - Click "Login with Strava"
   - Authorize the application

2. **Add Devices**:
   - Go to Settings
   - Configure your battery-powered devices
   - Set thresholds (e.g., 50 miles, 10 hours, etc.)
   - Select which Strava bikes/gear to track for each device
   - Choose activity types to include

3. **Mark Initial Charge**:
   - On the main dashboard, mark each device as charged
   - This sets the baseline for tracking

4. **Sync Activities**:
   - Click "Sync" to fetch activities from Strava
   - The app will calculate current usage based on activities since last charge

### Manual Sync

Run the sync script manually:

```bash
python check_batteries.py
```

Or use the sync script:

```bash
python sync_cron.py
```

### Setting Up Automatic Syncing

See [CRON_SETUP.md](CRON_SETUP.md) for detailed instructions on setting up weekly automatic syncs via cron.

**Quick Setup:**

```bash
crontab -e
```

Add this line (runs every Sunday at midnight):

```
0 0 * * 0 cd /path/to/battery_reminder && /usr/bin/python3 sync_cron.py >> sync.log 2>&1
```

## Docker Deployment

### Build the Docker image

```bash
docker build -t battery-reminder .
```

### Run the container

```bash
docker run -d \
  -p 5001:5001 \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/state.json:/app/state.json \
  --name battery-reminder \
  battery-reminder
```

**Note**: Mount `config.json` and `state.json` as volumes to persist configuration and state data.

## Project Structure

```
battery_reminder/
├── app.py                 # Flask web application
├── check_batteries.py     # Core monitoring logic and Strava client
├── sync_cron.py          # Cron script for automatic syncing
├── config.json           # Configuration file (create this)
├── state.json            # Application state (auto-generated)
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker configuration
├── CRON_SETUP.md        # Cron setup instructions
├── sync.log             # Cron sync logs
└── templates/           # HTML templates
    ├── base.html
    ├── index.html
    ├── settings.html
    ├── history.html
    └── activities.html
```

## Configuration Details

### Device Configuration

Each device in `state.json` has the following structure:

```json
{
  "device_id": {
    "name": "Device Name",
    "threshold_value": 50.0,
    "threshold_unit": "miles",
    "last_charged": "2024-01-01T00:00:00",
    "current_usage": 0.0,
    "gear_ids": [123456, 789012],
    "activity_types": ["Ride", "VirtualRide", "EBikeRide"]
  }
}
```

- `threshold_unit`: Can be `"miles"`, `"km"`, or `"hours"`
- `gear_ids`: List of Strava bike/gear IDs to track (empty = track all bikes)
- `activity_types`: List of activity types to include (default: cycling activities)

### Reminder Settings

- `days_to_remind`: Number of days since last charge before sending a reminder
- `email_message_template`: Customizable email message template

## API Endpoints

- `GET /` - Main dashboard
- `GET /login` - Strava OAuth login
- `GET /callback` - Strava OAuth callback
- `POST /sync` - Manually sync activities
- `POST /mark_charged/<device_id>` - Mark device as charged
- `POST /update_thresholds` - Update device thresholds
- `GET /settings` - Settings page
- `POST /update_settings` - Update application settings
- `POST /test_email` - Send test email
- `GET /history` - View charging history
- `GET /activities` - View recent Strava activities
- `GET /api/bikes` - API endpoint to fetch Strava bikes

## Troubleshooting

### Strava Authentication Issues

- Ensure your Strava app's callback URL is set to `http://localhost:5001/callback`
- Check that your Client ID and Secret are correct in `config.json`
- Tokens expire after 6 hours; the app automatically refreshes them

### Email Not Sending

- Verify SMTP settings in `config.json`
- For Gmail, ensure you're using an App Password, not your regular password
- Test email functionality from the Settings page
- Check that your email provider allows SMTP access

### Sync Issues

- Check `sync.log` for error messages
- Verify Strava tokens are valid (try re-authenticating)
- Ensure devices have a `last_charged` date set
- Check that activities exist in Strava for the time period since last charge

### Port Already in Use

Change the port by setting the `PORT` environment variable:

```bash
PORT=8080 python app.py
```

## License

This project is provided as-is for personal use.

## Contributing

Feel free to submit issues or pull requests for improvements.

