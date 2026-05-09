import RPi.GPIO as GPIO
import Adafruit_DHT  # Changed from dht11 to Adafruit_DHT
import time
import requests
import sys
import os

sys.stdout.reconfigure(line_buffering=True)

# Check if the system just rebooted
if not os.path.exists("/tmp/delay_completed"):
    print("System reboot detected. Waiting 10 minutes before starting the script...", flush=True)
    time.sleep(600)  # 600 seconds = 10 minutes
    open("/tmp/delay_completed", "w").close()  # Create a file to track delay completion

# ThingSpeak API Key
api_key = 'DEIN_THINGSPEAK_WRITE_API_KEY'
url = 'https://api.thingspeak.com/update'

# Pin Configuration
GPIO_PIN = 17  # Transistor control pin
Daten_PIN = 4  # DHT22 data pin

# Define Sensor Type
sensor = Adafruit_DHT.DHT22  # Using DHT22 instead of DHT11

# Timing Variables
Messung_Interval = 180
Schlaff_Interval = 1620

Temperatur_Messwerte = [None] * 10
Feuchtigkeit_Messwerte = [None] * 10
Temperatur_Summe = 0
Feuchtigkeit_Summe = 0

Erste_Wert_Temperatur = 0
Erste_Wert_Feuchtigkeit = 0
Zaehler = 1

# GPIO Setup
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()
GPIO.setup(GPIO_PIN, GPIO.OUT)

try:
    while True:
        GPIO.output(GPIO_PIN, GPIO.HIGH)  # Turn on sensor
        time.sleep(2)  # Stabilization time

        start_time = time.time()
        while time.time() - start_time < Messung_Interval:
            for i in range(len(Temperatur_Messwerte)):
                # Read temperature and humidity from DHT22
                humidity, temperature = Adafruit_DHT.read_retry(sensor, Daten_PIN)
                while humidity is None or temperature is None:
                    humidity, temperature = Adafruit_DHT.read_retry(sensor, Daten_PIN)

                Temperatur_Messwerte[i] = round(temperature, 2)
                Feuchtigkeit_Messwerte[i] = round(humidity, 2)
                Temperatur_Summe += Temperatur_Messwerte[i]
                Feuchtigkeit_Summe += Feuchtigkeit_Messwerte[i]

                print(f"Temperature: {Temperatur_Messwerte[i]:.1f} °C", flush=True)
                print(f"Humidity: {Feuchtigkeit_Messwerte[i]:.1f} %", flush=True)

                time.sleep(1)  # Delay between readings

            # Calculate Averages
            Mittelwert_Temperatur = round(Temperatur_Summe / len(Temperatur_Messwerte), 2)
            Mittelwert_Feuchtigkeit = round(Feuchtigkeit_Summe / len(Feuchtigkeit_Messwerte), 2)

            print(f"Mittelwert Temperatur: {Mittelwert_Temperatur:.1f} °C", flush=True)
            print(f"Mittelwert Feuchtigkeit: {Mittelwert_Feuchtigkeit:.1f} %", flush=True)

            Temperatur_Summe = 0
            Feuchtigkeit_Summe = 0

            if Zaehler == 1:
                Erste_Wert_Temperatur = Mittelwert_Temperatur
                Erste_Wert_Feuchtigkeit = Mittelwert_Feuchtigkeit

                # Send first values
                data = {'api_key': api_key, 'field1': Mittelwert_Temperatur, 'field2': Mittelwert_Feuchtigkeit}
                response = requests.post(url, data=data)
                if response.status_code == 200:
                    print("Erste Messwerte erfolgreich gesendet", flush=True)

            Sub_Temp = round(abs(Mittelwert_Temperatur - Erste_Wert_Temperatur), 2)
            Sub_Feuch = round(abs(Mittelwert_Feuchtigkeit - Erste_Wert_Feuchtigkeit), 2)

            print(f"Temperaturdifferenz: {Sub_Temp}", flush=True)
            print(f"Feuchtigkeitsdifferenz: {Sub_Feuch}", flush=True)

            # Send only if temperature or humidity change significantly
            if Sub_Temp >= 0.5 or Sub_Feuch >= 2:
                data = {'api_key': api_key}
                if Sub_Temp >= 0.5:
                    data['field1'] = Mittelwert_Temperatur
                    Erste_Wert_Temperatur = Mittelwert_Temperatur
                if Sub_Feuch >= 2:
                    data['field2'] = Mittelwert_Feuchtigkeit
                    Erste_Wert_Feuchtigkeit = Mittelwert_Feuchtigkeit

                response = requests.post(url, data=data)
                if response.status_code == 200:
                    print("Aktualisierte Messwerte erfolgreich gesendet", flush=True)

            Zaehler += 1

        GPIO.output(GPIO_PIN, GPIO.LOW)  # Turn off sensor
        print(f"Sensor ist ausgeschaltet für {Schlaff_Interval // 60} Minuten.", flush=True)
        time.sleep(Schlaff_Interval)

finally:
    GPIO.cleanup()
