import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import butter, sosfilt

# --- KONFIGURASI USER (GANTI DISINI) ---
# 1. Nama File CSV (Harus ada di folder yang sama)
TARGET_FILE = "data_teoae_20260112_153946.csv" 

# 2. Konfigurasi Audio
SAMPLE_RATE = 44100 

# 3. Konfigurasi Filter (Bandpass)
# Kita hanya meloloskan frekuensi antara LOW_CUT sampai HIGH_CUT
# Contoh TEOAE/Suara Manusia biasanya di 100Hz - 8000Hz
LOW_CUT = 100.0   # Buang frekuensi di bawah 100Hz (seperti dengung listrik 50Hz)
HIGH_CUT = 8000.0 # Buang frekuensi di atas 8000Hz (noise desis)
FILTER_ORDER = 4  # Kekuatan filter (makin tinggi makin tajam, standar = 4)

# --- FUNGSI FILTER ---
def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
    """
    Fungsi untuk membuang noise (Bandpass Filter).
    Hanya meloloskan suara di antara lowcut dan highcut.
    """
    nyq = 0.5 * fs # Frekuensi Nyquist
    low = lowcut / nyq
    high = highcut / nyq
    # Membuat desain filter
    sos = butter(order, [low, high], btype='band', output='sos')
    # Menerapkan filter ke data
    filtered_signal = sosfilt(sos, data)
    return filtered_signal

def main():
    print(f"--- Membuka File: {TARGET_FILE} ---")

    # 1. BACA DATA
    try:
        df = pd.read_csv(TARGET_FILE)
        # Ambil data dari kolom pertama
        raw_data = pd.to_numeric(df.iloc[:, 0], errors='coerce').dropna().values
    except FileNotFoundError:
        print(f"[ERROR] File '{TARGET_FILE}' tidak ditemukan!")
        print("Pastikan nama file di kodingan sudah sesuai dengan file asli.")
        return
    except Exception as e:
        print(f"[ERROR] {e}")
        return

    # 2. BUAT SUMBU WAKTU
    num_samples = len(raw_data)
    duration = num_samples / SAMPLE_RATE
    time_axis = np.linspace(0, duration, num_samples)
    print(f"Durasi Audio: {duration:.2f} detik ({num_samples} sampel)")

    # 3. PROSES FILTERING
    print(f"Menerapkan Filter Bandpass ({LOW_CUT}Hz - {HIGH_CUT}Hz)...")
    filtered_data = butter_bandpass_filter(raw_data, LOW_CUT, HIGH_CUT, SAMPLE_RATE, FILTER_ORDER)

    # 4. PLOTTING DENGAN PLOTLY
    print("Membuat Grafik Interaktif...")
    
    # Buat 2 Subplot (Atas: Raw, Bawah: Filtered)
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True, # Zoom di atas, yang bawah ikut nge-zoom
        vertical_spacing=0.1,
        subplot_titles=(f"Sinyal Asli (Raw) - {TARGET_FILE}", "Sinyal Setelah Filter (Bandpass)")
    )

    # Plot 1: Sinyal Asli
    # Gunakan Scattergl (WebGL) agar cepat merender ribuan titik data
    fig.add_trace(
        go.Scattergl(x=time_axis, y=raw_data, name="Raw Signal", 
                     line=dict(color='gray', width=1), opacity=0.8),
        row=1, col=1
    )

    # Plot 2: Sinyal Filtered
    fig.add_trace(
        go.Scattergl(x=time_axis, y=filtered_data, name="Filtered Signal", 
                     line=dict(color='blue', width=1.5)),
        row=2, col=1
    )

    # Update Layout agar terlihat keren
    fig.update_layout(
        height=700, # Tinggi gambar
        title_text="Analisis Sinyal Audio (Zoomable)",
        hovermode="x unified", # Saat kursor digerakkan, muncul info semua grafik
        template="plotly_dark" # Tema Gelap (Biar seperti software engineering pro)
    )

    # Label Sumbu
    fig.update_xaxes(title_text="Waktu (detik)", row=2, col=1)
    fig.update_yaxes(title_text="Amplitudo", row=1, col=1)
    fig.update_yaxes(title_text="Amplitudo", row=2, col=1)

    # Tampilkan
    fig.show()

if __name__ == "__main__":
    main()