import streamlit as st
import sqlite3
import os
import time
import qrcode
import io
import base64
from datetime import datetime
from PIL import Image

# ─── CONFIG ───────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Antrian Print - Hadi Prana",
    page_icon="🖨️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Batas upload 5 GB
MAX_UPLOAD_MB = 5120

DB_PATH = "antrian.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Ganti dengan link QRIS Pak Hadi (foto/gambar QRIS yang sudah di-upload ke Google Drive/Imgur dll)
QRIS_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/QR_code_for_mobile_English_Wikipedia.svg/480px-QR_code_for_mobile_English_Wikipedia.svg.png"
# ↑ Ganti URL di atas dengan URL foto QRIS Pak Hadi yang asli!

# ─── DATABASE ─────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS antrian (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomor_antrian INTEGER NOT NULL,
            nama_customer TEXT NOT NULL,
            nomor_wa TEXT NOT NULL,
            nama_file TEXT NOT NULL,
            path_file TEXT NOT NULL,
            jumlah_lembar INTEGER DEFAULT 1,
            jenis_layanan TEXT DEFAULT 'Print',
            pembayaran TEXT DEFAULT 'Cash',
            status TEXT DEFAULT 'Menunggu',
            catatan TEXT DEFAULT '',
            waktu_pesan TEXT NOT NULL,
            waktu_selesai TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

def get_next_nomor():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT MAX(nomor_antrian) FROM antrian WHERE date(waktu_pesan) = date('now', 'localtime')")
    result = c.fetchone()[0]
    conn.close()
    return (result or 0) + 1

def tambah_antrian(nama, wa, nama_file, path_file, lembar, jenis, bayar, catatan):
    nomor = get_next_nomor()
    waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO antrian (nomor_antrian, nama_customer, nomor_wa, nama_file, path_file,
                             jumlah_lembar, jenis_layanan, pembayaran, status, catatan, waktu_pesan)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Menunggu', ?, ?)
    """, (nomor, nama, wa, nama_file, path_file, lembar, jenis, bayar, catatan, waktu))
    conn.commit()
    conn.close()
    return nomor

def get_semua_antrian():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, nomor_antrian, nama_customer, nomor_wa, nama_file,
               jumlah_lembar, jenis_layanan, pembayaran, status, catatan, waktu_pesan, waktu_selesai
        FROM antrian
        WHERE date(waktu_pesan) = date('now', 'localtime')
        ORDER BY nomor_antrian ASC
    """)
    rows = c.fetchall()
    conn.close()
    return rows

def get_antrian_aktif():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT nomor_antrian, nama_customer, jenis_layanan, status
        FROM antrian
        WHERE status IN ('Menunggu', 'Dikerjakan')
        AND date(waktu_pesan) = date('now', 'localtime')
        ORDER BY nomor_antrian ASC
        LIMIT 5
    """)
    rows = c.fetchall()
    conn.close()
    return rows

def get_sedang_dikerjakan():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT nomor_antrian, nama_customer, jenis_layanan
        FROM antrian
        WHERE status = 'Dikerjakan'
        AND date(waktu_pesan) = date('now', 'localtime')
        ORDER BY nomor_antrian ASC
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    return row

def update_status(antrian_id, status_baru):
    waktu_selesai = ""
    if status_baru == "Selesai":
        waktu_selesai = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE antrian SET status = ?, waktu_selesai = ? WHERE id = ?",
              (status_baru, waktu_selesai, antrian_id))
    conn.commit()
    conn.close()

def get_antrian_by_nomor(nomor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, nomor_antrian, nama_customer, nama_file, jenis_layanan,
               pembayaran, status, waktu_pesan, waktu_selesai, jumlah_lembar
        FROM antrian
        WHERE nomor_antrian = ?
        AND date(waktu_pesan) = date('now', 'localtime')
        ORDER BY id DESC LIMIT 1
    """, (nomor,))
    row = c.fetchone()
    conn.close()
    return row

