

from machine import Pin, I2C, ADC, PWM
import network
import urequests
import time

#WiFi 
WIFI_SSID     = "iotlab"
WIFI_PASSWORD = "@50Ghana"

#Telegram notification
TELEGRAM_TOKEN   = "8732753716:AAEcevS4KoXXuoBpqCUGDgJfOIgH-4moPdY"
TELEGRAM_CHAT_ID = "6218203651"

# BME280 
BME280_ADDRESS = 0x76

#Rain sensor pins
RAIN_DIGITAL_PIN = 15
RAIN_ANALOG_PIN  = 34

#Rain detection threshold 
# Dry value typically 3500-4095

RAIN_THRESHOLD = 3500

#Stepper motor pins A4988
STEP_PIN   = 26
DIR_PIN    = 27
ENABLE_PIN = 25

# Motor calibration
# 500 steps
RETRACT_STEPS = 500
EXTEND_STEPS  = 500
STEP_DELAY_US = 800

#  Buzzer
BUZZER_PIN = 14
BUZZER_PWM = True

#BME280 prediction thresholds
HUMIDITY_THRESHOLD = 85         #  above this =  likely to rain
PRESSURE_THRESHOLD = 1005       #  below this = likely to rain

# System timing
READ_INTERVAL_SEC       = 5
DRY_CONFIRM_COUNT       = 3     
PREDICTION_COOLDOWN_SEC = 300  

# Behaviour 
AUTO_EXTEND = True              # extend back automatically when rain stops

# --- Data log ---
LOG_FILE = "/data.csv"

# Built-in — no external bme280.py file needed
class BME280:

    def __init__(self, i2c, address=0x76):
        self.i2c     = i2c
        self.address = address
        self._load_calibration()

    def _read_bytes(self, register, length):
        return self.i2c.readfrom_mem(self.address, register, length)

    def _load_calibration(self):
        cal         = self._read_bytes(0x88, 24)
        self.dig_T1 = cal[1] << 8 | cal[0]
        self.dig_T2 = self._signed(cal[3]  << 8 | cal[2])
        self.dig_T3 = self._signed(cal[5]  << 8 | cal[4])
        self.dig_P1 = cal[7] << 8 | cal[6]
        self.dig_P2 = self._signed(cal[9]  << 8 | cal[8])
        self.dig_P3 = self._signed(cal[11] << 8 | cal[10])
        self.dig_P4 = self._signed(cal[13] << 8 | cal[12])
        self.dig_P5 = self._signed(cal[15] << 8 | cal[14])
        self.dig_P6 = self._signed(cal[17] << 8 | cal[16])
        self.dig_P7 = self._signed(cal[19] << 8 | cal[18])
        self.dig_P8 = self._signed(cal[21] << 8 | cal[20])
        self.dig_P9 = self._signed(cal[23] << 8 | cal[22])
        hcal        = self._read_bytes(0xA1, 1)
        self.dig_H1 = hcal[0]
        hcal2       = self._read_bytes(0xE1, 7)
        self.dig_H2 = self._signed(hcal2[1] << 8 | hcal2[0])
        self.dig_H3 = hcal2[2]
        self.dig_H4 = self._signed((hcal2[3] << 4) | (hcal2[4] & 0x0F))
        self.dig_H5 = self._signed((hcal2[5] << 4) | (hcal2[4] >> 4))
        self.dig_H6 = self._signed(hcal2[6])
        self.i2c.writeto_mem(self.address, 0xF2, bytes([0x01]))
        self.i2c.writeto_mem(self.address, 0xF4, bytes([0x27]))
        self.i2c.writeto_mem(self.address, 0xF5, bytes([0xA0]))

    def _signed(self, val):
        return val - 65536 if val > 32767 else val

    def read(self):
        data  = self._read_bytes(0xF7, 8)
        adc_P = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        adc_T = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        adc_H = (data[6] << 8)  |  data[7]

        v1          = (adc_T / 16384.0 - self.dig_T1 / 1024.0) * self.dig_T2
        v2          = (adc_T / 131072.0 - self.dig_T1 / 8192.0) ** 2 * self.dig_T3
        t_fine      = int(v1 + v2)
        temperature = (v1 + v2) / 5120.0

        v1 = t_fine / 2.0 - 64000.0
        v2 = v1 * v1 * self.dig_P6 / 32768.0
        v2 += v1 * self.dig_P5 * 2.0
        v2 = v2 / 4.0 + self.dig_P4 * 65536.0
        v1 = (self.dig_P3 * v1 * v1 / 524288.0 + self.dig_P2 * v1) / 524288.0
        v1 = (1.0 + v1 / 32768.0) * self.dig_P1
        if v1 == 0:
            pressure = 0
        else:
            pressure  = 1048576.0 - adc_P
            pressure  = ((pressure - v2 / 4096.0) * 6250.0) / v1
            v1        = self.dig_P9 * pressure * pressure / 2147483648.0
            v2        = pressure * self.dig_P8 / 32768.0
            pressure  = pressure + (v1 + v2 + self.dig_P7) / 16.0
            pressure /= 100.0

        h        = t_fine - 76800.0
        h        = (adc_H - (self.dig_H4 * 64.0 + self.dig_H5 / 16384.0 * h)) * \
                   (self.dig_H2 / 65536.0 * (1.0 + self.dig_H6 / 67108864.0 * h * \
                   (1.0 + self.dig_H3 / 67108864.0 * h)))
        humidity = h * (1.0 - self.dig_H1 * h / 524288.0)
        humidity = max(0.0, min(100.0, humidity))

        return round(temperature, 2), round(pressure, 2), round(humidity, 2)



