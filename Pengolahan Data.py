import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import butter, sosfilt
from scipy.signal import find_peaks
from scipy.signal import windows

# --- KONFIGURASI ---
TARGET_FILE = r'D:\oae\Perekaman dan Pengolahan Data\rekaman_test.csv'
SAMPLE_RATE = 25000
LOW_CUTOFF = 500.0
HIGH_CUTOFF = 12000.0

# Batasan Waktu Baru
START_TIME = 0
END_TIME = 40

# --- FUNGSI FILTER ---
def butter_bandpass_filter(data, lowcut, highcut, fs, order=1):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    sos = butter(order, [low, high], btype='band', analog=False, output='sos')
    y = sosfilt(sos, data)
    return y

# --- 1. BACA DATA ---
print(f"--- Membuka File: {TARGET_FILE} ---")
try:
    df = pd.read_csv(TARGET_FILE)
    raw_data_full = df['Amplitude'].values
except Exception as e:
    print(f"[ERROR] {e}")
    exit()

start_idx = int(START_TIME * SAMPLE_RATE)
end_idx = int(END_TIME * SAMPLE_RATE)

# Pastikan indeks tidak melebihi panjang data
raw_data = raw_data_full[start_idx:end_idx]
print(f"Mengambil data dari index {start_idx} ke {end_idx} ({len(raw_data)} samples)")

# --- 3. PROSES CLEANING (FILTERING) ---
# Menghilangkan DC Offset
data_centered = raw_data - np.mean(raw_data)

# Terapkan Band-Pass Filter
print(f"Menerapkan Band-Pass Filter ({LOW_CUTOFF}Hz - {HIGH_CUTOFF}Hz)...")
clean_data = butter_bandpass_filter(data_centered, LOW_CUTOFF, HIGH_CUTOFF, SAMPLE_RATE, order=4)

sliced_samples = len(data_centered)
sliced_duration = sliced_samples / SAMPLE_RATE
# --- 4. SUMBU WAKTU (Disesuaikan dengan offset start_time) ---
time_axis = np.linspace(0, sliced_duration, sliced_samples)

signal_abs = np.abs(clean_data)

max_amp = np.max(signal_abs)

threshold_val = 0.20 * max_amp 

min_distance_samples = int(0.01 * SAMPLE_RATE) # 10ms window

print(f"Max Amp: {max_amp:.2f}")
print(f"Threshold set ke: {threshold_val:.2f} (20% dari Max)")
print(f"Min Distance: {min_distance_samples} samples")

# Cari puncak
peaks_indices, properties = find_peaks(signal_abs, height=threshold_val, distance=min_distance_samples)

# Dapatkan waktu dan nilai asli (bukan absolut) pada titik tersebut
peak_times = time_axis[peaks_indices]
peak_values = clean_data[peaks_indices]

print(f"Ditemukan {len(peaks_indices)} klik (campuran A dan 1/3A).")

EPOCH_DURATION_MS = 20  # Durasi setiap potongan (standar OAE: 20ms)
EPOCH_SAMPLES = int((EPOCH_DURATION_MS / 1000) * SAMPLE_RATE)

# Container untuk menyimpan potongan data
epochs = []
valid_indices = [] # Menyimpan index puncak yang valid (tidak di ujung file)

print(f"Memotong data menjadi segmen {EPOCH_DURATION_MS}ms ({EPOCH_SAMPLES} sampel)...")

for idx in peaks_indices:
    # Cek apakah potongan melebihi panjang data
    if idx + EPOCH_SAMPLES <= len(clean_data):
        # Ambil data dari titik klik sampai 20ms ke depan
        segment = clean_data[idx : idx + EPOCH_SAMPLES]
        
        epochs.append(segment)
        valid_indices.append(idx)

# Ubah list menjadi Numpy Array (Matrix)
# Dimensi: [Jumlah_Klik x Jumlah_Sampel]
epochs_matrix = np.array(epochs)

print(f"Berhasil membuat Matrix Epochs dengan ukuran: {epochs_matrix.shape}")
print(f"Total Epochs: {epochs_matrix.shape[0]}")
print(f"Panjang per Epoch: {epochs_matrix.shape[1]} sampel")

SAFE_END_MS = 19.5 
safe_idx = int((SAFE_END_MS / 1000) * SAMPLE_RATE)

