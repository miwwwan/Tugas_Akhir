import sounddevice as sd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import csv
import queue
import sys
from datetime import datetime
import os

# --- KONFIGURASI ---
SAMPLE_RATE = 44100   # Hz
BLOCK_SIZE = 2048     # Buffer diperbesar sedikit biar aman dari lag
CHANNELS = 1          
WINDOW_SIZE = 44100   # Lebar jendela grafik (1 detik)
FILENAME_PREFIX = "data_teoae_"

# Queue untuk transfer data antar thread (PENTING AGAR TIDAK CRASH)
q = queue.Queue()

# Setup Nama File
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"{FILENAME_PREFIX}{timestamp}.csv"

print(f"Mempersiapkan perekaman ke: {filename}")

# Setup File CSV
# Kita buka file di awal dan biarkan terbuka selama program jalan
csv_file = open(filename, mode='w', newline='')
csv_writer = csv.writer(csv_file)
csv_writer.writerow(["Amplitude"]) # Header cukup Amplitude saja (Index = Nomor Baris)

def audio_callback(indata, frames, time, status):
    """Thread Khusus Audio: Harus super cepat, tidak boleh ada proses berat disini"""
    if status:
        print(status, file=sys.stderr)
    # Masukkan copy data ke antrian untuk diproses thread utama
    q.put(indata.copy())

def update_plot(frame):
    """Thread Utama: Menggambar grafik dan menulis file"""
    while not q.empty():
        data = q.get()
        
        # 1. Update Grafik (Efek Scrolling)
        shift = len(data)
        plotdata[:] = np.roll(plotdata, -shift, axis=0)
        plotdata[-shift:] = data
        
        # 2. Simpan ke CSV (VERSI CEPAT)
        # Tidak perlu looping for-loop python yang lambat.
        # Langsung tulis blok data sekaligus.
        # Kita ubah bentuk data jadi list of list agar diterima csv_writer
        # Contoh: dari [0.1, 0.2] menjadi [[0.1], [0.2]]
        reshaped_data = data.reshape(-1, 1).tolist() 
        csv_writer.writerows(reshaped_data)

    # Update garis
    line.set_ydata(plotdata)
    return line,

# --- SETUP GRAFIK & STREAM ---
try:
    print("\n--- Memulai Sistem TEOAE ---")
    
    fig, ax = plt.subplots(figsize=(10, 5))
    plotdata = np.zeros((WINDOW_SIZE, 1))
    
    line, = ax.plot(plotdata, color='#00ff00', linewidth=0.8) # Warna hijau ala osiloskop
    ax.set_facecolor('black') # Background hitam biar keren
    ax.set_ylim([-1, 1])      # Range Amplitude
    ax.set_xlim([0, WINDOW_SIZE])
    ax.set_title(f"Real-Time Monitor | File: {filename}", color='black')
    ax.grid(True, color='gray', linestyle='--', alpha=0.5)

    # Stream Audio
    stream = sd.InputStream(
        channels=CHANNELS,
        samplerate=SAMPLE_RATE,
        callback=audio_callback,
        blocksize=BLOCK_SIZE
    )

    print(f"Merekam... Data disimpan real-time ke {filename}")
    print("Tutup jendela grafik untuk Stop.")

    with stream:
        ani = FuncAnimation(fig, update_plot, interval=20, blit=True, cache_frame_data=False)
        plt.show()

except KeyboardInterrupt:
    print("Berhenti.")
except Exception as e:
    print(f"Error: {e}")
finally:
    # Tutup file saat program mati
    csv_file.close()
    print("\nFile CSV telah ditutup dan diamankan.")