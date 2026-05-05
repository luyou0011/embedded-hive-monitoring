import RPi.GPIO as GPIO
import requests
import time
import os
from hx711 import HX711
import sys
sys.stdout.flush()  # Force output flush

# Check if the system just rebooted
if not os.path.exists("/tmp/delay_completed"):
    print("System reboot detected. Waiting 5 minutes before starting the script...", flush=True)
    time.sleep(300)  # 300 seconds = 5 minutes
    open("/tmp/delay_completed", "w").close()  # Create a file to track delay completion

# ThingSpeak API Key and URL
api_key = 'LD55T24KCSU367JF'
url = 'https://api.thingspeak.com/update'

# GPIO pin for transistor control
GPIO_PIN = 14
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_PIN, GPIO.OUT)

# Intervals
SLEEP_INTERVAL = 3420  # Sleep for 1 minute
AKTIV_INTERVAL = 180  # Active for 2 minutes

# Calibration file
CALIBRATION_FILE = "/home/pi/Desktop/HX711/calibration_data_4.txt"

# Save calibration data
def save_calibration_data(offset_1, offset_2, offset_3, offset_4, ratio_1, ratio_2, ratio_3, ratio_4):
    with open(CALIBRATION_FILE, 'w') as f:
        f.write(f"{offset_1}\n")
        f.write(f"{offset_2}\n")
        f.write(f"{offset_3}\n")
        f.write(f"{offset_4}\n")
        f.write(f"{ratio_1}\n")
        f.write(f"{ratio_2}\n")
        f.write(f"{ratio_3}\n")
        f.write(f"{ratio_4}\n")

# Load calibration data
def load_calibration_data():
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE, 'r') as f:
            lines = f.readlines()
            if len(lines) == 8:
                return (
                    int(lines[0].strip()), int(lines[1].strip()),
                    int(lines[2].strip()), int(lines[3].strip()),
                    float(lines[4].strip()), float(lines[5].strip()),
                    float(lines[6].strip()), float(lines[7].strip())
                )
    return None, None, None, None, None, None, None, None

try:
    # Initialize HX711 modules
    hx_1 = HX711(dout_pin=27, pd_sck_pin=22)
    hx_2 = HX711(dout_pin=6, pd_sck_pin=13)
    hx_3 = HX711(dout_pin=23, pd_sck_pin=24)
    hx_4 = HX711(dout_pin=12, pd_sck_pin=26)

    # Load or calibrate
    offset_1, offset_2, offset_3, offset_4, ratio_1, ratio_2, ratio_3, ratio_4 = load_calibration_data()
    if all(v is not None for v in [offset_1, offset_2, offset_3, offset_4, ratio_1, ratio_2, ratio_3, ratio_4]):
        hx_1.set_offset(offset_1)
        hx_1.set_scale_ratio(ratio_1)
        hx_2.set_offset(offset_2)
        hx_2.set_scale_ratio(ratio_2)
        hx_3.set_offset(offset_3)
        hx_3.set_scale_ratio(ratio_3)
        hx_4.set_offset(offset_4)
        hx_4.set_scale_ratio(ratio_4)
        print("Loaded saved calibration values.", flush=True)
    else:
        print("No saved calibration found. Calibrating...", flush=True)
        print("Please remove all loads and wait for 5 seconds.", flush=True)
#        input()
        print("Waiting for tare calibration to complete automatically...", flush=True)
        time.sleep(5)  # Wait 5 seconds before proceeding
        
        hx_1.zero()
        offset_1 = hx_1.get_raw_data_mean()
        hx_2.zero()
        offset_2 = hx_2.get_raw_data_mean()
        hx_3.zero()
        offset_3 = hx_3.get_raw_data_mean()
        hx_4.zero()
        offset_4 = hx_4.get_raw_data_mean()
        
        print("Place a known weight and wait for 5 seconds.", flush=True)
#        input()
        print("Waiting for tare calibration to complete automatically...", flush=True)
        time.sleep(5)  # Wait 5 seconds before proceeding
        known_weight_grams = 1000
        individual_weight = known_weight_grams / 4
        
        ratio_1 = hx_1.get_data_mean() / individual_weight
        ratio_2 = hx_2.get_data_mean() / individual_weight
        ratio_3 = hx_3.get_data_mean() / individual_weight
        ratio_4 = hx_4.get_data_mean() / individual_weight
        
        hx_1.set_scale_ratio(ratio_1)
        hx_2.set_scale_ratio(ratio_2)
        hx_3.set_scale_ratio(ratio_3)
        hx_4.set_scale_ratio(ratio_4)
        
        save_calibration_data(offset_1, offset_2, offset_3, offset_4, ratio_1, ratio_2, ratio_3, ratio_4)
        print("Calibration complete.", flush=True)

    counter = 1
    Compare_Value = None

    while True:
        # Power on sensors
        GPIO.output(GPIO_PIN, GPIO.HIGH)
        print("Sensors powered on.", flush=True)
        time.sleep(2)  # Stabilize sensors

        start_time = time.time()
        while time.time() - start_time < AKTIV_INTERVAL:
            read_1 = hx_1.get_weight_mean(20)
            read_2 = hx_2.get_weight_mean(20)
            read_3 = hx_3.get_weight_mean(20)
            read_4 = hx_4.get_weight_mean(20)

            total_weight = max(0, read_1 + read_2 + read_3 + read_4)
            print("Weight:", total_weight, "g", flush=True)

            if counter == 1 or abs(total_weight - Compare_Value) >= 500:
                data = {
                    'api_key': api_key,
                    'field3': round(total_weight / 1000, 3)
                }
                response = requests.post(url, data=data)
                if response.status_code == 200:
                    print("Weight sent successfully.", flush=True)
                else:
                    print(f"Error sending data: {response.status_code}", flush=True)
                Compare_Value = total_weight
            else:
                print("Weight change < 500g, not sent.", flush=True)

            counter += 1
            time.sleep(25)

        # Power off sensors
        GPIO.output(GPIO_PIN, GPIO.LOW)
        print(f"Sensors powered off. Sleeping for {SLEEP_INTERVAL} seconds.", flush=True)
        time.sleep(SLEEP_INTERVAL)

except (KeyboardInterrupt, SystemExit):
    print("Exiting program.", flush=True)

finally:
    GPIO.cleanup()