# Echo Removal (Untuk menghilangkan artifact stimulus awal)
ECHO_REMOVE_MS = 4
echo_remove_idx = int((ECHO_REMOVE_MS / 1000) * SAMPLE_RATE)

# Parameter Windowing (Tukey-like Profile dari Jurnal)
DISCARD_START_MS = 1.92
DISCARD_END_MS = 1.28
SMOOTHING_MS = 2.56

# Siapkan Windowing Array
n_total = EPOCH_SAMPLES
idx_start_valid = int((DISCARD_START_MS / 1000) * SAMPLE_RATE)
idx_end_valid = n_total - int((DISCARD_END_MS / 1000) * SAMPLE_RATE)
n_taper = int((SMOOTHING_MS / 1000) * SAMPLE_RATE)

custom_window = np.zeros(n_total)
idx_flat_start = idx_start_valid + n_taper
idx_flat_end = idx_end_valid - n_taper

# Buat bentuk trapesium (Tukey)
if idx_flat_start < idx_flat_end:
    taper_up = np.sin(np.linspace(0, np.pi/2, n_taper))**2
    custom_window[idx_start_valid : idx_flat_start] = taper_up
    custom_window[idx_flat_start : idx_flat_end] = 1.0
    taper_down = np.cos(np.linspace(0, np.pi/2, n_taper))**2
    custom_window[idx_flat_end : idx_end_valid] = taper_down
else:
    # Fallback jika sampling rate rendah
    custom_window[idx_start_valid:idx_end_valid] = 1.0

# === 2. PERSIAPAN DATA ===
CLICKS_PER_BLOCK = 8
num_epochs = len(epochs_matrix)
num_blocks = num_epochs // CLICKS_PER_BLOCK
valid_length = num_blocks * CLICKS_PER_BLOCK

# Copy data agar aman
epochs_processed = epochs_matrix[:valid_length].copy()

# A. SAFETY CUT (Lakukan di awal sekali)
epochs_processed[:, safe_idx:] = 0
print(f"Safety Cut: Data > {SAFE_END_MS}ms dinolkan.")

# B. HITUNG THRESHOLD OTOMATIS
# Gunakan statistik dari area tengah (4ms - 15ms)
check_start = int((4.0/1000) * SAMPLE_RATE)
check_end = int((15.0/1000) * SAMPLE_RATE)
valid_segments = epochs_processed[:, check_start:check_end]
noise_ref = np.std(valid_segments)
REJECTION_THRESHOLD = 3.0 * noise_ref # User-defined threshold (auto)

print(f"Auto-Threshold Rejection: {REJECTION_THRESHOLD:.6f}")

# === 3. PROSES LOOP: HITUNG -> CEK -> BAGI (BALANCED) ===
buffer_A_clean = []
buffer_B_clean = []

total_blocks = 0
valid_counter = 0 # Counter khusus untuk data yang lolos seleksi

print(f"Memproses {num_blocks} blok DNLR dengan Balanced Strategy...")

for i in range(num_blocks):
    total_blocks += 1
    
    # 1. Ambil Blok
    start_idx = i * CLICKS_PER_BLOCK
    block_epochs = epochs_processed[start_idx : start_idx + CLICKS_PER_BLOCK]
    
    # 2. Hitung Single Trial DNLR
    sweep_1 = np.sum(block_epochs[0:4], axis=0)
    sweep_2 = np.sum(block_epochs[4:8], axis=0)
    single_trial = (sweep_1 - sweep_2) / 8.0
    

    single_trial[:echo_remove_idx] = 0
    
    # 4. ARTIFACT REJECTION (CEK DULU SEBELUM MASUK BUFFER)
    # Cek area window valid saja
    check_segment = single_trial[idx_start_valid : idx_end_valid]
    
    if np.max(np.abs(check_segment)) <= REJECTION_THRESHOLD:
        # --- DATA VALID ---
        
        # 5. TERAPKAN WINDOWING (Sesuai Jurnal)
        # Mengalikan sinyal dengan profil Tukey (halus di tepi)
        weighted_signal = single_trial * custom_window
        
        # 6. DISTRIBUSI SEIMBANG (BALANCED SPLITTING)
        # Ganjil/Genap berdasarkan urutan kedatangan data VALID, bukan urutan asli
        if valid_counter % 2 == 0:
            buffer_A_clean.append(weighted_signal)
        else:
            buffer_B_clean.append(weighted_signal)
            
        valid_counter += 1
        
    else:
        # --- DATA DITOLAK ---
        pass # Tidak dimasukkan ke buffer manapun

