import serial
import wave
import struct
import csv
import time

def rekam_data(port, baudrate, duration, output_filename, sample_rate=25000, log_callback=print):
    """
    Fungsi untuk merekam data dari ESP32.
    log_callback: fungsi untuk mengirim text status ke GUI
    """
    output_wav = output_filename.replace(".csv", ".wav")
    output_csv = output_filename

    try:
        # Inisialisasi Serial
        log_callback(f"Membuka port {port}...")
        ser = serial.Serial(port, baudrate)

        log_callback("Menunggu ESP32 siap (2 detik)...")
        time.sleep(2) 

        ser.reset_input_buffer()

        # --- KIRIM PERINTAH START ---
        log_callback("Mengirim perintah START ke ESP32...")
        ser.write(b'S') 

        total_samples = int(sample_rate * duration)
        total_bytes = total_samples * 2  # 16-bit
        
        log_callback(f"Merekam selama {duration} detik... (Harap Tunggu)")

        # Membaca data (Blocking)
        raw = ser.read(total_bytes)

        # --- KIRIM PERINTAH STOP ---
        log_callback("Selesai mengambil data. Mengirim perintah STOP...")
        ser.write(b'E') 
        ser.close()

        # --- 1. SIMPAN SEBAGAI WAV ---
        with wave.open(output_wav, "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(raw)
        
        log_callback(f"File WAV tersimpan: {output_wav}")

        # --- 2. KONVERSI KE CSV ---
        log_callback("Mengonversi ke CSV...")
        samples = struct.unpack(f"<{total_samples}h", raw)

        with open(output_csv, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Sample_Index", "Amplitude"]) 
            
            for i, amplitude in enumerate(samples):
                writer.writerow([i, amplitude])

        log_callback(f"File CSV tersimpan: {output_csv}")
        return True, output_csv

    except Exception as e:
        log_callback(f"[ERROR Perekaman] {e}")
        return False, None