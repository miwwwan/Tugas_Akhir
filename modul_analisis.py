import pandas as pd
import numpy as np
from scipy.signal import butter, sosfilt, find_peaks, windows, stft, istft
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib import gridspec

# --- FUNGSI BANTUAN FILTER (Sama persis dengan kode asli) ---
def butter_bandpass_filter(data, lowcut, highcut, fs, order=1):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    sos = butter(order, [low, high], btype='band', analog=False, output='sos')
    y = sosfilt(sos, data)
    return y

def apply_time_freq_filter(signal_data, fs, multiplier=3.0, alpha=2.663, beta=-0.8):
    # Parameter STFT sama persis
    N_PERSEG = 128  
    HOP_SIZE = 10 
    N_OVERLAP = N_PERSEG - HOP_SIZE 

    f, t, Zxx = stft(signal_data, fs, window='hamming', nperseg=N_PERSEG, noverlap=N_OVERLAP)
    mask = np.zeros_like(Zxx, dtype=float)
    
    for i, freq in enumerate(f):
        if freq == 0:
            limit_time = 100 
        else:
            # Rumus latensi sama persis
            limit_time = multiplier * (alpha * 1e-3) * ((freq/1000.0 + 1e-9)**beta)
        mask[i, :] = np.where(t < limit_time, 1.0, 0.0)
    
    Zxx_filtered = Zxx * mask
    _, signal_filtered = istft(Zxx_filtered, fs, window='hamming', nperseg=N_PERSEG, noverlap=N_OVERLAP)
    
    # Padding/Trimming
    if len(signal_filtered) > len(signal_data):
        signal_filtered = signal_filtered[:len(signal_data)]
    elif len(signal_filtered) < len(signal_data):
        signal_filtered = np.pad(signal_filtered, (0, len(signal_data) - len(signal_filtered)))
        
    return signal_filtered