# === 4. HASIL AKHIR ===
rejected_count = total_blocks - valid_counter
acceptance_rate = (valid_counter / total_blocks) * 100

print(f"\n--- LAPORAN ARTIFACT REJECTION (BALANCED) ---")
print(f"Total Blok Diproses : {total_blocks}")
print(f"Ditolak (Artifact)  : {rejected_count}")
print(f"Diterima (Valid)    : {valid_counter} ({acceptance_rate:.2f}%)")
print(f"\n--- KESEIMBANGAN BUFFER ---")
print(f"Isi Buffer A        : {len(buffer_A_clean)}")
print(f"Isi Buffer B        : {len(buffer_B_clean)}")
print(f"Selisih             : {abs(len(buffer_A_clean) - len(buffer_B_clean))} (Harus <= 1)")

if len(buffer_A_clean) > 0 and len(buffer_B_clean) > 0:
    min_len = min(len(buffer_A_clean), len(buffer_B_clean))
    
    # Ambil data sejumlah min_len
    mean_A = np.mean(buffer_A_clean[:min_len], axis=0)
    mean_B = np.mean(buffer_B_clean[:min_len], axis=0)
    
    # Grand Average
    teoae_final = (mean_A + mean_B) / 2
else:
    print("[ERROR] Data habis setelah rejection! Coba perbesar Threshold.")

from scipy.signal import stft, istft

ALPHA = 2.663  # Konstanta latensi (bisa 5.326 untuk neonatus)
BETA = -0.8    # Eksponen frekuensi
MULTIPLIER = 3.0 # Batas atas (3x latensi rata-rata)

# Parameter STFT
N_PERSEG = 128  # Jendela 128 sampel (~5.12 ms)

HOP_SIZE = 10 
N_OVERLAP = N_PERSEG - HOP_SIZE # 128 - 10 = 118 sampel overlap

print(f"--- Konfigurasi Time-Frequency Filtering ---")
print(f"Power Law: t < {MULTIPLIER} * {ALPHA} * f^{BETA}")
print(f"STFT: Window={N_PERSEG}, Overlap={N_OVERLAP} (High Resolution)")

# Fungsi Pembuat & Penerap Mask
def apply_time_freq_filter(signal_data, fs, name="Signal"):
    # 1. Lakukan STFT
    f, t, Zxx = stft(signal_data, fs, window='hamming', nperseg=N_PERSEG, noverlap=N_OVERLAP)
    
    # 2. Buat Binary Mask
    # Matriks Mask inisialisasi nol
    mask = np.zeros_like(Zxx, dtype=float)
    
    # Loop per frekuensi untuk menentukan batas waktu (latensi)
    for i, freq in enumerate(f):
        if freq == 0:
            limit_time = 100 # Frekuensi 0 (DC) biarkan lolos panjang (atau filter nanti)
        else:
            # Hitung batas waktu latensi untuk frekuensi ini (dalam detik)
            # Rumus Eq(1) & (24): t_limit = 3 * a * f^b
            limit_time = MULTIPLIER * (ALPHA * 1e-3) * (freq/1000)**BETA 
            # Note: Jurnal pakai f dalam kHz untuk rumus a*f^b standard, 
            # tapi mari kita cek unit a. Biasanya a dalam ms. 
            # Jika a=2.663 (ms), maka limit_time dalam ms.
            # Jadi kita konversi limit_time ke detik (/1000).
            # Rumus jurnal: tau(f) = a * f^b. a dalam ms? 
            # Cek Source 111: "tau(f) (in seconds)... f (in Hz)". 
            # Jika f in Hz, a harus disesuaikan. 
            # Standard Kemp: a ~ 5ms at 1kHz. 2.663 cocok jika f dalam kHz.
            # Mari kita asumsikan a=2.663e-3 jika f dalam Hz, atau f dalam kHz.
            # Kita pakai f dalam kHz untuk aman: (freq/1000).
            limit_time = MULTIPLIER * (ALPHA * 1e-3) * ((freq/1000.0 + 1e-9)**BETA)

        # 3. Isi Mask
        # Jika waktu (t) < limit_time, maka Mask = 1 (Keep), sisanya 0 (Remove)
        # t adalah array waktu dari STFT
        mask[i, :] = np.where(t < limit_time, 1.0, 0.0)
    
    # 4. Terapkan Mask ke Sinyal STFT
    Zxx_filtered = Zxx * mask
    
    # 5. Kembalikan ke Time Domain (ISTFT)
    _, signal_filtered = istft(Zxx_filtered, fs, window='hamming', nperseg=N_PERSEG, noverlap=N_OVERLAP)
    
    # Potong/Padding agar panjangnya sama persis dengan input (karena efek padding STFT)
    if len(signal_filtered) > len(signal_data):
        signal_filtered = signal_filtered[:len(signal_data)]
    elif len(signal_filtered) < len(signal_data):
        signal_filtered = np.pad(signal_filtered, (0, len(signal_data) - len(signal_filtered)))
        
    return signal_filtered, f, t, mask, Zxx

