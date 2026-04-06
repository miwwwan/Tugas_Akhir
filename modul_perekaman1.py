import socket
import wave
import struct
import csv
import time

def rekam_data(ip_address, port, duration, output_filename, sample_rate=25000, log_callback=print):
    output_wav = output_filename.replace(".csv", ".wav")
    output_csv = output_filename

    try:
        log_callback(f"Menghubungkan ke ESP32 di {ip_address}:{port}...")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(10) # Timeout 10 detik
        client_socket.connect((ip_address, port))

        # --- KIRIM PERINTAH START ---
        log_callback("Mengirim perintah START...")
        client_socket.sendall(b'S')

        total_samples = int(sample_rate * duration)
        total_bytes = total_samples * 2  
        
        raw_data = bytearray()
        log_callback(f"Merekam {duration}s via WiFi... (Harap Tunggu)")

        # Membaca data secara streaming sampai durasi terpenuhi
        while len(raw_data) < total_bytes:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            raw_data.extend(chunk)

        # --- KIRIM PERINTAH STOP ---
        client_socket.sendall(b'E')
        client_socket.close()

        # --- 1. SIMPAN SEBAGAI WAV ---
        with wave.open(output_wav, "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(raw_data)
        
        log_callback(f"File WAV tersimpan: {output_wav}")

        # --- 2. KONVERSI KE CSV ---
        log_callback("Mengonversi ke CSV...")
        # Pastikan ukuran data sesuai untuk unpack
        actual_samples = len(raw_data) // 2
        samples = struct.unpack(f"<{actual_samples}h", raw_data[:actual_samples*2])

        with open(output_csv, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Sample_Index", "Amplitude"]) 
            for i, amplitude in enumerate(samples):
                writer.writerow([i, amplitude])

        log_callback(f"File CSV tersimpan: {output_csv}")
        return True, output_csv

    except Exception as e:
        log_callback(f"[ERROR WiFi] {e}")
        return False, None