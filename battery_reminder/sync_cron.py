#!/usr/bin/env python3
import sys
import os

# Add the script directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_batteries import BatteryMonitor

if __name__ == "__main__":
    monitor = BatteryMonitor()
    monitor.check_and_update()
    print("Sync completed successfully")