# === B. TERAPKAN KE BUFFER A DAN BUFFER B ===
# Pastikan kita menggunakan mean_A dan mean_B dari tahap sebelumnya
if 'mean_A' in locals() and 'mean_B' in locals():
    print("Memproses Buffer A...")
    filt_A, f_stft, t_stft, mask_A, Zxx_A = apply_time_freq_filter(mean_A, SAMPLE_RATE, "Buffer A")
    
    print("Memproses Buffer B...")
    filt_B, _, _, _, Zxx_B = apply_time_freq_filter(mean_B, SAMPLE_RATE, "Buffer B")
    
    # Update Variable Utama
    mean_A_filtered = filt_A
    mean_B_filtered = filt_B
    
    # Hitung Ulang Final TEOAE & Noise Floor dari sinyal yang sudah difilter
    teoae_final_filtered = (mean_A_filtered + mean_B_filtered) / 2
    noise_floor_filtered = (mean_A_filtered - mean_B_filtered) / 2
    
    print("Selesai. Buffer A dan B telah di-filter menggunakan Cochlear Latency Mask.")
    
else:
    print("[ERROR] Data Mean A/B tidak ditemukan. Jalankan tahap sebelumnya terlebih dahulu.")

buffer_A_new = []
buffer_B_new = []
buffer_Noise_new = [] # Container untuk Noise (Eq. 3)

valid_counter = 0

for i in range(num_blocks):
    # Ambil 1 Blok
    start_idx = i * CLICKS_PER_BLOCK
    block_epochs = epochs_processed[start_idx : start_idx + CLICKS_PER_BLOCK]
    
    # --- HITUNG SIGNAL (Eq. 2) ---
    sweep_1 = np.sum(block_epochs[0:4], axis=0)
    sweep_2 = np.sum(block_epochs[4:8], axis=0)
    signal_trial = (sweep_1 - sweep_2) / 8.0 # Pengurangan (Difference)
    
    # --- HITUNG NOISE (Eq. 3) ---
    # Jurnal Eq. 3: Rata-rata dari semua 8 epoch (Penjumlahan)
    # Ini menangkap noise latar belakang yang tidak terkunci dengan stimulus
    noise_trial = np.sum(block_epochs, axis=0) / 8.0 # Penjumlahan (Sum)
    
    # --- PRE-PROCESSING (Echo Cut & Windowing) ---
    # Terapkan perlakuan yang sama persis ke Signal dan Noise
    signal_trial[:echo_remove_idx] = 0
    noise_trial[:echo_remove_idx] = 0
    
    # Cek Validasi (Artifact Rejection) pada Signal
    check_segment = signal_trial[idx_start_valid : idx_end_valid]
    
    if np.max(np.abs(check_segment)) <= REJECTION_THRESHOLD:
        # Terapkan Windowing
        signal_weighted = signal_trial * custom_window
        noise_weighted = noise_trial * custom_window
        
        # Simpan ke Buffer (Balanced Split untuk Signal)
        if valid_counter % 2 == 0:
            buffer_A_new.append(signal_weighted)
        else:
            buffer_B_new.append(signal_weighted)
        
        # Simpan Noise (Semua noise valid dikumpulkan)
        buffer_Noise_new.append(noise_weighted)
        
        valid_counter += 1

# Hitung Mean
mean_A = np.mean(buffer_A_new, axis=0)
mean_B = np.mean(buffer_B_new, axis=0)
mean_Noise_Eq3 = np.mean(buffer_Noise_new, axis=0) # Noise Floor rata-rata