# buzzer works independently of WiFi

#   Try flipping BUZZER_PWM between True and False



if BUZZER_PWM:
    _buzzer_pwm = PWM(Pin(BUZZER_PIN), freq=1000, duty=0)
    def buzzer_on():
        _buzzer_pwm.duty(512)
    def buzzer_off():
        _buzzer_pwm.duty(0)
else:
    _buzzer_pin = Pin(BUZZER_PIN, Pin.OUT)
    _buzzer_pin.value(0)
    def buzzer_on():
        _buzzer_pin.value(1)
    def buzzer_off():
        _buzzer_pin.value(0)


def beep(on_ms=150, off_ms=100, count=1):
    """Core beep — on_ms=buzz duration, off_ms=gap, count=repeats"""
    for i in range(count):
        buzzer_on()
        time.sleep_ms(on_ms)
        buzzer_off()
        if i < count - 1:
            time.sleep_ms(off_ms)


def beep_boot():
    """2 short beeps — system started OK"""
    beep(on_ms=120, off_ms=100, count=2)


def beep_wifi_fail():
    """4 rapid beeps — WiFi offline at boot"""
    beep(on_ms=80, off_ms=80, count=4)


def beep_rain():
    """3 long beeps — rain detected, retracting"""
    beep(on_ms=500, off_ms=200, count=3)


def beep_clear():
    """1 long beep — rain stopped, extending"""
    beep(on_ms=800, off_ms=0, count=1)


def beep_prediction():
    """2 short + 1 long — rain predicted soon"""
    beep(on_ms=120, off_ms=100, count=2)
    time.sleep_ms(200)
    beep(on_ms=500, off_ms=0, count=1)


def init_log():
    """Create CSV with header if file does not exist yet"""
    try:
        import uos
        uos.stat(LOG_FILE)
        print("Data log found:", LOG_FILE)
    except OSError:
        with open(LOG_FILE, "w") as f:
            f.write("timestamp,temperature,humidity,pressure,rain\n")
        print("Data log created:", LOG_FILE)


def log_data(temperature, humidity, pressure, rain):
    """
    Append one reading row to the CSV.
    rain = 1 when sensor detects water, 0 when dry.
    """
    try:
        with open(LOG_FILE, "a") as f:
            f.write("{},{},{},{},{}\n".format(
                time.time(),
                temperature,
                humidity,
                pressure,
                1 if rain else 0))
    except Exception as e:
        print("  [Log] write error:", e)


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("WiFi already connected:", wlan.ifconfig()[0])
        return True

    print("Connecting to WiFi: {}".format(WIFI_SSID))
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    timeout = 20
    elapsed = 0
    while not wlan.isconnected() and elapsed < timeout:
        time.sleep(1)
        elapsed += 1
        print("  waiting {}/{}s".format(elapsed, timeout))

    if wlan.isconnected():
        print("WiFi connected — IP:", wlan.ifconfig()[0])
        return True
    else:
        print("WiFi FAILED — Telegram disabled")
        print("Buzzer + motor + logging still active")
        return False