def get_statistik():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='Menunggu' THEN 1 ELSE 0 END) as menunggu,
            SUM(CASE WHEN status='Dikerjakan' THEN 1 ELSE 0 END) as dikerjakan,
            SUM(CASE WHEN status='Selesai' THEN 1 ELSE 0 END) as selesai
        FROM antrian
        WHERE date(waktu_pesan) = date('now', 'localtime')
    """)
    row = c.fetchone()
    conn.close()
    return row

# ─── QR CODE GENERATOR ────────────────────────────────────────────────────────
def generate_qr(url):
    qr = qrcode.QRCode(version=1, box_size=8, border=3,
                        error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def img_to_b64(buf):
    return base64.b64encode(buf.getvalue()).decode()

# ─── CUSTOM CSS ───────────────────────────────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');

    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }

    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        min-height: 100vh;
    }

    .brand-header { text-align: center; padding: 2rem 1rem 1rem; }
    .brand-title { font-size: 2rem; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; }
    .brand-subtitle { font-size: 0.85rem; color: #a0a0c0; letter-spacing: 2px; text-transform: uppercase; margin-top: 0.25rem; }

    .card {
        background: rgba(255,255,255,0.06);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .card-title {
        font-size: 0.75rem; font-weight: 700; letter-spacing: 2px;
        text-transform: uppercase; color: #8b8bab; margin-bottom: 0.75rem;
    }

    .now-serving {
        background: linear-gradient(135deg, #f7971e, #ffd200);
        border-radius: 16px; padding: 1.5rem; text-align: center; margin-bottom: 1rem;
    }
    .now-serving-label { font-size: 0.7rem; font-weight: 700; letter-spacing: 3px; color: rgba(0,0,0,0.6); text-transform: uppercase; }
    .now-serving-number { font-family: 'Space Mono', monospace; font-size: 5rem; font-weight: 700; color: #1a1a2e; line-height: 1; margin: 0.25rem 0; }
    .now-serving-name { font-size: 1rem; font-weight: 600; color: rgba(0,0,0,0.75); }

    .badge { display: inline-block; padding: 0.2rem 0.7rem; border-radius: 999px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.5px; }
    .badge-menunggu { background: rgba(251,191,36,0.2); color: #fbbf24; }
    .badge-dikerjakan { background: rgba(59,130,246,0.2); color: #60a5fa; }
    .badge-selesai { background: rgba(52,211,153,0.2); color: #34d399; }
    .badge-batal { background: rgba(248,113,113,0.2); color: #f87171; }

    .antrian-item {
        display: flex; align-items: center; justify-content: space-between;
        padding: 0.75rem 1rem; background: rgba(255,255,255,0.04);
        border-radius: 10px; margin-bottom: 0.5rem; border: 1px solid rgba(255,255,255,0.06);
    }
    .antrian-item-number { font-family: 'Space Mono', monospace; font-size: 1.25rem; font-weight: 700; color: #ffd200; min-width: 3rem; }
    .antrian-item-info { flex: 1; padding: 0 0.75rem; }
    .antrian-item-name { font-weight: 600; color: #e0e0f0; font-size: 0.9rem; }
    .antrian-item-type { font-size: 0.75rem; color: #8b8bab; }

    .ticket {
        background: linear-gradient(135deg, #1a1a2e, #302b63);
        border: 2px solid #ffd200; border-radius: 20px; padding: 2rem; text-align: center;
    }
    .ticket-number { font-family: 'Space Mono', monospace; font-size: 6rem; font-weight: 700; color: #ffd200; line-height: 1; }
    .ticket-label { font-size: 0.75rem; letter-spacing: 3px; color: #8b8bab; text-transform: uppercase; margin-bottom: 0.5rem; }

    /* QRIS Payment box */
    .qris-payment-box {
        background: rgba(255,255,255,0.07);
        border: 2px solid rgba(255,210,0,0.5);
        border-radius: 20px;
        padding: 1.5rem;
        text-align: center;
        margin-bottom: 1rem;
    }
    .qris-title {
        font-size: 1rem; font-weight: 800; color: #ffd200;
        letter-spacing: 1px; margin-bottom: 0.25rem;
    }
    .qris-sub {
        font-size: 0.78rem; color: #a0a0c0; margin-bottom: 1rem;
    }
    .qris-img {
        width: 200px; height: 200px; border-radius: 12px;
        border: 3px solid white; margin: 0 auto 1rem; display: block;
    }
    .qris-confirm-note {
        font-size: 0.8rem; color: #fbbf24; font-weight: 600; margin-top: 0.75rem;
    }

    .stat-box { background: rgba(255,255,255,0.06); border-radius: 12px; padding: 1rem; text-align: center; }
    .stat-num { font-family: 'Space Mono', monospace; font-size: 2rem; font-weight: 700; color: #ffd200; }
    .stat-label { font-size: 0.7rem; color: #8b8bab; letter-spacing: 1px; text-transform: uppercase; }

    .stButton > button {
        background: linear-gradient(135deg, #f7971e, #ffd200) !important;
        color: #1a1a2e !important; font-weight: 700 !important; border: none !important;
        border-radius: 10px !important; padding: 0.6rem 1.5rem !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.9rem !important; letter-spacing: 0.3px !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover { transform: translateY(-1px) !important; box-shadow: 0 8px 24px rgba(247,151,30,0.35) !important; }

    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div,
    .stTextArea > div > div > textarea {
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 10px !important; color: #ffffff !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    label, .stRadio label, .stSelectbox label {
        color: #c0c0d8 !important; font-size: 0.85rem !important; font-weight: 500 !important;
    }
    .stFileUploader > div {
        background: rgba(255,255,255,0.05) !important;
        border: 2px dashed rgba(255,210,0,0.3) !important;
        border-radius: 12px !important;
    }
    hr { border-color: rgba(255,255,255,0.1) !important; }
    .stTabs [data-baseweb="tab"] { color: #8b8bab !important; font-weight: 600 !important; }
    .stTabs [aria-selected="true"] { color: #ffd200 !important; border-bottom-color: #ffd200 !important; }
    div[data-testid="stForm"] {
        background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px; padding: 1.5rem;
    }
    .stSuccess { background: rgba(52,211,153,0.15) !important; border-radius: 10px !important; }
    .stError { background: rgba(248,113,113,0.15) !important; border-radius: 10px !important; }
    .stWarning { background: rgba(251,191,36,0.15) !important; border-radius: 10px !important; }
    .stInfo { background: rgba(96,165,250,0.15) !important; border-radius: 10px !important; }
    .block-container { padding-top: 1rem !important; }
    </style>
    """, unsafe_allow_html=True)