print(f"Data Terkumpul: {valid_counter} Sweeps")
print(f"Mean Signal & Mean Noise (Eq.3) berhasil dihitung.")


print("\nMenerapkan Time-Frequency Filter...")
filt_A, f_stft, _, _, _ = apply_time_freq_filter(mean_A, SAMPLE_RATE, "Buffer A")
filt_B, _, _, _, _ = apply_time_freq_filter(mean_B, SAMPLE_RATE, "Buffer B")
filt_Noise, _, _, _, _ = apply_time_freq_filter(mean_Noise_Eq3, SAMPLE_RATE, "Noise Eq3")

# Sinyal Final TEOAE (Rata-rata A dan B yang sudah difilter)
signal_final = (filt_A + filt_B) / 2
noise_final = filt_Noise

# --- 15. FREQUENCY ANALYSIS (SNR CALCULATION) & DATA PREP FOR TABLE ---

# FFT Parameters
n_fft = len(signal_final)
freqs_fft = np.fft.rfftfreq(n_fft, 1/SAMPLE_RATE) # Rename var agar tidak bentrok
fft_window = windows.hann(n_fft)

# Hitung FFT (Magnitude)
fft_signal = np.abs(np.fft.rfft(signal_final * fft_window))
fft_noise = np.abs(np.fft.rfft(noise_final * fft_window))

# Konversi ke dBSPL (Relative)
mag_signal_db = 20 * np.log10(fft_signal + 1e-12)
mag_noise_db = 20 * np.log10(fft_noise + 1e-12)

# Tabel SNR Setup
FREQ_BANDS = [1000, 1500, 2000, 3000, 4000] 
BAND_WIDTH = 150 # Hz (+/-)

# Container data untuk Tabel Plotly
col_freq = []
col_sig = []
col_noise = []
col_snr = []
col_status = []
col_color = [] # Untuk warna sel status

overall_pass = 0

print(f"\n--- MENGHITUNG SNR UNTUK TABEL VISUAL ---")

for f_center in FREQ_BANDS:
    # Cari index frekuensi
    idx_band = np.where((freqs_fft >= f_center - BAND_WIDTH) & (freqs_fft <= f_center + BAND_WIDTH))[0]
    
    col_freq.append(f_center)
    
    if len(idx_band) > 0:
        # Rata-rata power di pita frekuensi
        p_signal = np.mean(mag_signal_db[idx_band])
        p_noise = np.mean(mag_noise_db[idx_band])
        snr = p_signal - p_noise
        
        # Simpan ke list (format string 2 desimal)
        col_sig.append(f"{p_signal:.2f}")
        col_noise.append(f"{p_noise:.2f}")
        col_snr.append(f"{snr:.2f}")
        
        # Cek Kriteria (Contoh: SNR > 3dB untuk status, >6dB untuk Pass Criteria Total)
        if snr >= 6.0:
            col_status.append("PASS")
            col_color.append("lightgreen")
        else:
            col_status.append("REFER")
            col_color.append("lightsalmon")

        if snr >= 6.0:
            overall_pass += 1
    else:
        col_sig.append("N/A")
        col_noise.append("N/A")
        col_snr.append("N/A")
        col_status.append("N/A")
        col_color.append("white")

print(f"Pass Criteria: {overall_pass}/{len(FREQ_BANDS)} Bands with SNR > 6dB")

# --- 16. WAVE REPRODUCIBILITY (WWR) & VISUALIZATION (GABUNGAN TABEL + GRAFIK) ---

print(f"\n--- ANALISIS KORELASI & MEMBUAT GRAFIK GABUNGAN ---")