def send_telegram(message):
    url     = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_TOKEN)
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = urequests.post(url, json=payload, timeout=8)
        if response.status_code == 200:
            print("  [Telegram] sent OK")
        else:
            print("  [Telegram] HTTP error:", response.status_code)
        response.close()
    except Exception as e:
        print("  [Telegram] failed:", e)


# buzzer_pattern:
#   "boot"       → 2 short beeps
#   "wifi_fail"  → 4 rapid beeps
#   "rain"       → 3 long beeps
#   "clear"      → 1 long beep
#   "prediction" → 2 short + 1 long
#   "default"    → 2 short beeps


def notify(message, buzzer_pattern="default"):
    print("NOTIFY: {}".format(message))

    
    if buzzer_pattern == "boot":
        beep_boot()
    elif buzzer_pattern == "wifi_fail":
        beep_wifi_fail()
    elif buzzer_pattern == "rain":
        beep_rain()
    elif buzzer_pattern == "clear":
        beep_clear()
    elif buzzer_pattern == "prediction":
        beep_prediction()
    else:
        beep(on_ms=150, off_ms=100, count=2)

    if wifi_ok:
        send_telegram(message)
    else:
        print("  Telegram skipped — no WiFi")




print("\n" + "=" * 52)
print("  CLOTHESLINE SYSTEM STARTING UP")
print("=" * 52)

# WiFi
wifi_ok = connect_wifi()

# I2C + BME280
i2c     = I2C(0, scl=Pin(22), sda=Pin(21))
devices = i2c.scan()
print("I2C devices found:", [hex(d) for d in devices])

bme_ok = False
if not devices:
    print("ERROR: No I2C device — check BME280 wiring")
else:
    try:
        bme     = BME280(i2c=i2c, address=BME280_ADDRESS)
        t, p, h = bme.read()
        print("BME280 OK  T:{:.1f}C  P:{:.1f}hPa  H:{:.1f}%".format(t, p, h))
        bme_ok = True
    except Exception as e:
        print("BME280 error:", e)
        if devices and devices[0] == 119:
            print("Tip: change BME280_ADDRESS to 0x77")

# Rain sensor
rain_digital = Pin(RAIN_DIGITAL_PIN, Pin.IN)
rain_analog  = ADC(Pin(RAIN_ANALOG_PIN))
rain_analog.atten(ADC.ATTN_11DB)
print("Rain sensor OK  DO:GPIO{}  AO:GPIO{}".format(
      RAIN_DIGITAL_PIN, RAIN_ANALOG_PIN))

# Stepper driver
step_pin   = Pin(STEP_PIN,   Pin.OUT)
dir_pin    = Pin(DIR_PIN,    Pin.OUT)
enable_pin = Pin(ENABLE_PIN, Pin.OUT)
enable_pin.value(0)
print("Stepper driver OK  STEP:{}  DIR:{}  EN:{}".format(
      STEP_PIN, DIR_PIN, ENABLE_PIN))

# Data log
init_log()

# Status summary
print("-" * 52)
print("WiFi      :", "OK - " + network.WLAN(network.STA_IF).ifconfig()[0]
                     if wifi_ok else "OFFLINE")
print("BME280    :", "OK" if bme_ok else "NOT FOUND")
print("Rain sens :", "OK")
print("Motor     :", "OK")
print("Buzzer    :", "GPIO{} ({})".format(
      BUZZER_PIN, "PWM passive" if BUZZER_PWM else "active"))
print("Data log  :", LOG_FILE)
print("Notify    :", "Telegram + Buzzer" if wifi_ok else "Buzzer only")
print("Threshold :", "Rain <", RAIN_THRESHOLD, " Humid >",
      HUMIDITY_THRESHOLD, "% Press <", PRESSURE_THRESHOLD, "hPa")
print("=" * 52 + "\n")

# Boot beep pattern depends on WiFi status
if wifi_ok:
    notify(
        "Clothesline system online. WiFi:OK BME280:{} Monitoring started.".format(
        "OK" if bme_ok else "FAIL"),
        buzzer_pattern="boot")
else:
    notify(
        "Boot complete. WiFi OFFLINE — buzzer and motor active.",
        buzzer_pattern="wifi_fail")