# ─── STATUS BADGE ─────────────────────────────────────────────────────────────
def status_badge(status):
    cls = {
        "Menunggu": "badge-menunggu",
        "Dikerjakan": "badge-dikerjakan",
        "Selesai": "badge-selesai",
        "Dibatalkan": "badge-batal",
    }.get(status, "badge-menunggu")
    return f'<span class="badge {cls}">{status}</span>'

# ─── TAMPILKAN TIKET ──────────────────────────────────────────────────────────
def tampilkan_tiket(nomor, nama, jenis, bayar):
    st.markdown(f"""
    <div class="ticket">
        <div class="ticket-label">🎫 Nomor Antrian Kamu</div>
        <div class="ticket-number">{nomor:02d}</div>
        <div style="color:#a0a0c0; font-size:0.85rem; margin-top:0.75rem;">
            {nama} · {jenis}<br>
            <span style="color:#ffd200; font-weight:700;">Pembayaran: {bayar}</span><br><br>
            <span style="color:#8b8bab;">Simpan nomor ini untuk cek status pesanan!</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─── HALAMAN CUSTOMER ─────────────────────────────────────────────────────────
def halaman_customer():
    st.markdown("""
    <div class="brand-header">
        <div class="brand-title">🖨️ Hadi Prana</div>
        <div class="brand-subtitle">Percetakan & Fotocopy · Tanah Baru, Bogor</div>
    </div>
    """, unsafe_allow_html=True)

    # Antrian sedang dikerjakan
    sedang = get_sedang_dikerjakan()
    if sedang:
        st.markdown(f"""
        <div class="now-serving">
            <div class="now-serving-label">⚡ Sedang Dikerjakan</div>
            <div class="now-serving-number">{sedang[0]:02d}</div>
            <div class="now-serving-name">{sedang[1]} · {sedang[2]}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="card" style="text-align:center; padding: 1rem;">
            <span style="color:#8b8bab; font-size:0.9rem;">Belum ada pesanan yang sedang dikerjakan</span>
        </div>
        """, unsafe_allow_html=True)

    # Daftar antrian menunggu
    antrian_list = get_antrian_aktif()
    menunggu = [a for a in antrian_list if a[3] == "Menunggu"]
    if menunggu:
        st.markdown('<div class="card"><div class="card-title">📋 Antrian Menunggu</div>', unsafe_allow_html=True)
        for a in menunggu:
            st.markdown(f"""
            <div class="antrian-item">
                <div class="antrian-item-number">{a[0]:02d}</div>
                <div class="antrian-item-info">
                    <div class="antrian-item-name">{a[1]}</div>
                    <div class="antrian-item-type">{a[2]}</div>
                </div>
                {status_badge(a[3])}
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

    tab1, tab2 = st.tabs(["📤 Pesan Print / Scan", "🔍 Cek Status Saya"])

    with tab1:
        # ── TAHAP QRIS: tampilkan QR bayar, tunggu konfirmasi, baru beri nomor antrian ──
        if st.session_state.get("tahap_qris"):
            data = st.session_state["pending_order"]
            st.markdown(f"""
            <div class="qris-payment-box">
                <div class="qris-title">💳 Pembayaran QRIS</div>
                <div class="qris-sub">Scan QR di bawah untuk membayar, lalu klik tombol konfirmasi</div>
                <img class="qris-img" src="{QRIS_IMAGE_URL}" alt="QRIS Hadi Prana" />
                <div style="font-size:0.85rem; color:#e0e0f0;">
                    <b>{data['nama']}</b> · {data['jenis']}<br>
                    <span style="color:#a0a0c0;">{data['lembar']} lembar</span>
                </div>
                <div class="qris-confirm-note">
                    ⚠️ Pastikan pembayaran sudah berhasil sebelum konfirmasi!
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_batal, col_konfirm = st.columns(2)
            with col_batal:
                if st.button("❌ Batalkan", use_container_width=True, key="batal_qris"):
                    st.session_state.pop("tahap_qris", None)
                    st.session_state.pop("pending_order", None)
                    st.rerun()
            with col_konfirm:
                if st.button("✅ Sudah Bayar, Ambil Nomor!", use_container_width=True, key="konfirm_qris"):
                    d = st.session_state["pending_order"]
                    nomor = tambah_antrian(
                        d["nama"], d["wa"], d["nama_file"], d["path_file"],
                        d["lembar"], d["jenis"], "QRIS", d["catatan"]
                    )
                    st.session_state["nomor_saya"] = nomor
                    st.session_state["nama_saya"] = d["nama"]
                    st.session_state.pop("tahap_qris", None)
                    st.session_state.pop("pending_order", None)
                    st.session_state["tiket_baru"] = {
                        "nomor": nomor, "nama": d["nama"],
                        "jenis": d["jenis"], "bayar": "QRIS"
                    }
                    st.rerun()

        # ── TAMPILKAN TIKET setelah konfirmasi (Cash atau QRIS) ──
        elif st.session_state.get("tiket_baru"):
            t = st.session_state["tiket_baru"]
            st.success(f"✅ Berhasil! Nomor antrian kamu: **{t['nomor']:02d}**")
            tampilkan_tiket(t["nomor"], t["nama"], t["jenis"], t["bayar"])
            st.markdown("""
            <div style="text-align:center; margin-top:1rem;">
                <span style="color:#8b8bab; font-size:0.8rem;">
                    Pak Hadi akan mengirim WA ketika dokumenmu selesai 📲
                </span>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔄 Pesan Lagi", use_container_width=True):
                st.session_state.pop("tiket_baru", None)
                st.rerun()

        # ── FORM PESAN ──
        else:
            st.markdown("##### Isi form di bawah untuk pesan antrian")
            with st.form("form_pesan", clear_on_submit=False):
                col1, col2 = st.columns(2)
                with col1:
                    nama = st.text_input("Nama Kamu *", placeholder="contoh: Budi")
                with col2:
                    wa = st.text_input("No. WhatsApp *", placeholder="contoh: 08123456789")

                jenis = st.selectbox("Jenis Layanan", [
                    "Print Hitam Putih", "Print Warna", "Scan Dokumen", "Lainnya"
                ])
                lembar = st.number_input("Jumlah Lembar / Halaman", min_value=1, max_value=9999, value=1)
                bayar = st.radio("Metode Pembayaran", ["Cash saat ambil", "QRIS"], horizontal=True)
                catatan = st.text_area("Catatan Tambahan (opsional)",
                                       placeholder="Ukuran kertas, warna, dll...", height=80)
                file = st.file_uploader(
                    f"Upload File * (maks {MAX_UPLOAD_MB // 1024} GB)",
                    type=["pdf", "doc", "docx", "jpg", "jpeg", "png", "xlsx", "pptx",
                          "ppt", "xls", "txt", "zip", "rar"]
                )

                submitted = st.form_submit_button("🚀 Ambil Nomor Antrian", use_container_width=True)

                if submitted:
                    if not nama.strip() or not wa.strip() or file is None:
                        st.error("⚠️ Nama, nomor WA, dan file wajib diisi!")
                    else:
                        # Cek ukuran file
                        file_bytes = file.getbuffer()
                        file_size_mb = len(file_bytes) / (1024 * 1024)
                        if file_size_mb > MAX_UPLOAD_MB:
                            st.error(f"⚠️ File terlalu besar! Maksimal {MAX_UPLOAD_MB // 1024} GB.")
                        else:
                            # Simpan file
                            safe_name = f"{int(time.time())}_{file.name}"
                            path = os.path.join(UPLOAD_DIR, safe_name)
                            with open(path, "wb") as f_out:
                                f_out.write(file_bytes)

                            if bayar == "QRIS":
                                # ── QRIS: simpan data sementara, tampilkan QR bayar dulu ──
                                st.session_state["tahap_qris"] = True
                                st.session_state["pending_order"] = {
                                    "nama": nama.strip(),
                                    "wa": wa.strip(),
                                    "nama_file": file.name,
                                    "path_file": path,
                                    "lembar": lembar,
                                    "jenis": jenis,
                                    "catatan": catatan,
                                }
                                st.rerun()
                            else:
                                # ── CASH: langsung masukkan ke antrian & tampilkan tiket ──
                                nomor = tambah_antrian(
                                    nama.strip(), wa.strip(), file.name, path,
                                    lembar, jenis, "Cash saat ambil", catatan
                                )
                                st.session_state["nomor_saya"] = nomor
                                st.session_state["nama_saya"] = nama.strip()
                                st.session_state["tiket_baru"] = {
                                    "nomor": nomor, "nama": nama.strip(),
                                    "jenis": jenis, "bayar": "Cash saat ambil"
                                }
                                st.rerun()

    with tab2:
        st.markdown("##### Masukkan nomor antrian kamu")
        nomor_cek = st.number_input("Nomor Antrian", min_value=1, max_value=999, step=1,
                                     value=st.session_state.get("nomor_saya", 1))
        if st.button("🔍 Cek Status", use_container_width=True):
            data = get_antrian_by_nomor(nomor_cek)
            if data:
                _, nomor, nama, nama_file, jenis, bayar, status, waktu_pesan, waktu_selesai, lembar = data
                warna = {"Menunggu": "#fbbf24", "Dikerjakan": "#60a5fa", "Selesai": "#34d399"}.get(status, "#fbbf24")

                st.markdown(f"""
                <div class="card">
                    <div style="text-align:center; margin-bottom:1rem;">
                        <div style="font-family:'Space Mono',monospace; font-size:3.5rem; font-weight:700; color:{warna}; line-height:1;">{nomor:02d}</div>
                        <div style="margin-top:0.5rem;">{status_badge(status)}</div>
                    </div>
                    <div style="display:grid; gap:0.5rem; font-size:0.85rem;">
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:#8b8bab;">Nama</span>
                            <span style="color:#e0e0f0; font-weight:600;">{nama}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:#8b8bab;">File</span>
                            <span style="color:#e0e0f0;">{nama_file}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:#8b8bab;">Layanan</span>
                            <span style="color:#e0e0f0;">{jenis} · {lembar} lembar</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:#8b8bab;">Pembayaran</span>
                            <span style="color:#e0e0f0;">{bayar}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:#8b8bab;">Waktu Pesan</span>
                            <span style="color:#e0e0f0;">{waktu_pesan[11:16]}</span>
                        </div>
                        {"<div style='display:flex; justify-content:space-between;'><span style='color:#8b8bab;'>Selesai</span><span style='color:#34d399; font-weight:700;'>" + waktu_selesai[11:16] + "</span></div>" if waktu_selesai else ""}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if status == "Selesai":
                    st.success("✅ Dokumen kamu sudah selesai! Silakan ambil di kasir Pak Hadi.")
                elif status == "Dikerjakan":
                    st.info("⚡ Dokumen kamu sedang dikerjakan oleh Pak Hadi!")
                else:
                    semua = get_antrian_aktif()
                    pos = next((i+1 for i, a in enumerate(semua) if a[0] == nomor), None)
                    if pos:
                        st.warning(f"⏳ Posisi kamu saat ini: **nomor {pos} dalam antrian**. Harap sabar ya!")
            else:
                st.error("❌ Nomor antrian tidak ditemukan untuk hari ini.")

        st.markdown("""
        <div style="text-align:center; margin-top:1.5rem; font-size:0.78rem; color:#8b8bab;">
            Pak Hadi akan mengirim pesan WA ketika dokumenmu selesai 📲
        </div>
        """, unsafe_allow_html=True)

# ─── HALAMAN ADMIN ────────────────────────────────────────────────────────────
def halaman_admin():
    st.markdown("""
    <div class="brand-header">
        <div class="brand-title">⚙️ Dashboard Pak Hadi</div>
        <div class="brand-subtitle">Kelola Antrian · Hadi Prana</div>
    </div>
    """, unsafe_allow_html=True)

    stats = get_statistik()
    if stats and stats[0]:
        total, menunggu, dikerjakan, selesai = stats
        c1, c2, c3, c4 = st.columns(4)
        for col, val, label in zip(
            [c1, c2, c3, c4],
            [total, menunggu, dikerjakan, selesai],
            ["Total", "Menunggu", "Dikerjakan", "Selesai"]
        ):
            with col:
                st.markdown(f"""
                <div class="stat-box">
                    <div class="stat-num">{val or 0}</div>
                    <div class="stat-label">{label}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("")

    tab_antrian, tab_qr = st.tabs(["📋 Kelola Antrian", "📱 QR Code & Info WA"])

    with tab_antrian:
        if st.button("🔄 Refresh", use_container_width=False):
            st.rerun()
        semua = get_semua_antrian()
        if not semua:
            st.info("Belum ada pesanan masuk hari ini.")
        else:
            for row in semua:
                rid, nomor, nama, wa, nama_file, lembar, jenis, bayar, status, catatan, waktu, selesai = row
                with st.expander(f"#{nomor:02d} · {nama} · {jenis} · {status}", expanded=(status == "Menunggu")):
                    col_info, col_aksi = st.columns([2, 1])
                    with col_info:
                        st.markdown(f"""
                        <div style="font-size:0.85rem; color:#c0c0d8; line-height:2;">
                            📁 <b>File:</b> {nama_file}<br>
                            📞 <b>WA:</b> {wa}<br>
                            🖨️ <b>Lembar:</b> {lembar}<br>
                            💳 <b>Bayar:</b> {bayar}<br>
                            🕐 <b>Pesan:</b> {waktu[11:16]}<br>
                            {"💬 <b>Catatan:</b> " + catatan if catatan else ""}
                        </div>
                        """, unsafe_allow_html=True)

                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("SELECT path_file FROM antrian WHERE id=?", (rid,))
                        pf = c.fetchone()
                        conn.close()
                        if pf and os.path.exists(pf[0]):
                            with open(pf[0], "rb") as f:
                                st.download_button(
                                    f"⬇️ Download {nama_file}",
                                    f.read(),
                                    file_name=nama_file,
                                    key=f"dl_{rid}"
                                )

                    with col_aksi:
                        st.markdown(f"**Status:** {status_badge(status)}", unsafe_allow_html=True)
                        st.markdown("")
                        if status == "Menunggu":
                            if st.button("▶️ Kerjakan", key=f"kerja_{rid}", use_container_width=True):
                                update_status(rid, "Dikerjakan")
                                st.rerun()
                        if status == "Dikerjakan":
                            if st.button("✅ Selesai", key=f"selesai_{rid}", use_container_width=True):
                                update_status(rid, "Selesai")
                                wa_clean = wa.replace("-", "").replace(" ", "")
                                if not wa_clean.startswith("62"):
                                    wa_clean = "62" + wa_clean.lstrip("0")
                                pesan = f"Halo {nama}! 👋%0APesanan kamu ({jenis}) sudah selesai dikerjakan.%0ASilakan ambil di tempat Pak Hadi ya! 🙏%0A%0ATerima kasih sudah percaya pada Hadi Prana Percetakan ✨"
                                link_wa = f"https://wa.me/{wa_clean}?text={pesan}"
                                st.success(f"Tandai selesai! Kirim notifikasi ke {nama}:")
                                st.markdown(f'<a href="{link_wa}" target="_blank"><button style="width:100%; background:linear-gradient(135deg,#25D366,#128C7E); color:white; border:none; border-radius:10px; padding:0.5rem 1rem; font-weight:700; cursor:pointer; margin-top:0.5rem;">📲 Kirim WA ke {nama}</button></a>', unsafe_allow_html=True)
                                st.rerun()
                        if status not in ["Selesai", "Dibatalkan"]:
                            if st.button("❌ Batalkan", key=f"batal_{rid}", use_container_width=True):
                                update_status(rid, "Dibatalkan")
                                st.rerun()

    with tab_qr:
        st.markdown("#### 📱 QR Code untuk Ditempel di Kasir")
        url_input = st.text_input(
            "URL Website",
            value="https://hadipranaprint.streamlit.app",
        )
        if url_input:
            qr_buf = generate_qr(url_input)
            b64 = img_to_b64(qr_buf)
            st.markdown(f"""
            <div style="text-align:center; margin: 1.5rem 0;">
                <div style="display:inline-block; background:white; padding:1.5rem; border-radius:16px; box-shadow: 0 8px 32px rgba(255,210,0,0.3);">
                    <img src="data:image/png;base64,{b64}" style="width:220px; height:220px;" />
                    <div style="margin-top:0.75rem; font-size:0.75rem; color:#302b63; font-weight:700; letter-spacing:1px;">SCAN UNTUK ORDER PRINT</div>
                    <div style="font-size:0.65rem; color:#8b8bab; margin-top:0.25rem;">Hadi Prana · Tanah Baru, Bogor</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.download_button("⬇️ Download QR Code (PNG)", qr_buf.getvalue(),
                               file_name="qr_hadiPrana.png", mime="image/png", use_container_width=True)

        st.markdown("---")
        st.markdown("#### 🖼️ URL Gambar QRIS Pak Hadi")
        st.info("Ganti URL QRIS_IMAGE_URL di baris 28 file app.py dengan link foto QRIS Pak Hadi yang sudah diupload ke internet (Google Drive publik, Imgur, dll).")
        st.code(f'QRIS_IMAGE_URL = "{QRIS_IMAGE_URL}"', language="python")

        st.markdown("---")
        st.markdown("#### 💬 Template WA Business")
        st.markdown("""
        <div class="card">
            <div class="card-title">Away Message / Quick Reply</div>
            <div style="background:rgba(37,211,102,0.1); border:1px solid rgba(37,211,102,0.3); border-radius:10px; padding:1rem; font-size:0.85rem; color:#c0c0d8; line-height:1.8; font-family:monospace;">
            Halo! 👋 Terima kasih sudah menghubungi Hadi Prana Percetakan.<br><br>
            Untuk pesan <b>Print / Scan</b>, silakan lanjut melalui website antrian kami:<br>
            🔗 <span style="color:#ffd200;">[URL WEBSITE]</span><br><br>
            Upload file & ambil nomor antrian di sana. ✅<br>
            Pak Hadi akan kirim notifikasi WA kalau dokumennya sudah selesai! 📲<br><br>
            Untuk <b>Fotocopy</b>, silakan datang langsung ke tempat. 📍
            </div>
        </div>
        """, unsafe_allow_html=True)

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    init_db()
    inject_css()

    params = st.query_params
    mode = params.get("mode", "customer")

    if mode == "admin":
        if "admin_ok" not in st.session_state:
            st.markdown('<div class="brand-header"><div class="brand-title">🔐 Login Admin</div></div>', unsafe_allow_html=True)
            pin = st.text_input("Masukkan PIN Admin", type="password")
            if st.button("Masuk"):
                if pin == "hadi1234":
                    st.session_state["admin_ok"] = True
                    st.rerun()
                else:
                    st.error("PIN salah!")
            st.markdown('<div style="text-align:center; margin-top:1rem; font-size:0.78rem; color:#8b8bab;">Akses khusus Pak Hadi</div>', unsafe_allow_html=True)
        else:
            halaman_admin()
            if st.sidebar.button("🚪 Logout"):
                del st.session_state["admin_ok"]
                st.rerun()
    else:
        halaman_customer()
        st.markdown("""
        <div style="text-align:center; margin-top:2rem; font-size:0.72rem; color:#8b8bab;">
            Status antrian diperbarui otomatis · Hadi Prana © 2026
        </div>
        """, unsafe_allow_html=True)
        time.sleep(30)
        st.rerun()

if __name__ == "__main__":
    main()
