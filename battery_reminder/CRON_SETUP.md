# Weekly Cron Job Setup

This guide explains how to set up the weekly automatic sync for the Battery Reminder app.

## Setup Instructions

1. **Find your Python path:**
   ```bash
   which python3
   ```
   Or if you're using a virtual environment:
   ```bash
   which python
   ```

2. **Edit your crontab:**
   ```bash
   crontab -e
   ```

3. **Add the following line** (runs every Sunday at midnight):
   ```
   0 0 * * 0 cd /Users/clarenceyeung/sram/battery_reminder && /usr/bin/python3 sync_cron.py >> sync.log 2>&1
   ```
   
   **Or** if you want to run it at a different time, use:
   ```
   MINUTE HOUR * * DAY cd /Users/clarenceyeung/sram/battery_reminder && /usr/bin/python3 sync_cron.py >> sync.log 2>&1
   ```
   
   Where:
   - `MINUTE` = minute (0-59)
   - `HOUR` = hour (0-23)
   - `DAY` = day of week (0-7, where 0 and 7 = Sunday)

4. **Save and exit** the crontab editor

5. **Verify the cron job is set:**
   ```bash
   crontab -l
   ```

6. **Test the script manually:**
   ```bash
   cd /Users/clarenceyeung/sram/battery_reminder
   python3 sync_cron.py
   ```

## Logs

The sync output will be logged to `sync.log` in the battery_reminder directory. Check it if you need to debug issues.

## Troubleshooting

- Make sure the Python path in the cron job matches your system
- Ensure the file paths are absolute or relative to the working directory
- Check `sync.log` for any error messages
- Verify your Strava tokens are still valid (they may need to be refreshed)