def step_motor(steps, direction):
    """direction 0 = retract   direction 1 = extend"""
    dir_pin.value(direction)
    for _ in range(steps):
        step_pin.value(1)
        time.sleep_us(STEP_DELAY_US)
        step_pin.value(0)
        time.sleep_us(STEP_DELAY_US)


def retract_clothesline():
    print("MOTOR: retracting...")
    step_motor(RETRACT_STEPS, 0)
    print("MOTOR: retracted")


def extend_clothesline():
    print("MOTOR: extending...")
    step_motor(EXTEND_STEPS, 1)
    print("MOTOR: extended")


def read_rain_average(samples=10):
    """Average 10 ADC reads to eliminate noise"""
    total = 0
    for _ in range(samples):
        total += rain_analog.read()
        time.sleep_ms(10)
    return total // samples


def is_raining():
    """Returns (raining_bool, analog_value, digital_value)"""
    analog_val  = read_rain_average()
    digital_val = rain_digital.value()
    raining     = analog_val < RAIN_THRESHOLD
    return raining, analog_val, digital_val


def check_rain_prediction(humidity, pressure):
    return humidity > HUMIDITY_THRESHOLD and pressure < PRESSURE_THRESHOLD




clothes_retracted    = False
dry_count            = 0
last_prediction_time = 0



print("Monitoring. Cycle:{}s  Dry:{} reads  Cooldown:{}s\n".format(
      READ_INTERVAL_SEC, DRY_CONFIRM_COUNT, PREDICTION_COOLDOWN_SEC))

while True:

    print("-" * 52)


    # Rain sensor read (done first so log_data gets current rain status)
    raining, analog_val, digital_val = is_raining()

    print("Rain analog  : {}  (threshold {} — lower = wetter)".format(
          analog_val, RAIN_THRESHOLD))
    print("Rain digital : {}  (0 = wet   1 = dry)".format(digital_val))

  
    #  BME280 — read, log, and check prediction
   
    if bme_ok:
        try:
            temperature, pressure, humidity = bme.read()

            print("Temp     : {:.1f} C".format(temperature))
            print("Humidity : {:.1f}%  (alert > {}%)".format(
                  humidity, HUMIDITY_THRESHOLD))
            print("Pressure : {:.1f} hPa  (alert < {} hPa)".format(
                  pressure, PRESSURE_THRESHOLD))

            # Log reading with current rain status
            log_data(temperature, humidity, pressure, raining)
            print("  [Log] saved")

            # Check prediction
            if check_rain_prediction(humidity, pressure):
                now = time.time()
                if now - last_prediction_time > PREDICTION_COOLDOWN_SEC:
                    notify(
                        "Rain prediction. Humidity {:.0f}% pressure {:.0f}hPa. Rain likely soon.".format(
                        humidity, pressure),
                        buzzer_pattern="prediction")
                    last_prediction_time = now
                else:
                    secs_left = PREDICTION_COOLDOWN_SEC - (now - last_prediction_time)
                    print("Prediction: cooldown ({}s left)".format(int(secs_left)))
            else:
                print("Prediction: conditions normal")

        except Exception as e:
            print("BME280 read error:", e)

    else:
        print("BME280 unavailable — prediction + logging skipped")

   
    # Motor state machine
  

    if raining and not clothes_retracted:
        # STATE 1: Rain just started
        print("STATE 1: Rain detected — retracting now")
        retract_clothesline()
        clothes_retracted = True
        dry_count         = 0
        notify("Rain detected. Clothes retracted automatically.",
               buzzer_pattern="rain")

    elif raining and clothes_retracted:
        # STATE 2: Still raining, already retracted
        print("STATE 2: Rain continues — holding retracted")
        dry_count = 0

    elif not raining and clothes_retracted:
        # STATE 3: Rain stopped — confirm before extending
        dry_count += 1
        print("STATE 3: No rain — dry count {}/{} before extending".format(
              dry_count, DRY_CONFIRM_COUNT))

        if AUTO_EXTEND and dry_count >= DRY_CONFIRM_COUNT:
            print("STATE 3: Rain confirmed stopped — extending now")
            extend_clothesline()
            clothes_retracted = False
            dry_count         = 0
            notify("Rain stopped. Clothes extended back automatically.",
                   buzzer_pattern="clear")

    else:
        # STATE 4: All clear
        print("STATE 4: All clear — clothesline extended and monitoring")

    print("-" * 52 + "\n")
    time.sleep(READ_INTERVAL_SEC)


