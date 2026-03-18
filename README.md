# Automatic Clothesline System

An IoT-based autonomous clothesline that detects rain, retracts clothes automatically, sends notifications to your phone, and logs weather data — built on ESP32 with MicroPython.
## Demo
[Watch Demo Video](https://drive.google.com/file/d/1y_oTeR_VdOd5Jy7SF4ZiMp0rPfVo6vlA/view?usp=drive_link)


# Overview

This project implements a smart clothesline system that monitors weather conditions using a BME280 sensor and a rain sensor. When rain is detected the system retracts the clothesline using a NEMA 17 stepper motor, alerts the user via Telegram and a local buzzer, and logs all sensor readings to a CSV file for later analysis.

The system operates in two independent layers:

- **Local layer** — the rain sensor and stepper motor work without any internet connection. Clothes are always protected regardless of WiFi status.
- **Cloud layer** — when WiFi is available, Telegram push notifications are sent for rain detection, rain prediction, and system status updates.



# Features

- Automatic clothesline retraction when rain is detected
- Automatic extension when rain stops 
- Rain prediction using humidity and pressure trends from BME280
- Telegram push notifications for all events
- Local buzzer alerts with distinct patterns for each event
- CSV data logging to ESP32 internal flash
- System runs fully without WiFi
- notification Telegram



# Hardware Requirements

| Component | Purpose |
|---|---|
| ESP32 DevKit V1 | Main microcontroller |
| BME280 sensor | Temperature, humidity, pressure |
| Rain sensor module | Rain detection (analog + digital output) |
| NEMA 17 stepper motor | Clothesline retraction mechanism |
| A4988 or DRV8825 driver | Stepper motor driver |
| passive buzzer | Local audio alerts |
| 12V power supply | Motor power |
|Gear belt  | Clothesline |



# Wiring

# BME280
| BME280 Pin | ESP32 Pin |
|---|---|
| VCC | 3.3V |
| GND | GND |
| SDA | GPIO 21 |
| SCL | GPIO 22 |

# Rain Sensor
| Rain Module Pin | ESP32 Pin |
|---|---|
| VCC | 3.3V |
| GND | GND |
| DO (digital) | GPIO 15 |
| AO (analog) | GPIO 34 |

# Stepper Driver (A4988)
| Driver Pin | ESP32 Pin |
|---|---|
| STEP | GPIO 26 |
| DIR | GPIO 27 |
| ENABLE | GPIO 25 |
| VMOT | 12V external supply |
| GND (ESP32) | ESP32 GND |
| GND (power) | Power supply GND |

# Buzzer
| Buzzer Pin | ESP32 Pin |
|---|---|
| Signal | GPIO 14 |
| Other pin | GND |

> **Important:** ESP32 GND and the motor power supply GND must be connected together.
  **Important:** 12v Power supply for motor must be connected first before anything else. 




# MicroPython Libraries Used
All libraries used are built into MicroPython — no external packages needed:
- `machine` — GPIO, I2C, ADC, PWM
- `network` — WiFi
- `urequests` — HTTP requests
- `time` — delays and timestamps
- `uos` — filesystem access


# Setup

# 1.Configure credentials

Open `main.py` and edit the configuration block at the top:

```python
WIFI_SSID     = "your_wifi_name"
WIFI_PASSWORD = "your_wifi_password"

TELEGRAM_TOKEN   = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"
```

# 2. Get Telegram credentials

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts to create your bot
3. Copy the token provided
4. Start a chat with your new bot (search its name, press Start)
5. Open this URL in a browser replacing YOUR\_TOKEN:
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
6. Find the number next to `"id"` inside `"chat"` — that is your chat ID


# 3. Calibrate the rain sensor

Run the code with the sensor completely dry and note the printed `Rain Analog` value. Subtract 300 from that value and set it as `RAIN_THRESHOLD`. For example if the dry value reads 3800, set:


RAIN_THRESHOLD = 3500

# 4. Calibrate motor steps

For this project the full length was `RETRACT_STEPS = 500` for the Gear belt. Increase the value until the clothesline travels its full length.


# Notifications

# Telegram 
Sends instant push notifications to your phone when WiFi is available.

# Buzzer 
Works without internet. Five distinct patterns identify each event by sound:

| Pattern | Meaning |
|---|---|
| 2 short beeps | System started OK |
| 4 rapid beeps | WiFi offline at boot |
| 3 long beeps | Rain detected — retracting |
| 1 long beep | Rain stopped — extending |
| 2 short + 1 long | Rain likely soon (prediction) |


# Data Logging

Every BME280 reading is saved to `/data.csv` on the ESP32 internal flash. 

**CSV format:**

timestamp,temperature,humidity,pressure,rain
1234567,29.4,82.1,1007.2,0
1234572,29.5,83.0,1006.8,0
1234577,29.6,86.2,1004.1,1


The `rain` column is `1` when the rain sensor detects water, `0` when dry.

**To retrieve your data:**
1. Connect ESP32 to laptop via USB
2. Open Thonny → View → Files
3. On the ESP32 side, right-click `data.csv` → Download to computer
4. Open in Excel or Google Sheets
5. Insert a line chart on humidity and pressure columns


# System Logic

# Rain detection (motor control)
The rain sensor analog output is averaged over 10 readings to eliminate noise. When the averaged value drops below `RAIN_THRESHOLD`, rain is detected and the motor retracts immediately — regardless of WiFi status.

# Rain prediction (notification only)
When humidity exceeds `HUMIDITY_THRESHOLD` (85%) AND pressure drops below `PRESSURE_THRESHOLD` (1005 hPa) simultaneously, a prediction alert is sent. A 5-minute cooldown prevents spam.

# State machine
The main loop implements a four-state finite state machine:

| State | Condition | Action |
|---|---|---|
| 1 | Rain starts, not retracted | Retract + notify |
| 2 | Rain continues, retracted | Hold position |
| 3 | Rain stops, was retracted | Count dry readings, extend when confirmed |
| 4 | No rain, not retracted | Monitor only |

The `DRY_CONFIRM_COUNT = 3` setting requires 3 consecutive dry readings (15 seconds at 5s interval) before extending. This prevents the motor extending during brief pauses in rainfall.



# Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `RAIN_THRESHOLD` | 3500 | Analog value below which rain is detected |
| `RETRACT_STEPS` | 500 | Motor steps for full retraction |
| `EXTEND_STEPS` | 500 | Motor steps for full extension |
| `STEP_DELAY_US` | 800 | Microseconds between motor pulses |
| `HUMIDITY_THRESHOLD` | 85 | Humidity % for rain prediction |
| `PRESSURE_THRESHOLD` | 1005 | Pressure hPa for rain prediction |
| `READ_INTERVAL_SEC` | 5 | Seconds between sensor reads |
| `DRY_CONFIRM_COUNT` | 3 | Dry readings before extending |
| `PREDICTION_COOLDOWN_SEC` | 300 | Seconds between prediction alerts |
| `AUTO_EXTEND` | True | Extend automatically when rain stops |
| `BUZZER_PWM` | True | True = passive buzzer|
| `BUZZER_PIN` | 14 | GPIO pin for buzzer |
| `LOG_FILE` | /data.csv | Path for sensor data log |



# Troubleshooting

**Rain sensor triggers without rain**
- Recalibrate `RAIN_THRESHOLD` — read dry value and subtract 300
- Adjust the blue potentiometer on the sensor module

**Telegram not receiving messages**
- Confirm the bot has been started (search bot name, press Start)
- Verify chat ID from getUpdates URL
- Check WiFi is connected (printed in serial monitor on boot)


# Future Improvements

- Firebase Realtime Database integration for cloud data storage
- Flutter mobile app with live dashboard
- Firebase Cloud Functions for serverless notification logic
- Gear reduction stage for increased motor torque on longer lines
- Limit switches for end-of-travel motor protection
- NTP time synchronisation for real timestamps in CSV
- Solar power integration for outdoor autonomous deployment

![Images](./asset/Top%20View.jpg )
![Images](./asset/Front%20view.jpg)
![Images](./asset/Inner%20View.jpg)
![Images](./asset/Side%20view.jpg)
![Images](./asset/Back%20view.jpg)


## Author

Built as an mid-semester academic IoT project demonstrating autonomous weather-responsive embedded systems design by Ametepey Duke Dela Brightton and Tatchie Emmanuel
