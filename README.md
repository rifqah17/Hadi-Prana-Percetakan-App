# 🖨️ Sistem Antrian Digital — Hadi Prana Percetakan

Website antrian digital untuk UMKM Percetakan dan Fotocopy Hadi Prana.
Dibuat sebagai proyek solusi Transformasi Industri 4.0 oleh Kelompok 1 - 2B Analisis Kimia, Politeknik AKA Bogor.

---

## ✨ Fitur

| Fitur | Keterangan |
|---|---|
| Upload file print | Customer upload PDF/Word/JPG langsung dari HP |
| Nomor antrian otomatis | Diberikan setelah upload berhasil |
| Status antrian real-time | Customer bisa cek status kapan saja |
| Dashboard Pak Hadi | Kelola antrian, download file, update status |
| Notifikasi WA | Tombol kirim WA otomatis ke customer |
| QR Code | Cetak & tempel di kasir / kirim via WA |
| Template WA Business | Pesan balasan otomatis untuk WA Pak Hadi |

---

## 🚀 Cara Jalankan di Laptop (Lokal)

### 1. Install Python (jika belum)
Download dari https://python.org (Python 3.10 ke atas)

### 2. Install dependencies
Buka terminal / command prompt di folder ini, lalu ketik:
```bash
pip install -r requirements.txt
```

### 3. Jalankan app
```bash
streamlit run app.py
```

Website akan terbuka otomatis di browser: `http://localhost:8501`

---

## 🌐 Cara Deploy ke Internet (Streamlit Cloud) — GRATIS

Agar bisa diakses dari HP customer via QR Code:

1. **Buat akun** di https://streamlit.io (gratis, login pakai Google)
2. **Upload kode** ke GitHub:
   - Buat repo baru di https://github.com
   - Upload semua file (`app.py`, `requirements.txt`, `README.md`)
3. **Deploy:**
   - Masuk ke https://share.streamlit.io
   - Klik "New app" → pilih repo GitHub kamu
   - Klik "Deploy"
4. **Dapat URL** seperti `https://hadipranaprint.streamlit.app`
5. **Update QR Code** di dashboard admin dengan URL tersebut

---

## 📱 Setup WhatsApp Business Pak Hadi

1. Download **WhatsApp Business** (gratis di Play Store)
2. Daftarkan nomor WA Pak Hadi
3. Masuk ke **Pengaturan → Alat Bisnis → Pesan Otomatis**
4. Aktifkan **"Pesan Tidak Ada"** dan isi template:

```
Halo! 👋 Terima kasih sudah menghubungi Hadi Prana Percetakan.

Untuk pesan Print / Scan, silakan lanjut melalui website antrian kami:
🔗 [ISI URL WEBSITE KAMU DI SINI]

Upload file & ambil nomor antrian di sana.
Pak Hadi akan kirim notifikasi WA kalau dokumennya sudah selesai! ✅

Untuk Fotocopy, silakan datang langsung ke tempat. 📍
```

5. Aktifkan juga **Quick Reply** dengan shortcut `/order` untuk kirim link dengan cepat

---

## 🔐 Akses Dashboard Admin (Pak Hadi)

- URL: `[URL_WEBSITE]/?mode=admin`
- PIN default: `hadi1234`
- **Ganti PIN** di file `app.py` baris yang ada `"hadi1234"` sesuai keinginan

### Yang bisa dilakukan di dashboard:
- ✅ Lihat semua antrian hari ini
- ⬇️ Download file yang diupload customer
- ▶️ Tandai "Sedang Dikerjakan"
- ✅ Tandai "Selesai" + tombol kirim WA ke customer otomatis
- ❌ Batalkan pesanan
- 📱 Download QR Code untuk ditempel di kasir

---

## 🗂️ Struktur File

```
hadi_prana_app/
├── app.py              # Kode utama Streamlit
├── requirements.txt    # Daftar library yang dibutuhkan
├── README.md           # Panduan ini
├── antrian.db          # Database antrian (dibuat otomatis)
└── uploads/            # Folder file upload customer (dibuat otomatis)
```

---

## 👥 Tim Pengembang

Kelompok 1 - Kelas 2B Analisis Kimia  
Politeknik AKA Bogor, 2026  

- Affan Fakhri Izzudin
- Agung Suranenggala
- Debby Listy
- Nissa Nur Fitri
- Rifqah Nabilah
