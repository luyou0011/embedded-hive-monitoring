import RPi.GPIO as GPIO
import time
GPIO.setwarnings(False)  # Disable unnecessary warnings


# GPIO-Pin-Nummerierung verwenden (BCM-Modus)
GPIO.setmode(GPIO.BCM)

# Pin 17 als Ausgang definieren
LED_PIN = 15
GPIO.setup(LED_PIN, GPIO.OUT)

# PWM auf GPIO 17 starten (Frequenz: 100 Hz)
pwm = GPIO.PWM(LED_PIN, 75)  # 100 Hz
pwm.start(1)  # 10% Duty Cycle (sehr niedrige Intensität)

try:
    # LED dauerhaft leuchten lassen
    while True:
        time.sleep(1)  # Endlos warten

except KeyboardInterrupt:
    # Bei einem manuellen Abbruch (Strg+C) alles aufräumen
    pwm.stop()
    GPIO.cleanup()
