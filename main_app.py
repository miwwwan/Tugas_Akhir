import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import datetime
import os

# Import Matplotlib Backend untuk Tkinter
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Import modul kita (Pastikan modul_perekaman.py dan modul_analisis.py ada di folder yang sama)
import modul_perekaman
import modul_analisis

class TEOAEApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TEOAE System Interface (Integrated)")
        
        # --- MODIFIKASI UKURAN WINDOW ---
        # Mengubah ukuran menjadi lebih lebar (Widescreen) agar grafik jelas
        self.root.geometry("1366x720") 
        
        # Variabel Default
        self.port_var = tk.StringVar(value="COM8")
        self.duration_var = tk.StringVar(value="40")
        self.filename_var = tk.StringVar(value=f"rekaman_{datetime.datetime.now().strftime('%H%M%S')}.csv")
        
        self.is_recording = False
        self.canvas = None # Variabel untuk menyimpan grafik
        
        self.setup_ui()
        
    def setup_ui(self):
        # === PANEL KIRI (Kontrol) ===
        # Width diset agar tidak terlalu lebar, menyisakan ruang untuk grafik
        left_panel = ttk.Frame(self.root, width=300)
        left_panel.pack(side="left", fill="y", padx=10, pady=10)
        
        # 1. Konfigurasi Frame
        config_frame = ttk.LabelFrame(left_panel, text="Konfigurasi Hardware", padding=10)
        config_frame.pack(fill="x", pady=5)
        
        ttk.Label(config_frame, text="COM Port:").grid(row=0, column=0, sticky="w")
        ttk.Entry(config_frame, textvariable=self.port_var, width=15).grid(row=0, column=1, sticky="e", padx=5)
        
        ttk.Label(config_frame, text="Durasi (s):").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(config_frame, textvariable=self.duration_var, width=15).grid(row=1, column=1, sticky="e", padx=5, pady=5)
        
        # 2. File Frame
        file_frame = ttk.LabelFrame(left_panel, text="Output File", padding=10)
        file_frame.pack(fill="x", pady=5)
        ttk.Label(file_frame, text="Nama File CSV:").pack(anchor="w")
        ttk.Entry(file_frame, textvariable=self.filename_var).pack(fill="x", pady=5)
        
        # 3. Tombol Aksi
        action_frame = ttk.Frame(left_panel)
        action_frame.pack(fill="x", pady=10)
        
        self.btn_record = ttk.Button(action_frame, text="1. MULAI REKAMAN", command=self.start_recording_thread)
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
        # Menggunakan expand=True agar mengambil sisa ruang yang tersedia
        right_panel = ttk.LabelFrame(self.root, text="Visualisasi Hasil Analisis", padding=5)
        right_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        # Container untuk Grafik
        self.plot_container = ttk.Frame(right_panel)
        self.plot_container.pack(fill="both", expand=True)
        
        # Label Placeholder (Tampil sebelum ada grafik)
        self.lbl_placeholder = ttk.Label(self.plot_container, text="Grafik Analisis akan muncul di sini.", font=("Arial", 12))
        self.lbl_placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def log(self, message):
        """Menampilkan pesan log dengan timestamp"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    # --- BAGIAN PEREKAMAN ---
    def start_recording_thread(self):
        if self.is_recording: return
        
        port = self.port_var.get()
        try: 
            duration = int(self.duration_var.get())
        except ValueError: 
            messagebox.showerror("Error", "Durasi harus angka!")
            return
        
        filename = self.filename_var.get()
        if not filename.endswith(".csv"):
            filename += ".csv"
            self.filename_var.set(filename)
            
        self.is_recording = True
        self.btn_record.config(state="disabled")
        self.btn_analyze.config(state="disabled")
        
        # Jalankan di Thread terpisah
        t = threading.Thread(target=self.run_recording, args=(port, duration, filename))
        t.daemon = True
        t.start()
        
    def run_recording(self, port, duration, filename):
        self.log(f"Menghubungkan ke {port}...")
        # Panggil fungsi dari modul_perekaman.py
        success, saved_file = modul_perekaman.rekam_data(port, 921600, duration, filename, log_callback=self.log)
        
        self.is_recording = False
        self.root.after(0, lambda: self.finish_recording(success))

    def finish_recording(self, success):
        self.btn_record.config(state="normal")
        if success:
            self.btn_analyze.config(state="normal")
            messagebox.showinfo("Selesai", "Rekaman berhasil disimpan. Silakan lanjut ke Analisis.")
        else:
            messagebox.showerror("Gagal", "Terjadi kesalahan saat merekam.")

    # --- BAGIAN ANALISIS ---
    def start_analysis_thread(self):
        filename = self.filename_var.get()
        if not os.path.exists(filename):
            messagebox.showerror("Error", f"File {filename} tidak ditemukan!")
            return
            
        # Jalankan di Thread terpisah
        t = threading.Thread(target=self.run_analysis, args=(filename,))
        t.daemon = True
        t.start()
        
    def run_analysis(self, filename):
        self.log("Sedang menganalisis data (DSP)...")
        
        # Panggil fungsi dari modul_analisis.py (Versi Matplotlib)
        # Fungsi ini mengembalikan object Figure (gambar) dan Status Text
        fig, status = modul_analisis.proses_data_oae(filename, log_callback=self.log)
        
        if fig is not None:
            self.root.after(0, lambda: self.display_results(fig, status))
        else:
            self.log("Analisis gagal atau tidak valid.")

    def display_results(self, fig, status):
        self.log(f"Proses Selesai. Status Diagnostik: {status}")
        
        # Hapus placeholder teks jika ada
        if self.lbl_placeholder:
            self.lbl_placeholder.destroy()
            self.lbl_placeholder = None
            
        # Hapus canvas grafik lama jika ada
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
            
        # Tempelkan grafik Matplotlib ke dalam Tkinter Frame
        self.canvas = FigureCanvasTkAgg(fig, master=self.plot_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

if __name__ == "__main__":
    root = tk.Tk()
    # Style agar tampilan lebih modern
    style = ttk.Style()
    style.theme_use('clam') 
    
    app = TEOAEApp(root)
    root.mainloop()