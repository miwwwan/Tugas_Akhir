import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import datetime
import os

# Import Matplotlib Backend untuk Tkinter
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Import modul (Pastikan modul_perekaman.py dan modul_analisis.py ada di folder yang sama)
import modul_perekaman1
import modul_analisis

class TEOAEApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TEOAE System Interface (Wireless Mode)")
        
        # Ukuran Widescreen agar grafik jelas
        self.root.geometry("1366x720") 
        
        # --- VARIABEL KONFIGURASI ---
        # Masukkan IP yang muncul di Serial Monitor ESP32 nanti
        self.ip_var = tk.StringVar(value="192.168.1.15") 
        self.port_tcp_var = tk.StringVar(value="8080")
        self.duration_var = tk.StringVar(value="40")
        self.filename_var = tk.StringVar(value=f"rekaman_{datetime.datetime.now().strftime('%H%M%S')}.csv")
        
        self.is_recording = False
        self.canvas = None # Variabel untuk menyimpan grafik
        
        self.setup_ui()
        
    def setup_ui(self):
        # === PANEL KIRI (Kontrol) ===
        left_panel = ttk.Frame(self.root, width=300)
        left_panel.pack(side="left", fill="y", padx=10, pady=10)
        
        # 1. Konfigurasi Wireless (Ganti dari Serial)
        config_frame = ttk.LabelFrame(left_panel, text="Konfigurasi Wireless (TCP)", padding=10)
        config_frame.pack(fill="x", pady=5)
        
        ttk.Label(config_frame, text="IP ESP32:").grid(row=0, column=0, sticky="w")
        ttk.Entry(config_frame, textvariable=self.ip_var, width=15).grid(row=0, column=1, sticky="e", padx=5)
        
        ttk.Label(config_frame, text="Port:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(config_frame, textvariable=self.port_tcp_var, width=15).grid(row=1, column=1, sticky="e", padx=5, pady=5)

        ttk.Label(config_frame, text="Durasi (s):").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(config_frame, textvariable=self.duration_var, width=15).grid(row=2, column=1, sticky="e", padx=5, pady=5)
        
        # 2. File Frame
        file_frame = ttk.LabelFrame(left_panel, text="Output File", padding=10)
        file_frame.pack(fill="x", pady=5)
        ttk.Label(file_frame, text="Nama File CSV:").pack(anchor="w")
        ttk.Entry(file_frame, textvariable=self.filename_var).pack(fill="x", pady=5)
        
        # 3. Tombol Aksi
        action_frame = ttk.Frame(left_panel)
        action_frame.pack(fill="x", pady=10)
        
        self.btn_record = ttk.Button(action_frame, text="1. MULAI REKAMAN (WIFI)", command=self.start_recording_thread)
        self.btn_record.pack(fill="x", pady=3)
        
        self.btn_analyze = ttk.Button(action_frame, text="2. ANALISIS DATA", command=self.start_analysis_thread)
        self.btn_analyze.pack(fill="x", pady=3)
        self.btn_analyze["state"] = "disabled"
        
        # 4. Log Area
        log_frame = ttk.LabelFrame(left_panel, text="Log Sistem", padding=10)
        log_frame.pack(fill="both", expand=True, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=10, state='disabled', font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True)
        
        # === PANEL KANAN (Visualisasi) ===
        right_panel = ttk.LabelFrame(self.root, text="Visualisasi Hasil Analisis", padding=5)
        right_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        self.plot_container = ttk.Frame(right_panel)
        self.plot_container.pack(fill="both", expand=True)
        
        self.lbl_placeholder = ttk.Label(self.plot_container, text="Grafik Analisis akan muncul di sini.", font=("Arial", 12))
        self.lbl_placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def log(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    # --- BAGIAN PEREKAMAN ---
    def start_recording_thread(self):
        if self.is_recording: return
        
        ip = self.ip_var.get()
        try: 
            duration = int(self.duration_var.get())
            port_tcp = int(self.port_tcp_var.get())
        except ValueError: 
            messagebox.showerror("Error", "IP/Port/Durasi tidak valid!")
            return
        
        filename = self.filename_var.get()
        if not filename.endswith(".csv"):
            filename += ".csv"
            self.filename_var.set(filename)
            
        self.is_recording = True
        self.btn_record.config(state="disabled")
        self.btn_analyze.config(state="disabled")
        
        # Jalankan di Thread terpisah agar GUI tidak beku
        t = threading.Thread(target=self.run_recording, args=(ip, port_tcp, duration, filename))
        t.daemon = True
        t.start()
        
    def run_recording(self, ip, port, duration, filename):
        self.log(f"Menghubungkan ke Server {ip}:{port}...")
        # Memanggil modul_perekaman versi WiFi
        success, saved_file = modul_perekaman1.rekam_data(ip, port, duration, filename, log_callback=self.log)
        
        self.is_recording = False
        self.root.after(0, lambda: self.finish_recording(success))

    def finish_recording(self, success):
        self.btn_record.config(state="normal")
        if success:
            self.btn_analyze.config(state="normal")
            messagebox.showinfo("Selesai", "Rekaman WiFi berhasil disimpan.")
        else:
            messagebox.showerror("Gagal", "Koneksi ke ESP32 gagal atau terputus.")

    # --- BAGIAN ANALISIS (TETAP SAMA) ---
    def start_analysis_thread(self):
        filename = self.filename_var.get()
        if not os.path.exists(filename):
            messagebox.showerror("Error", f"File {filename} tidak ditemukan!")
            return
        t = threading.Thread(target=self.run_analysis, args=(filename,))
        t.daemon = True
        t.start()
        
    def run_analysis(self, filename):
        self.log("Sedang menganalisis data (DSP)...")
        fig, status = modul_analisis.proses_data_oae(filename, log_callback=self.log)
        if fig is not None:
            self.root.after(0, lambda: self.display_results(fig, status))
        else:
            self.log("Analisis gagal.")

    def display_results(self, fig, status):
        self.log(f"Proses Selesai. Status: {status}")
        if self.lbl_placeholder:
            self.lbl_placeholder.destroy()
            self.lbl_placeholder = None
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
            
        self.canvas = FigureCanvasTkAgg(fig, master=self.plot_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam') 
    app = TEOAEApp(root)
    root.mainloop()