def proses_data_oae(file_path, log_callback=print):
    """
    Logika proses ini disalin PERSIS dari 'Pengolahan Data.py' asli.
    Hanya bagian print diganti log_callback dan plot diganti return Figure.
    """
    # --- KONFIGURASI ---
    SAMPLE_RATE = 25000
    LOW_CUTOFF = 500.0
    HIGH_CUTOFF = 12000.0
    START_TIME = 0
    END_TIME = 40

    log_callback(f"--- Membuka File: {file_path} ---")
    try:
        df = pd.read_csv(file_path)
        raw_data_full = df['Amplitude'].values
    except Exception as e:
        log_callback(f"[ERROR] {e}")
        return None, None

    start_idx = int(START_TIME * SAMPLE_RATE)
    end_idx = int(END_TIME * SAMPLE_RATE)
    
    # Pastikan slicing aman
    if end_idx > len(raw_data_full):
        end_idx = len(raw_data_full)
        
    raw_data = raw_data_full[start_idx:end_idx]
    
    # --- PROSES CLEANING ---
    data_centered = raw_data - np.mean(raw_data)
    clean_data = butter_bandpass_filter(data_centered, LOW_CUTOFF, HIGH_CUTOFF, SAMPLE_RATE, order=4)

    # --- PEAK DETECTION ---
    signal_abs = np.abs(clean_data)
    max_amp = np.max(signal_abs)
    threshold_val = 0.20 * max_amp 
    min_distance_samples = int(0.01 * SAMPLE_RATE)

    peaks_indices, _ = find_peaks(signal_abs, height=threshold_val, distance=min_distance_samples)
    log_callback(f"Ditemukan {len(peaks_indices)} klik.")

    # --- EPOCHING ---
    EPOCH_DURATION_MS = 20  
    EPOCH_SAMPLES = int((EPOCH_DURATION_MS / 1000) * SAMPLE_RATE)
    epochs = []
    
    for idx in peaks_indices:
        if idx + EPOCH_SAMPLES <= len(clean_data):
            segment = clean_data[idx : idx + EPOCH_SAMPLES]
            epochs.append(segment)

    if not epochs:
        log_callback("Tidak ada epoch valid.")
        return None, None

    epochs_matrix = np.array(epochs)

    # --- SETUP WINDOWING TUKEY ---
    SAFE_END_MS = 19.5 
    safe_idx = int((SAFE_END_MS / 1000) * SAMPLE_RATE)
    ECHO_REMOVE_MS = 4
    echo_remove_idx = int((ECHO_REMOVE_MS / 1000) * SAMPLE_RATE)
    
    DISCARD_START_MS = 1.92
    DISCARD_END_MS = 1.28
    SMOOTHING_MS = 2.56
    
    n_total = EPOCH_SAMPLES
    idx_start_valid = int((DISCARD_START_MS / 1000) * SAMPLE_RATE)
    idx_end_valid = n_total - int((DISCARD_END_MS / 1000) * SAMPLE_RATE)
    n_taper = int((SMOOTHING_MS / 1000) * SAMPLE_RATE)

    custom_window = np.zeros(n_total)
    idx_flat_start = idx_start_valid + n_taper
    idx_flat_end = idx_end_valid - n_taper

    if idx_flat_start < idx_flat_end:
        taper_up = np.sin(np.linspace(0, np.pi/2, n_taper))**2
        custom_window[idx_start_valid : idx_flat_start] = taper_up
        custom_window[idx_flat_start : idx_flat_end] = 1.0
        taper_down = np.cos(np.linspace(0, np.pi/2, n_taper))**2
        custom_window[idx_flat_end : idx_end_valid] = taper_down
    else:
        custom_window[idx_start_valid:idx_end_valid] = 1.0

    # --- PERSIAPAN DATA ---
    CLICKS_PER_BLOCK = 8
    num_epochs = len(epochs_matrix)
    num_blocks = num_epochs // CLICKS_PER_BLOCK
    valid_length = num_blocks * CLICKS_PER_BLOCK
    epochs_processed = epochs_matrix[:valid_length].copy()

    # Safety Cut
    epochs_processed[:, safe_idx:] = 0
    
    # Auto Threshold
    check_start = int((4.0/1000) * SAMPLE_RATE)
    check_end = int((15.0/1000) * SAMPLE_RATE)
    valid_segments = epochs_processed[:, check_start:check_end]
    noise_ref = np.std(valid_segments)
    REJECTION_THRESHOLD = 3.0 * noise_ref 

    # --- PROCESSING LOOP (BALANCED) ---
    buffer_A_new = []
    buffer_B_new = []
    buffer_Noise_new = []
    valid_counter = 0

    for i in range(num_blocks):
        start_idx = i * CLICKS_PER_BLOCK
        block_epochs = epochs_processed[start_idx : start_idx + CLICKS_PER_BLOCK]
        
        # Hitung Signal (Eq 2)
        sweep_1 = np.sum(block_epochs[0:4], axis=0)
        sweep_2 = np.sum(block_epochs[4:8], axis=0)
        signal_trial = (sweep_1 - sweep_2) / 8.0 
        
        # Hitung Noise (Eq 3)
        noise_trial = np.sum(block_epochs, axis=0) / 8.0 
        
        # Pre-Processing
        signal_trial[:echo_remove_idx] = 0
        noise_trial[:echo_remove_idx] = 0
        
        # Artifact Rejection
        check_segment = signal_trial[idx_start_valid : idx_end_valid]
        
        if np.max(np.abs(check_segment)) <= REJECTION_THRESHOLD:
            # Windowing
            signal_weighted = signal_trial * custom_window
            noise_weighted = noise_trial * custom_window
            
            # Balanced Split
            if valid_counter % 2 == 0:
                buffer_A_new.append(signal_weighted)
            else:
                buffer_B_new.append(signal_weighted)
            
            buffer_Noise_new.append(noise_weighted)
            valid_counter += 1

    log_callback(f"Sweeps Diterima: {valid_counter}/{num_blocks}")

    if len(buffer_A_new) == 0 or len(buffer_B_new) == 0:
        log_callback("[ERROR] Data habis setelah rejection.")
        return None, None

    # Mean Calculation
    mean_A = np.mean(buffer_A_new, axis=0)
    mean_B = np.mean(buffer_B_new, axis=0)
    mean_Noise_Eq3 = np.mean(buffer_Noise_new, axis=0)

    # Time-Frequency Filter
    filt_A = apply_time_freq_filter(mean_A, SAMPLE_RATE)
    filt_B = apply_time_freq_filter(mean_B, SAMPLE_RATE)
    filt_Noise = apply_time_freq_filter(mean_Noise_Eq3, SAMPLE_RATE)

    # Final Signal
    signal_final = (filt_A + filt_B) / 2
    noise_final = filt_Noise

    # --- SNR Calculation ---
    n_fft = len(signal_final)
    # Gunakan rfftfreq agar sesuai Plotly code sebelumnya
    freqs_fft = np.fft.rfftfreq(n_fft, 1/SAMPLE_RATE) 
    fft_window = windows.hann(n_fft)

    fft_signal = np.abs(np.fft.rfft(signal_final * fft_window))
    fft_noise = np.abs(np.fft.rfft(noise_final * fft_window))

    mag_signal_db = 20 * np.log10(fft_signal + 1e-12)
    mag_noise_db = 20 * np.log10(fft_noise + 1e-12)

    # --- WWR Calculation ---
    corr_matrix = np.corrcoef(filt_A, filt_B)
    wwr_score = corr_matrix[0, 1] * 100 

    # --- TABLE PREPARATION ---
    FREQ_BANDS = [1000, 1500, 2000, 3000, 4000] 
    BAND_WIDTH = 150
    
    table_data = []
    overall_pass = 0
    
    for f_center in FREQ_BANDS:
        idx_band = np.where((freqs_fft >= f_center - BAND_WIDTH) & (freqs_fft <= f_center + BAND_WIDTH))[0]
        
        if len(idx_band) > 0:
            p_signal = np.mean(mag_signal_db[idx_band])
            p_noise = np.mean(mag_noise_db[idx_band])
            snr = p_signal - p_noise
            
            status = "PASS" if snr >= 6.0 else "REFER"
            if snr >= 6.0: overall_pass += 1
            
            table_data.append([f"{f_center}", f"{p_signal:.2f}", f"{p_noise:.2f}", f"{snr:.2f}", status])
        else:
            table_data.append([f"{f_center}", "N/A", "N/A", "N/A", "N/A"])

    final_status = "PASS" if (overall_pass >= 3 and wwr_score >= 70.0) else "REFER"
    status_color = "#32CD32" if final_status == "PASS" else "#FF6347" # LimeGreen vs Tomato

    # --- VISUALISASI MATPLOTLIB ---
    # Setup Figure
    fig = Figure(figsize=(10, 8), dpi=100)
    fig.patch.set_facecolor('#f0f0f0') # Background abu-abu muda biar rapi
    fig.suptitle(f"TEOAE Analysis: {final_status} (WWR: {wwr_score:.1f}%)", 
                 fontsize=16, fontweight='bold', color=status_color, y=0.95)
    
    gs = gridspec.GridSpec(2, 2, height_ratios=[1, 2], hspace=0.3)
    
    # 1. Tabel Hasil
    ax_table = fig.add_subplot(gs[0, :])
    ax_table.axis('off')
    col_labels = ["Freq (Hz)", "Signal (dB)", "Noise (dB)", "SNR (dB)", "Status"]
    
    the_table = ax_table.table(cellText=table_data, colLabels=col_labels, loc='center', cellLoc='center')
    the_table.auto_set_font_size(False)
    the_table.set_fontsize(10)
    the_table.scale(1, 1.8)
    
    # Coloring Table Cells
    for i, row in enumerate(table_data):
        # Header Color
        for j in range(5):
            the_table[(0, j)].set_facecolor('#404040')
            the_table[(0, j)].set_text_props(color='white', weight='bold')
            
        # Status Cell Color
        cell_status = the_table[(i+1, 4)]
        if row[4] == "PASS":
            cell_status.set_facecolor('#90EE90') # Light Green
        elif row[4] == "REFER":
            cell_status.set_facecolor('#FFB6C1') # Light Pink

    # 2. Waveform Overlay
    ax_wave = fig.add_subplot(gs[1, 0])
    time_axis = np.linspace(0, EPOCH_DURATION_MS, len(filt_A))
    
    ax_wave.plot(time_axis, filt_A, label="Buffer A", color='green', alpha=0.8, linewidth=1.5)
    ax_wave.plot(time_axis, filt_B, label="Buffer B", color='magenta', alpha=0.8, linewidth=1.5)
    ax_wave.set_title("Waveform Overlay")
    ax_wave.set_xlabel("Time (ms)")
    ax_wave.set_ylabel("Amplitude")
    ax_wave.legend(loc='upper right')
    ax_wave.grid(True, linestyle='--', alpha=0.5)

    # 3. Scatter Correlation
    ax_scatter = fig.add_subplot(gs[1, 1])
    ax_scatter.scatter(filt_A, filt_B, s=10, c='cyan', edgecolors='black', linewidth=0.5, alpha=0.6)
    
    # Diagonal Line
    limit_val = max(np.max(np.abs(filt_A)), np.max(np.abs(filt_B))) * 1.1
    ax_scatter.plot([-limit_val, limit_val], [-limit_val, limit_val], 'k--', alpha=0.5)
    ax_scatter.set_xlim(-limit_val, limit_val)
    ax_scatter.set_ylim(-limit_val, limit_val)
    
    ax_scatter.set_title(f"Correlation (WWR: {wwr_score:.1f}%)")
    ax_scatter.set_xlabel("Amplitude A")
    ax_scatter.set_ylabel("Amplitude B")
    ax_scatter.grid(True, linestyle='--', alpha=0.5)
    
    return fig, final_status