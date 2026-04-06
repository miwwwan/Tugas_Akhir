import serial
import wave
import struct
import csv
import time

# --- KONFIGURASI ---
PORT = "COM8"           
BAUD = 921600
SAMPLE_RATE = 25000     # <--- UBAH INI (Sebelumnya 44100)
DURATION = 40
OUTPUT_WAV = "Noise_Kanan_wean.wav" # (Opsional: ganti nama file biar tidak tertukar)
OUTPUT_CSV = "Noise_Kanan_wean.csv"

# Inisialisasi Serial
print(f"Membuka port {PORT}...")
ser = serial.Serial(PORT, BAUD)

# PENTING: Tunggu ESP32 restart/siap setelah serial dibuka
print("Menunggu ESP32 siap (2 detik)...")
time.sleep(2) 

# Bersihkan buffer sisa (garbage data) sebelum mulai
ser.reset_input_buffer()

# --- KIRIM PERINTAH START ---
print("Mengirim perintah START ke ESP32...")
ser.write(b'S')  # Kirim karakter 'S'

total_samples = SAMPLE_RATE * DURATION
total_bytes = total_samples * 2   # 2 byte per sample (16-bit)

print(f"Merekam selama {DURATION} detik...")

# Membaca data mentah dari serial
# Code ini akan 'blocking' sampai jumlah byte terpenuhi
raw = ser.read(total_bytes)

# --- KIRIM PERINTAH STOP ---
print("Selesai mengambil data. Mengirim perintah STOP...")
ser.write(b'E') # Kirim karakter 'E' agar ESP32 berhenti klik

ser.close()

# --- 1. SIMPAN SEBAGAI WAV ---
wav = wave.open(OUTPUT_WAV, "w")
wav.setnchannels(1)
wav.setsampwidth(2)
wav.setframerate(SAMPLE_RATE)
wav.writeframes(raw)
wav.close()
print(f"File WAV tersimpan: {OUTPUT_WAV}")

# --- 2. KONVERSI & SIMPAN SEBAGAI CSV ---
print("Mengonversi ke CSV...")
samples = struct.unpack(f"<{total_samples}h", raw)

with open(OUTPUT_CSV, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["Sample_Index", "Amplitude"]) 
    
    for i, amplitude in enumerate(samples):
        writer.writerow([i, amplitude])

print(f"File CSV tersimpan: {OUTPUT_CSV}")