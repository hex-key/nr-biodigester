#!/usr/bin/env python3
import datetime
import glob
import os
import sys
import time
from collections import deque
import matplotlib.animation as animation
from matplotlib.dates import DateFormatter
import matplotlib.pyplot as plt

LED_PIN = 5 #gpio5
LED_CUTOFF = 23

import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.output(LED_PIN, GPIO.LOW)

# 1-Wire directory setup
BASE_DIR = '/sys/bus/w1/devices/'
device_folders = glob.glob(os.path.join(BASE_DIR, '28*'))

# Ensure sensors are found
if len(device_folders) < 3:
    print(f"Warning: Found {len(device_folders)} sensor(s). Expected 3.")
    if not device_folders:
        sys.exit("Error: No 1-Wire DS18B20 sensors found.")

# Limit to 3 sensors and map display names
SENSOR_CONFIG = [
    {"id": os.path.basename(device_folders[0]), "file": os.path.join(device_folders[0], 'w1_slave'), "name": "Sensor 1"},
    {"id": os.path.basename(device_folders[1]), "file": os.path.join(device_folders[1], 'w1_slave'), "name": "Sensor 2"} if len(device_folders) > 1 else None,
    {"id": os.path.basename(device_folders[2]), "file": os.path.join(device_folders[2], 'w1_slave'), "name": "Sensor 3"} if len(device_folders) > 2 else None,
]
SENSOR_CONFIG = [s for s in SENSOR_CONFIG if s is not None]

# Data buffers (keep last 60 readings)
HISTORY_LENGTH = 60
timestamps = deque(maxlen=HISTORY_LENGTH)
data_series = [deque(maxlen=HISTORY_LENGTH) for _ in SENSOR_CONFIG]

def read_sensor(file_path):
    """Reads and parses temperature in Celsius from a single DS18B20 sensor file."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        retries = 5
        while lines[0].strip()[-3:] != 'YES' and retries > 0:
            time.sleep(0.1)
            with open(file_path, 'r') as f:
                lines = f.readlines()
            retries -= 1

        if lines[0].strip()[-3:] == 'YES':
            equals_pos = lines[1].find('t=')
            if equals_pos != -1:
                temp_string = lines[1][equals_pos + 2:].strip()
                temp_c = float(temp_string) / 1000.0
                return round(temp_c - 3.0, 2)  # Applied -3C calibration offset
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return None

# Setup Matplotlib Interactive Plot
fig, ax = plt.subplots(figsize=(10, 5))
lines = []
colors = ['#e63946', '#457b9d', '#2a9d8f']

for idx, sensor in enumerate(SENSOR_CONFIG):
    line, = ax.plot([], [], label=sensor['name'], color=colors[idx % len(colors)], lw=1.8)
    lines.append(line)

ax.set_title("Real-Time Temperature Monitoring (3 Sensors)")
ax.set_xlabel("Time")
ax.set_ylabel("Temperature (°C)")
ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
ax.grid(True, linestyle='--', alpha=0.5)
ax.legend(loc='upper left')
fig.autofmt_xdate()

def update(frame):
    now = datetime.datetime.now()
    valid_readings = []

    # Read all sensors
    min_temp = 100
    for idx, sensor in enumerate(SENSOR_CONFIG):
        temp = read_sensor(sensor['file'])
        
        if temp < min_temp:
            min_temp = temp        
        
        if temp is not None:
            data_series[idx].append(temp)
            valid_readings.append(temp)
        elif len(data_series[idx]) > 0:
            # Maintain previous reading if read dropped
            data_series[idx].append(data_series[idx][-1])
        else:
            data_series[idx].append(0.0)

    timestamps.append(now)
    
    # Turn on LED if any temp is under cutoff
    if min_temp < LED_CUTOFF:
        GPIO.output(LED_PIN, GPIO.HIGH)
        print("min temp too low: ", min_temp)
    else:
        print("min temp high: ", min_temp)
        GPIO.output(LED_PIN, GPIO.LOW)

    # Update line data
    for idx, line in enumerate(lines):
        line.set_data(timestamps, data_series[idx])

    # Dynamic Axis Rescaling
    if timestamps:
        ax.set_xlim(timestamps[0], timestamps[-1] + datetime.timedelta(seconds=2))

    all_current_temps = [val for series in data_series for val in series]
    if all_current_temps:
        min_temp = min(all_current_temps)
        max_temp = max(all_current_temps)
        ax.set_ylim(min_temp - 2, max_temp + 2)

    return lines

# Animate every 2000ms (2 seconds)
ani = animation.FuncAnimation(fig, update, interval=2000, blit=False, cache_frame_data=False)

try:
    plt.tight_layout()
    plt.show()
except KeyboardInterrupt:
    print("\nLive plotting stopped.")