if 'mean_A' in locals() and 'mean_B' in locals():
    # 1. Filter Buffer A & B (Independent Filtering untuk WWR)
    filt_A, _, _, _, _ = apply_time_freq_filter(mean_A, SAMPLE_RATE, "Buffer A")
    filt_B, _, _, _, _ = apply_time_freq_filter(mean_B, SAMPLE_RATE, "Buffer B")
    
    # 2. Hitung WWR
    corr_matrix = np.corrcoef(filt_A, filt_B)
    wwr_score = corr_matrix[0, 1] * 100 
    
    # 3. KEPUTUSAN DIAGNOSTIK
    if bands_passed := overall_pass >= 3 and wwr_score >= 70.0:
        status_text = "PASS"
        main_color = "lime"
    else:
        status_text = "REFER"
        main_color = "red"
        
    print(f"Status Akhir: [{status_text}] (SNR Passed: {overall_pass}, WWR: {wwr_score:.1f}%)")

    # --- 4. BUAT LAYOUT: TABEL (ATAS) & GRAFIK (BAWAH) ---
    
    # Kita alokasikan ruang: 
    # row_heights=[0.25, 0.75] -> Tabel dapat 25%, Grafik dapat 75%
    # vertical_spacing=0.08 -> Memberi sedikit jarak antara tabel dan grafik
    fig_final = make_subplots(
        rows=2, cols=2,
        row_heights=[0.30, 0.70], 
        vertical_spacing=0.08,
        specs=[[{"type": "table", "colspan": 2}, None],
               [{"type": "xy"}, {"type": "xy"}]],
        subplot_titles=(f"Analisis TEOAE (Status: {status_text})", 
                        "", 
                        f"Waveform Overlay (WWR: {wwr_score:.1f}%)", 
                        "Scatter Correlation")
    )

    # === BAGIAN 1: TABEL HASIL (Row 1, Col 1) ===
    # Kita set height=30 (pixel) per baris agar pas
    fig_final.add_trace(go.Table(
        header=dict(
            values=['<b>Freq (Hz)</b>', '<b>Signal (dB)</b>', '<b>Noise (dB)</b>', '<b>SNR (dB)</b>', '<b>Status</b>'],
            fill_color='black',
            font=dict(color='white', size=12),
            align='center',
            height=30 # Tinggi Header
        ),
        cells=dict(
            values=[col_freq, col_sig, col_noise, col_snr, col_status],
            fill_color=[['#222']*len(col_freq), ['#222']*len(col_freq), ['#222']*len(col_freq), ['#222']*len(col_freq), col_color],
            font=dict(color=['white', 'white', 'white', 'white', 'black'], size=12),
            align='center',
            height=30 # Tinggi Baris Data
        )
    ), row=1, col=1)

    # === BAGIAN 2: GRAFIK SINYAL (Row 2, Col 1 & 2) ===
    time_axis = np.linspace(0, EPOCH_DURATION_MS, len(filt_A))

    # Plot Overlay
    fig_final.add_trace(go.Scattergl(
        x=time_axis, y=filt_A, name="Buffer A (Filt)",
        line=dict(color='#00ff00', width=1.5), opacity=0.8
    ), row=2, col=1)
    
    fig_final.add_trace(go.Scattergl(
        x=time_axis, y=filt_B, name="Buffer B (Filt)",
        line=dict(color='#ff00ff', width=1.5), opacity=0.8
    ), row=2, col=1)

    # Plot Scatter
    fig_final.add_trace(go.Scattergl(
        x=filt_A, y=filt_B, mode='markers',
        marker=dict(size=3, color='cyan', opacity=0.5),
        name='Corr Points', showlegend=False
    ), row=2, col=2)

    # Garis Diagonal Scatter
    limit_val = max(np.max(np.abs(filt_A)), np.max(np.abs(filt_B)))
    fig_final.add_shape(type="line",
        x0=-limit_val, y0=-limit_val, x1=limit_val, y1=limit_val,
        line=dict(color="gray", dash="dash"),
        row=2, col=2
    )

    # Update Layout Global
    # Mengurangi margin (t, b, l, r) agar tabel tidak terpotong atau memunculkan scroll
    fig_final.update_layout(
        title_text=f"TEOAE Analysis Report | Overall: <b>{status_text}</b>",
        template="plotly_dark",
        height=800, 
        margin=dict(l=40, r=40, t=60, b=40), # Margin diperkecil
        hovermode="x unified"
    )

    # Label Axis
    fig_final.update_xaxes(title_text="Time (ms)", row=2, col=1)
    fig_final.update_yaxes(title_text="Amplitude", row=2, col=1)
    fig_final.update_xaxes(title_text="Amp Buffer A", row=2, col=2)
    fig_final.update_yaxes(title_text="Amp Buffer B", row=2, col=2)

    fig_final.show()

else:
    print("[ERROR] Mean A/B tidak ditemukan. Harap jalankan tahap Averaging sebelumnya.")