import time
import Adafruit_ADS1x15
import requests
import sys
import os


sys.stdout.reconfigure(line_buffering=True)  # Forces real-time logging

# Check if the system just rebooted
if not os.path.exists("/tmp/delay_completed"):
    print("System reboot detected. Waiting 15 minutes before starting the script...", flush=True)
    time.sleep(900)  # 900 seconds = 15 minutes
    open("/tmp/delay_completed", "w").close()  # Create a file to track delay completion

# ThingSpeak API Key and URL
api_key = 'DEIN_THINGSPEAK_WRITE_API_KEY'
url = 'https://api.thingspeak.com/update'

# ADC-Instanz erstellen
adc = Adafruit_ADS1x15.ADS1115()

# Verstärkung (GAIN) einstellen
GAIN = 1  # Messbereich: ±4.096 V

# Spannungsteiler-Verhältnis berechnen (R1 = 100kΩ, R2 = 33kΩ)
divider_ratio = (100 + 33) / 33  # R1 + R2 / R2 = 133 / 33 ≈ 4.0303

def calculate_battery_percentage(voltage):
    """
    Berechnet den Batteriestand basierend auf der angegebenen Spannung und der Tabelle.
    """
    # LiPo-Spannungs-SoC-Tabelle
    voltage_soc_table = [
        (4.20, 100),
        (4.15, 95),
        (4.10, 90),
        (4.05, 85),
        (4.00, 80),
        (3.95, 75),
        (3.90, 70),
        (3.85, 65),
        (3.80, 60),
        (3.75, 55),
        (3.70, 50),
        (3.65, 45),
        (3.60, 40),
        (3.55, 35),
        (3.50, 30),
        (3.45, 25),
        (3.40, 20),
        (3.35, 15),
        (3.30, 10),
        (3.25, 5),
        (3.20, 0)
    ]

    # Werte vergleichen und interpolieren
    for i in range(len(voltage_soc_table) - 1):
        high_voltage, high_soc = voltage_soc_table[i]
        low_voltage, low_soc = voltage_soc_table[i + 1]

        if high_voltage >= voltage >= low_voltage:
            # Lineare Interpolation zwischen den Punkten
            percentage = high_soc + (voltage - high_voltage) * (low_soc - high_soc) / (low_voltage - high_voltage)
            return round(percentage, 1)

    # Falls Spannung außerhalb des Bereichs liegt
    if voltage > 4.20:
        return 100.0
    elif voltage < 3.20:
        return 0.0

print('[Drücken Sie Strg+C, um das Skript zu beenden]', flush=True)
try:
    # Hauptprogrammschleife
    while True:
        # Rohwert von Kanal 0 lesen
        raw_value = adc.read_adc(0, gain=GAIN)

        # Rohwert in Spannung umrechnen
        V_ADC = (raw_value * 4.096) / 32767  # GAIN = 1 → ±4.096 V

        # Batteriespannung berechnen
        V_Battery = V_ADC * divider_ratio

        # Batterieprozentsatz berechnen
        battery_percentage = calculate_battery_percentage(V_Battery)

        # Ergebnisse ausgeben
        print(f"ADC Spannung: {V_ADC:.3f} V", flush=True)
        print(f"Batterie Spannung: {V_Battery:.3f} V", flush=True)
        print(f"Batterie Ladezustand: {battery_percentage:.1f}%", flush=True)
        
        # Daten an ThingSpeak senden
        try:
            data = {
                'api_key': api_key,
                'field4': battery_percentage  # Sends battery percentage to ThingSpeak Field 4
            }
            response = requests.post(url, data=data)

            if response.status_code == 200:
                print("Battery status sent successfully to ThingSpeak.", flush=True)
            else:
                print(f"Error sending data: {response.status_code}", flush=True)

        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}", flush=True)
        time.sleep(1200)

except KeyboardInterrupt:
    print('Skript beendet!', flush=True)
