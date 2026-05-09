import sounddevice as sd
import wave
import time
import base64
import json
import os
import numpy as np
import math
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from scipy.fftpack import fft
from scipy.signal import butter, lfilter
from datetime import datetime

sd.default.device = "sysdefault:CARD=sndrpigooglevoi"
sd.default.dtype = "int32"
sd.default.channels = 1


# Configuration
CHANNELS = 2
RATE = 48000  # Correct sample rate
RECORD_SECONDS = 5
BLOCK_SIZE = 100 * 1024  # Each block ~100 KB
TIMEOUT = 15
LOCAL_DIR = "/home/pi/Desktop/SPH/lokale_aufnahmen"

# AWS IoT MQTT Client setup
Client = AWSIoTMQTTClient('RPiClient')
Client.configureEndpoint('XXX.amazonaws.com', 8883)
Client.configureCredentials('/home/pi/AWS/root-ca.pem', '/home/pi/AWS/private.pem.key', '/AWS/certificate.pem.crt')

letzte_Signal = None

def Server_Signal_callback(client, userdata, message):
    global letzte_Signal
    letzte_Signal = time.time()
    print(f"Es wurde ein Signal vom Server empfangen")

def Verbinden_Mit_Dem_Server():
    try:
        Client.connect()
        print("Mit dem Server verbunden")
        Client.subscribe("Server/Signal", 1, Server_Signal_callback)
        return True
    except Exception as e:
        print(f"Verbindung zu AWS IoT fehlgeschlagen: {e}")
        return False

def Ist_Server_Online():
    if letzte_Signal and (time.time() - letzte_Signal) < TIMEOUT:
        return True
    return False

def remove_dc_offset(data):
    return data - np.mean(data)

def calculate_rms(data):
    squared_data = data ** 2
    rms = np.sqrt(np.mean(squared_data))
    return max(rms, 1e-12)  # Prevent zero or near-zero values

def calculate_peak_frequency(data, RATE):
    fft_result = np.abs(fft(data))
    half_len = len(fft_result) // 2
    freqs = np.fft.fftfreq(len(data), 1.0 / RATE)[:half_len]
    peak_freq = freqs[np.argmax(fft_result[:half_len])]
    return peak_freq

def high_pass_filter(data, cutoff, fs, order=5):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    return lfilter(b, a, data)

def Event_Trigger(frames, RATE):
    audio_data = np.frombuffer(frames, dtype=np.int32)  # Correct dtype
    
    # Remove DC offset
    audio_data = remove_dc_offset(audio_data)

    # Apply high-pass filter
    filtered_audio = high_pass_filter(audio_data, cutoff=50, fs=RATE)

    # Calculate RMS and amplitude
    rms = calculate_rms(filtered_audio)
    amplitude_db = 20 * math.log10(rms)

    # Calculate peak frequency
    peak_freq = calculate_peak_frequency(filtered_audio, RATE)

    print(f"Peak Frequency: {peak_freq:.2f} Hz, Amplitude: {amplitude_db:.2f} dB")
    return peak_freq, amplitude_db

def Speichern_Audio_Datei_Als_Wave(wave_datei, frames):
    if not os.path.exists(LOCAL_DIR):
        os.makedirs(LOCAL_DIR)

    datei_pfad = os.path.join(LOCAL_DIR, wave_datei)

    try:
        with wave.open(datei_pfad, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(4)  #32-bit audio
            wf.setframerate(RATE)
            wf.writeframes(frames)

        print(f"Aufnahme gespeichert unter {datei_pfad}")
    except Exception as e:
        print(f"Fehler beim Speichern der Datei {datei_pfad}: {e}")

def Kodieren(datei_pfad):
    try:
        with open(datei_pfad, 'rb') as f:
            audio_datei = f.read()
        return base64.b64encode(audio_datei).decode('utf-8')  # ✅ Fixed encoding
    except Exception as e:
        print(f"Die Audio-Datei konnte nicht kodiert werden: {e}")
        return None

def senden(datei_pfad):
    json_frames = Kodieren(datei_pfad)
    if json_frames is None:
        return False

    json_bytes = json_frames.encode('utf-8')
    total_blocks = (len(json_bytes) + BLOCK_SIZE - 1) // BLOCK_SIZE

    for i in range(0, len(json_bytes), BLOCK_SIZE):
        block = json_bytes[i:i + BLOCK_SIZE]
        payload = {
            "filename": os.path.basename(datei_pfad),
            "Block_Nummer": i // BLOCK_SIZE,
            "audio_data": block.decode('utf-8'),
            "Total_Blocks": total_blocks
        }
        try:
            Client.publish(topic='Bienen/Geräusche', QoS=1, payload=json.dumps(payload))
            print(f"Block {i // BLOCK_SIZE} erfolgreich gesendet")
        except Exception as e:
            print(f"Senden fehlgeschlagen: {e}")
            return False
    return True

def verarbeite_datei(wave_datei):
    datei_pfad = os.path.join(LOCAL_DIR, wave_datei)
    if senden(datei_pfad):
        os.remove(datei_pfad)
        print(f"Datei {datei_pfad} erfolgreich gesendet und gelöscht.")
    else:
        print(f"Datei {datei_pfad} konnte nicht gesendet werden.")

def Aufnehmen(wave_datei):
    try:
        print("🎙️ Aufnahme startet...")
        audio_data = sd.rec(
            int(RATE * RECORD_SECONDS),
            samplerate=RATE,
            channels=CHANNELS,
            dtype='int32'  
        )
        sd.wait()

        frames = audio_data.tobytes()
        peak_freq, amplitude_db = Event_Trigger(frames, RATE)

        if 50 <= peak_freq <= 1000 and 25 <= amplitude_db <= 110:
            print("Frequenz im Bereich, Audio wird gespeichert.")
            Speichern_Audio_Datei_Als_Wave(wave_datei, frames)
        else:
            print("Frequenz außerhalb des Bereichs, Aufnahme verworfen.")

    except Exception as e:
        print(f"Fehler bei der Aufnahme: {e}")

# Main loop
count = 1
if Verbinden_Mit_Dem_Server():
    while True:
        wave_datei = f"Aufgenommene_Audio_{count}.wav"
        Aufnehmen(wave_datei)

        if Ist_Server_Online():
            verarbeite_datei(wave_datei)

        count += 1
        time.sleep(10)
else:
    print("Verbindung zum Server fehlgeschlagen")
