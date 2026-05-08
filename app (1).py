import streamlit as st
import sqlite3
import os
import time
import qrcode
import io
import base64
from datetime import datetime
 
# ─── CONFIG ───────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Antrian Print - Hadi Prana",
    page_icon="🖨️",
    layout="centered",
    initial_sidebar_state="collapsed",
)
 
DB_PATH        = "antrian.db"
UPLOAD_DIR     = "uploads"
MAX_UPLOAD_MB  = 5120          # 5 GB
ADMIN_PIN      = "hadi1234"
os.makedirs(UPLOAD_DIR, exist_ok=True)
 
# ─── DATABASE ─────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
 
    # Tabel antrian
    c.execute("""
        CREATE TABLE IF NOT EXISTS antrian (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nomor_antrian   INTEGER NOT NULL,
            nama_customer   TEXT NOT NULL,
            nomor_wa        TEXT NOT NULL,
            nama_file       TEXT NOT NULL,
            path_file       TEXT NOT NULL,
            jumlah_lembar   INTEGER DEFAULT 1,
            jenis_layanan   TEXT DEFAULT 'Print',
            pembayaran      TEXT DEFAULT 'Cash',
            status          TEXT DEFAULT 'Menunggu',
            catatan         TEXT DEFAULT '',
            harga           INTEGER DEFAULT 0,
            waktu_pesan     TEXT NOT NULL,
            waktu_selesai   TEXT DEFAULT ''
        )
    """)
 
    # Tambah kolom harga kalau belum ada (upgrade dari versi lama)
    try:
        c.execute("ALTER TABLE antrian ADD COLUMN harga INTEGER DEFAULT 0")
    except Exception:
        pass
 
    # Tabel pengaturan (harga satuan & QRIS URL)
    c.execute("""
        CREATE TABLE IF NOT EXISTS pengaturan (
            kunci   TEXT PRIMARY KEY,
            nilai   TEXT NOT NULL
        )
    """)
 
    # Harga default
    defaults = {
        "harga_print_bw"   : "500",
        "harga_print_warna": "1500",
        "harga_scan"       : "1000",
        "harga_lainnya"    : "1000",
        "qris_url"         : "",
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO pengaturan VALUES (?, ?)", (k, v))
 
    conn.commit()
    conn.close()
 
def get_setting(kunci):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT nilai FROM pengaturan WHERE kunci=?", (kunci,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""
 
def set_setting(kunci, nilai):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO pengaturan VALUES (?, ?)", (kunci, str(nilai)))
    conn.commit()
    conn.close()
 
def hitung_harga(jenis, lembar):
    key = {
        "Print Hitam Putih": "harga_print_bw",
        "Print Warna"      : "harga_print_warna",
        "Scan Dokumen"     : "harga_scan",
        "Lainnya"          : "harga_lainnya",
    }.get(jenis, "harga_lainnya")
    satuan = int(get_setting(key) or 0)
    return satuan * lembar
 
def get_next_nomor():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT MAX(nomor_antrian) FROM antrian WHERE date(waktu_pesan)=date('now','localtime')")
    r = c.fetchone()[0]
    conn.close()
    return (r or 0) + 1
 
def tambah_antrian(nama, wa, nama_file, path_file, lembar, jenis, bayar, catatan, harga):
    nomor = get_next_nomor()
    waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO antrian
          (nomor_antrian,nama_customer,nomor_wa,nama_file,path_file,
           jumlah_lembar,jenis_layanan,pembayaran,status,catatan,harga,waktu_pesan)
        VALUES (?,?,?,?,?,?,?,?,'Menunggu',?,?,?)
    """, (nomor, nama, wa, nama_file, path_file, lembar, jenis, bayar, catatan, harga, waktu))
    conn.commit()
    conn.close()
    return nomor
 
def update_status(antrian_id, status_baru):
    selesai = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status_baru == "Selesai" else ""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE antrian SET status=?, waktu_selesai=? WHERE id=?",
              (status_baru, selesai, antrian_id))
    conn.commit()
    conn.close()
 
def update_harga_antrian(antrian_id, harga_baru):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE antrian SET harga=? WHERE id=?", (harga_baru, antrian_id))
    conn.commit()
    conn.close()
 
def get_semua_antrian():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id,nomor_antrian,nama_customer,nomor_wa,nama_file,
               jumlah_lembar,jenis_layanan,pembayaran,status,catatan,harga,waktu_pesan,waktu_selesai
        FROM antrian
        WHERE date(waktu_pesan)=date('now','localtime')
        ORDER BY nomor_antrian ASC
    """)
    rows = c.fetchall()
    conn.close()
    return rows
 
def get_antrian_aktif():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT nomor_antrian,nama_customer,jenis_layanan,status
        FROM antrian
        WHERE status IN ('Menunggu','Dikerjakan')
          AND date(waktu_pesan)=date('now','localtime')
        ORDER BY nomor_antrian ASC LIMIT 5
    """)
    rows = c.fetchall()
    conn.close()
    return rows
 
def get_sedang_dikerjakan():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT nomor_antrian,nama_customer,jenis_layanan
        FROM antrian
        WHERE status='Dikerjakan' AND date(waktu_pesan)=date('now','localtime')
        ORDER BY nomor_antrian ASC LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    return row
 
def get_antrian_by_nomor(nomor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id,nomor_antrian,nama_customer,nama_file,jenis_layanan,
               pembayaran,status,waktu_pesan,waktu_selesai,jumlah_lembar,harga
        FROM antrian
        WHERE nomor_antrian=? AND date(waktu_pesan)=date('now','localtime')
        ORDER BY id DESC LIMIT 1
    """, (nomor,))
    row = c.fetchone()
    conn.close()
    return row
 
def get_statistik():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN status='Menunggu'  THEN 1 ELSE 0 END),
               SUM(CASE WHEN status='Dikerjakan' THEN 1 ELSE 0 END),
               SUM(CASE WHEN status='Selesai'   THEN 1 ELSE 0 END),
               SUM(CASE WHEN status='Selesai'   THEN harga ELSE 0 END)
        FROM antrian WHERE date(waktu_pesan)=date('now','localtime')
    """)
    row = c.fetchone()
    conn.close()
    return row
 
# ─── QR GENERATOR ─────────────────────────────────────────────────────────────
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
 
def rupiah(n):
    return f"Rp {int(n):,}".replace(",", ".")
 
# ─── CSS ──────────────────────────────────────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Mono:wght@700&display=swap');
    html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;}
    .stApp{background:linear-gradient(135deg,#0f0c29 0%,#302b63 50%,#24243e 100%);min-height:100vh;}
 
    .brand-header{text-align:center;padding:2rem 1rem 1rem;}
    .brand-title{font-size:2rem;font-weight:800;color:#fff;letter-spacing:-0.5px;}
    .brand-subtitle{font-size:0.85rem;color:#a0a0c0;letter-spacing:2px;text-transform:uppercase;margin-top:0.25rem;}
 
    .card{background:rgba(255,255,255,0.06);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.12);border-radius:16px;padding:1.5rem;margin-bottom:1rem;}
    .card-title{font-size:0.75rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#8b8bab;margin-bottom:0.75rem;}
 
    .now-serving{background:linear-gradient(135deg,#f7971e,#ffd200);border-radius:16px;padding:1.5rem;text-align:center;margin-bottom:1rem;}
    .now-serving-label{font-size:0.7rem;font-weight:700;letter-spacing:3px;color:rgba(0,0,0,0.6);text-transform:uppercase;}
    .now-serving-number{font-family:'Space Mono',monospace;font-size:5rem;font-weight:700;color:#1a1a2e;line-height:1;margin:0.25rem 0;}
    .now-serving-name{font-size:1rem;font-weight:600;color:rgba(0,0,0,0.75);}
 
    .badge{display:inline-block;padding:0.2rem 0.7rem;border-radius:999px;font-size:0.72rem;font-weight:700;}
    .badge-menunggu{background:rgba(251,191,36,0.2);color:#fbbf24;}
    .badge-dikerjakan{background:rgba(59,130,246,0.2);color:#60a5fa;}
    .badge-selesai{background:rgba(52,211,153,0.2);color:#34d399;}
    .badge-batal{background:rgba(248,113,113,0.2);color:#f87171;}
    .badge-tagihan{background:rgba(167,139,250,0.2);color:#a78bfa;}
 
    .antrian-item{display:flex;align-items:center;justify-content:space-between;padding:0.75rem 1rem;background:rgba(255,255,255,0.04);border-radius:10px;margin-bottom:0.5rem;border:1px solid rgba(255,255,255,0.06);}
    .antrian-item-number{font-family:'Space Mono',monospace;font-size:1.25rem;font-weight:700;color:#ffd200;min-width:3rem;}
    .antrian-item-info{flex:1;padding:0 0.75rem;}
    .antrian-item-name{font-weight:600;color:#e0e0f0;font-size:0.9rem;}
    .antrian-item-type{font-size:0.75rem;color:#8b8bab;}
 
    .ticket{background:linear-gradient(135deg,#1a1a2e,#302b63);border:2px solid #ffd200;border-radius:20px;padding:2rem;text-align:center;}
    .ticket-number{font-family:'Space Mono',monospace;font-size:6rem;font-weight:700;color:#ffd200;line-height:1;}
    .ticket-label{font-size:0.75rem;letter-spacing:3px;color:#8b8bab;text-transform:uppercase;margin-bottom:0.5rem;}
 
    /* TAGIHAN BOX */
    .tagihan-box{background:rgba(167,139,250,0.08);border:2px solid rgba(167,139,250,0.4);border-radius:20px;padding:1.5rem;margin-bottom:1rem;text-align:center;}
    .tagihan-title{font-size:1rem;font-weight:800;color:#a78bfa;margin-bottom:0.25rem;}
    .tagihan-sub{font-size:0.78rem;color:#a0a0c0;margin-bottom:1rem;}
    .tagihan-rincian{background:rgba(255,255,255,0.05);border-radius:12px;padding:1rem;margin-bottom:1rem;text-align:left;}
    .tagihan-total{font-family:'Space Mono',monospace;font-size:2rem;font-weight:700;color:#ffd200;margin:0.5rem 0;}
 
    /* QRIS BOX */
    .qris-box{background:rgba(255,255,255,0.07);border:2px solid rgba(255,210,0,0.5);border-radius:20px;padding:1.5rem;text-align:center;margin-bottom:1rem;}
    .qris-title{font-size:1rem;font-weight:800;color:#ffd200;margin-bottom:0.25rem;}
    .qris-sub{font-size:0.78rem;color:#a0a0c0;margin-bottom:1rem;}
    .qris-img{max-width:220px;width:100%;border-radius:12px;border:3px solid white;margin:0 auto 1rem;display:block;}
    .qris-total{font-family:'Space Mono',monospace;font-size:1.75rem;font-weight:700;color:#34d399;margin:0.5rem 0;}
    .qris-note{font-size:0.8rem;color:#fbbf24;font-weight:600;margin-top:0.75rem;}
 
    .stat-box{background:rgba(255,255,255,0.06);border-radius:12px;padding:1rem;text-align:center;}
    .stat-num{font-family:'Space Mono',monospace;font-size:2rem;font-weight:700;color:#ffd200;}
    .stat-label{font-size:0.7rem;color:#8b8bab;letter-spacing:1px;text-transform:uppercase;}
 
    .harga-card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:1rem;margin-bottom:0.5rem;}
    .harga-label{font-size:0.8rem;color:#a0a0c0;margin-bottom:0.25rem;}
    .harga-val{font-family:'Space Mono',monospace;font-size:1.1rem;color:#ffd200;font-weight:700;}
 
    .stButton>button{background:linear-gradient(135deg,#f7971e,#ffd200)!important;color:#1a1a2e!important;font-weight:700!important;border:none!important;border-radius:10px!important;padding:0.6rem 1.5rem!important;font-family:'Plus Jakarta Sans',sans-serif!important;font-size:0.9rem!important;transition:all 0.2s ease!important;}
    .stButton>button:hover{transform:translateY(-1px)!important;box-shadow:0 8px 24px rgba(247,151,30,0.35)!important;}
    .stTextInput>div>div>input,.stNumberInput>div>div>input,.stSelectbox>div>div,.stTextArea>div>div>textarea{background:rgba(255,255,255,0.08)!important;border:1px solid rgba(255,255,255,0.15)!important;border-radius:10px!important;color:#fff!important;font-family:'Plus Jakarta Sans',sans-serif!important;}
    label,.stRadio label,.stSelectbox label{color:#c0c0d8!important;font-size:0.85rem!important;font-weight:500!important;}
    .stFileUploader>div{background:rgba(255,255,255,0.05)!important;border:2px dashed rgba(255,210,0,0.3)!important;border-radius:12px!important;}
    hr{border-color:rgba(255,255,255,0.1)!important;}
    .stTabs [data-baseweb="tab"]{color:#8b8bab!important;font-weight:600!important;}
    .stTabs [aria-selected="true"]{color:#ffd200!important;border-bottom-color:#ffd200!important;}
    div[data-testid="stForm"]{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:1.5rem;}
    .stSuccess{background:rgba(52,211,153,0.15)!important;border-radius:10px!important;}
    .stError{background:rgba(248,113,113,0.15)!important;border-radius:10px!important;}
    .stWarning{background:rgba(251,191,36,0.15)!important;border-radius:10px!important;}
    .stInfo{background:rgba(96,165,250,0.15)!important;border-radius:10px!important;}
    .block-container{padding-top:1rem!important;}
    </style>
    """, unsafe_allow_html=True)
 
def status_badge(status):
    cls = {"Menunggu":"badge-menunggu","Dikerjakan":"badge-dikerjakan",
           "Selesai":"badge-selesai","Dibatalkan":"badge-batal",
           "Menunggu Pembayaran":"badge-tagihan"}.get(status,"badge-menunggu")
    return f'<span class="badge {cls}">{status}</span>'
 
def tampilkan_tiket(nomor, nama, jenis, bayar, harga):
    st.markdown(f"""
    <div class="ticket">
        <div class="ticket-label">🎫 Nomor Antrian Kamu</div>
        <div class="ticket-number">{nomor:02d}</div>
        <div style="color:#a0a0c0;font-size:0.85rem;margin-top:0.75rem;">
            {nama} · {jenis}<br>
            <span style="color:#ffd200;font-weight:700;">Pembayaran: {bayar}</span>
            {"&nbsp;·&nbsp;<span style='color:#34d399;'>"+rupiah(harga)+"</span>" if harga else ""}<br><br>
            <span style="color:#8b8bab;">Simpan nomor ini untuk cek status pesanan!</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
 
# ─── ALUR CUSTOMER ─────────────────────────────────────────────────────────────
# Tahapan session_state:
#  (kosong)         → tampilkan form
#  tahap="tagihan"  → tampilkan tagihan + pilih bayar
#  tahap="qris"     → tampilkan QRIS + tombol sudah bayar
#  tahap="tiket"    → tampilkan tiket nomor antrian
 
def halaman_customer():
    st.markdown("""
    <div class="brand-header">
        <div class="brand-title">🖨️ Hadi Prana</div>
        <div class="brand-subtitle">Percetakan & Fotocopy · Tanah Baru, Bogor</div>
    </div>
    """, unsafe_allow_html=True)
 
    # Banner antrian sedang dikerjakan
    sedang = get_sedang_dikerjakan()
    if sedang:
        st.markdown(f"""
        <div class="now-serving">
            <div class="now-serving-label">⚡ Sedang Dikerjakan</div>
            <div class="now-serving-number">{sedang[0]:02d}</div>
            <div class="now-serving-name">{sedang[1]} · {sedang[2]}</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="card" style="text-align:center;padding:1rem;">
            <span style="color:#8b8bab;font-size:0.9rem;">Belum ada pesanan yang sedang dikerjakan</span>
        </div>""", unsafe_allow_html=True)
 
    # Daftar antrian menunggu
    menunggu_list = [a for a in get_antrian_aktif() if a[3] == "Menunggu"]
    if menunggu_list:
        st.markdown('<div class="card"><div class="card-title">📋 Antrian Menunggu</div>', unsafe_allow_html=True)
        for a in menunggu_list:
            st.markdown(f"""
            <div class="antrian-item">
                <div class="antrian-item-number">{a[0]:02d}</div>
                <div class="antrian-item-info">
                    <div class="antrian-item-name">{a[1]}</div>
                    <div class="antrian-item-type">{a[2]}</div>
                </div>
                {status_badge(a[3])}
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
 
    st.markdown("---")
    tab1, tab2 = st.tabs(["📤 Pesan Print / Scan", "🔍 Cek Status Saya"])
 
    with tab1:
        tahap = st.session_state.get("tahap", "")
 
        # ── TAHAP 3: Tiket sudah didapat ─────────────────────────────────────
        if tahap == "tiket":
            t = st.session_state["order"]
            st.success(f"✅ Pesanan diterima! Nomor antrian kamu: **{t['nomor']:02d}**")
            tampilkan_tiket(t["nomor"], t["nama"], t["jenis"], t["bayar"], t["harga"])
            st.markdown("""<div style="text-align:center;margin-top:1rem;">
                <span style="color:#8b8bab;font-size:0.8rem;">
                    Pak Hadi akan mengirim WA ketika dokumenmu selesai 📲
                </span></div>""", unsafe_allow_html=True)
            if st.button("🔄 Pesan Lagi", use_container_width=True):
                st.session_state.pop("tahap", None)
                st.session_state.pop("order", None)
                st.rerun()
 
        # ── TAHAP 2b: Tampilkan QRIS bayar ───────────────────────────────────
        elif tahap == "qris":
            d = st.session_state["order"]
            qris_url = get_setting("qris_url")
 
            st.markdown(f"""
            <div class="qris-box">
                <div class="qris-title">💳 Scan QRIS untuk Membayar</div>
                <div class="qris-sub">Scan QR di bawah menggunakan aplikasi e-wallet atau mobile banking</div>
            """, unsafe_allow_html=True)
 
            if qris_url:
                st.markdown(f'<img class="qris-img" src="{qris_url}" alt="QRIS Hadi Prana"/>', unsafe_allow_html=True)
            else:
                st.warning("⚠️ QR QRIS belum diatur oleh admin. Minta Pak Hadi upload foto QRIS di halaman admin.")
 
            st.markdown(f"""
                <div class="qris-total">{rupiah(d['harga'])}</div>
                <div style="font-size:0.85rem;color:#e0e0f0;">
                    {d['nama']} · {d['jenis']} · {d['lembar']} lembar
                </div>
                <div class="qris-note">⚠️ Pastikan pembayaran sudah berhasil sebelum klik konfirmasi!</div>
            </div>""", unsafe_allow_html=True)
 
            col_batal, col_konfirm = st.columns(2)
            with col_batal:
                if st.button("❌ Batalkan", use_container_width=True, key="batal_qris"):
                    st.session_state.pop("tahap", None)
                    st.session_state.pop("order", None)
                    st.rerun()
            with col_konfirm:
                if st.button("✅ Sudah Bayar!", use_container_width=True, key="konfirm_qris"):
                    d = st.session_state["order"]
                    nomor = tambah_antrian(d["nama"], d["wa"], d["nama_file"],
                                          d["path_file"], d["lembar"], d["jenis"],
                                          "QRIS", d["catatan"], d["harga"])
                    st.session_state["order"]["nomor"] = nomor
                    st.session_state["order"]["bayar"] = "QRIS"
                    st.session_state["tahap"] = "tiket"
                    st.rerun()
 
        # ── TAHAP 2a: Tampilkan tagihan + pilih metode bayar ──────────────────
        elif tahap == "tagihan":
            d = st.session_state["order"]
 
            st.markdown(f"""
            <div class="tagihan-box">
                <div class="tagihan-title">🧾 Tagihan Pesanan</div>
                <div class="tagihan-sub">Cek rincian pesananmu sebelum membayar</div>
                <div class="tagihan-rincian">
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;color:#c0c0d8;margin-bottom:6px;">
                        <span>Layanan</span><span style="color:#e0e0f0;font-weight:600;">{d['jenis']}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;color:#c0c0d8;margin-bottom:6px;">
                        <span>Jumlah Lembar</span><span style="color:#e0e0f0;font-weight:600;">{d['lembar']} lembar</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;color:#c0c0d8;margin-bottom:6px;">
                        <span>File</span><span style="color:#e0e0f0;">{d['nama_file']}</span>
                    </div>
                    {"<div style='display:flex;justify-content:space-between;font-size:0.85rem;color:#c0c0d8;'><span>Catatan</span><span style='color:#e0e0f0;'>" + d['catatan'] + "</span></div>" if d['catatan'] else ""}
                    <hr style="margin:0.75rem 0;border-color:rgba(255,255,255,0.1)!important;"/>
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:0.9rem;font-weight:700;color:#a78bfa;">Total Bayar</span>
                        <span style="font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;color:#ffd200;">{rupiah(d['harga'])}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
 
            st.markdown("##### Pilih Metode Pembayaran")
            col_cash, col_qris = st.columns(2)
            with col_cash:
                if st.button("💵 Cash saat ambil", use_container_width=True, key="pilih_cash"):
                    d = st.session_state["order"]
                    nomor = tambah_antrian(d["nama"], d["wa"], d["nama_file"],
                                          d["path_file"], d["lembar"], d["jenis"],
                                          "Cash saat ambil", d["catatan"], d["harga"])
                    st.session_state["order"]["nomor"] = nomor
                    st.session_state["order"]["bayar"] = "Cash saat ambil"
                    st.session_state["tahap"] = "tiket"
                    st.rerun()
            with col_qris:
                if st.button("💳 Bayar QRIS", use_container_width=True, key="pilih_qris"):
                    st.session_state["tahap"] = "qris"
                    st.rerun()
 
            if st.button("← Kembali ke Form", use_container_width=False, key="back_form"):
                # Hapus file yang sudah disimpan
                d = st.session_state.get("order", {})
                if d.get("path_file") and os.path.exists(d["path_file"]):
                    os.remove(d["path_file"])
                st.session_state.pop("tahap", None)
                st.session_state.pop("order", None)
                st.rerun()
 
        # ── TAHAP 1: Form upload ──────────────────────────────────────────────
        else:
            # Tampilkan daftar harga
            harga_bw     = int(get_setting("harga_print_bw") or 0)
            harga_warna  = int(get_setting("harga_print_warna") or 0)
            harga_scan   = int(get_setting("harga_scan") or 0)
            harga_lain   = int(get_setting("harga_lainnya") or 0)
 
            st.markdown(f"""
            <div class="card">
                <div class="card-title">💰 Daftar Harga (per lembar)</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;">
                    <div class="harga-card">
                        <div class="harga-label">🖤 Print Hitam Putih</div>
                        <div class="harga-val">{rupiah(harga_bw)}</div>
                    </div>
                    <div class="harga-card">
                        <div class="harga-label">🌈 Print Warna</div>
                        <div class="harga-val">{rupiah(harga_warna)}</div>
                    </div>
                    <div class="harga-card">
                        <div class="harga-label">📠 Scan Dokumen</div>
                        <div class="harga-val">{rupiah(harga_scan)}</div>
                    </div>
                    <div class="harga-card">
                        <div class="harga-label">📦 Lainnya</div>
                        <div class="harga-val">{rupiah(harga_lain)}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
 
            st.markdown("##### Isi form untuk pesan antrian")
            with st.form("form_pesan", clear_on_submit=False):
                col1, col2 = st.columns(2)
                with col1:
                    nama = st.text_input("Nama Kamu *", placeholder="contoh: Budi")
                with col2:
                    wa = st.text_input("No. WhatsApp *", placeholder="contoh: 08123456789")
 
                jenis  = st.selectbox("Jenis Layanan",
                                      ["Print Hitam Putih","Print Warna","Scan Dokumen","Lainnya"])
                lembar = st.number_input("Jumlah Lembar / Halaman", min_value=1, max_value=9999, value=1)
                catatan = st.text_area("Catatan Tambahan (opsional)",
                                       placeholder="Ukuran kertas, warna, dll...", height=80)
                file = st.file_uploader(
                    f"Upload File * (maks {MAX_UPLOAD_MB//1024} GB)",
                    type=["pdf","doc","docx","jpg","jpeg","png","xlsx","pptx","ppt","xls","txt","zip","rar"]
                )
 
                # Preview total harga
                total_preview = hitung_harga(jenis, lembar)
                st.markdown(f"""
                <div style="background:rgba(255,210,0,0.08);border:1px solid rgba(255,210,0,0.3);
                            border-radius:10px;padding:0.75rem 1rem;margin-top:0.5rem;
                            display:flex;justify-content:space-between;align-items:center;">
                    <span style="color:#a0a0c0;font-size:0.85rem;">Estimasi Total</span>
                    <span style="font-family:'Space Mono',monospace;font-size:1.25rem;
                                 font-weight:700;color:#ffd200;">{rupiah(total_preview)}</span>
                </div>
                """, unsafe_allow_html=True)
 
                submitted = st.form_submit_button("🧾 Lihat Tagihan & Bayar", use_container_width=True)
 
                if submitted:
                    if not nama.strip() or not wa.strip() or file is None:
                        st.error("⚠️ Nama, nomor WA, dan file wajib diisi!")
                    else:
                        file_bytes = file.getbuffer()
                        if len(file_bytes) / (1024*1024) > MAX_UPLOAD_MB:
                            st.error(f"⚠️ File terlalu besar! Maksimal {MAX_UPLOAD_MB//1024} GB.")
                        else:
                            safe_name = f"{int(time.time())}_{file.name}"
                            path = os.path.join(UPLOAD_DIR, safe_name)
                            with open(path, "wb") as fout:
                                fout.write(file_bytes)
                            harga = hitung_harga(jenis, lembar)
                            st.session_state["order"] = {
                                "nama": nama.strip(), "wa": wa.strip(),
                                "nama_file": file.name, "path_file": path,
                                "lembar": lembar, "jenis": jenis,
                                "catatan": catatan, "harga": harga,
                            }
                            st.session_state["tahap"] = "tagihan"
                            st.rerun()
 
    with tab2:
        st.markdown("##### Masukkan nomor antrian kamu")
        nomor_cek = st.number_input("Nomor Antrian", min_value=1, max_value=999, step=1,
                                     value=st.session_state.get("order", {}).get("nomor", 1))
        if st.button("🔍 Cek Status", use_container_width=True):
            data = get_antrian_by_nomor(nomor_cek)
            if data:
                _, nomor, nama, nama_file, jenis, bayar, status, waktu_pesan, waktu_selesai, lembar, harga = data
                warna = {"Menunggu":"#fbbf24","Dikerjakan":"#60a5fa","Selesai":"#34d399"}.get(status,"#fbbf24")
                st.markdown(f"""
                <div class="card">
                    <div style="text-align:center;margin-bottom:1rem;">
                        <div style="font-family:'Space Mono',monospace;font-size:3.5rem;font-weight:700;color:{warna};line-height:1;">{nomor:02d}</div>
                        <div style="margin-top:0.5rem;">{status_badge(status)}</div>
                    </div>
                    <div style="display:grid;gap:0.5rem;font-size:0.85rem;">
                        <div style="display:flex;justify-content:space-between;">
                            <span style="color:#8b8bab;">Nama</span><span style="color:#e0e0f0;font-weight:600;">{nama}</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;">
                            <span style="color:#8b8bab;">File</span><span style="color:#e0e0f0;">{nama_file}</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;">
                            <span style="color:#8b8bab;">Layanan</span><span style="color:#e0e0f0;">{jenis} · {lembar} lembar</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;">
                            <span style="color:#8b8bab;">Total</span><span style="color:#ffd200;font-weight:700;">{rupiah(harga)}</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;">
                            <span style="color:#8b8bab;">Pembayaran</span><span style="color:#e0e0f0;">{bayar}</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;">
                            <span style="color:#8b8bab;">Waktu Pesan</span><span style="color:#e0e0f0;">{waktu_pesan[11:16]}</span>
                        </div>
                        {"<div style='display:flex;justify-content:space-between;'><span style='color:#8b8bab;'>Selesai</span><span style='color:#34d399;font-weight:700;'>" + waktu_selesai[11:16] + "</span></div>" if waktu_selesai else ""}
                    </div>
                </div>""", unsafe_allow_html=True)
 
                if status == "Selesai":
                    st.success("✅ Dokumen kamu sudah selesai! Silakan ambil di kasir Pak Hadi.")
                elif status == "Dikerjakan":
                    st.info("⚡ Dokumen kamu sedang dikerjakan oleh Pak Hadi!")
                else:
                    semua = get_antrian_aktif()
                    pos = next((i+1 for i, a in enumerate(semua) if a[0] == nomor), None)
                    if pos:
                        st.warning(f"⏳ Posisi kamu: **nomor {pos} dalam antrian**. Harap sabar ya!")
            else:
                st.error("❌ Nomor antrian tidak ditemukan untuk hari ini.")
 
        st.markdown("""<div style="text-align:center;margin-top:1.5rem;font-size:0.78rem;color:#8b8bab;">
            Pak Hadi akan mengirim pesan WA ketika dokumenmu selesai 📲</div>""", unsafe_allow_html=True)
 
# ─── HALAMAN ADMIN ─────────────────────────────────────────────────────────────
def halaman_admin():
    st.markdown("""
    <div class="brand-header">
        <div class="brand-title">⚙️ Dashboard Pak Hadi</div>
        <div class="brand-subtitle">Kelola Antrian · Hadi Prana</div>
    </div>""", unsafe_allow_html=True)
 
    stats = get_statistik()
    if stats and stats[0]:
        total, menunggu, dikerjakan, selesai, omzet = stats
        c1,c2,c3,c4,c5 = st.columns(5)
        for col, val, label in zip(
            [c1,c2,c3,c4,c5],
            [total, menunggu, dikerjakan, selesai, rupiah(omzet or 0)],
            ["Total","Menunggu","Dikerjakan","Selesai","💰 Omzet"]
        ):
            with col:
                st.markdown(f"""<div class="stat-box">
                    <div class="stat-num" style="font-size:{'1.1rem' if label=='💰 Omzet' else '2rem'};">{val or 0}</div>
                    <div class="stat-label">{label}</div></div>""", unsafe_allow_html=True)
        st.markdown("")
 
    tab_antrian, tab_harga, tab_qr = st.tabs(["📋 Kelola Antrian", "💰 Atur Harga & QRIS", "📱 QR Code & WA"])
 
    # ── TAB ANTRIAN ────────────────────────────────────────────────────────────
    with tab_antrian:
        if st.button("🔄 Refresh", key="refresh_admin"):
            st.rerun()
        semua = get_semua_antrian()
        if not semua:
            st.info("Belum ada pesanan masuk hari ini.")
        else:
            for row in semua:
                rid,nomor,nama,wa,nama_file,lembar,jenis,bayar,status,catatan,harga,waktu,selesai = row
                with st.expander(f"#{nomor:02d} · {nama} · {jenis} · {status}", expanded=(status=="Menunggu")):
                    col_info, col_aksi = st.columns([2,1])
                    with col_info:
                        st.markdown(f"""
                        <div style="font-size:0.85rem;color:#c0c0d8;line-height:2;">
                            📁 <b>File:</b> {nama_file}<br>
                            📞 <b>WA:</b> {wa}<br>
                            🖨️ <b>Lembar:</b> {lembar}<br>
                            💰 <b>Total:</b> <span style="color:#ffd200;font-weight:700;">{rupiah(harga)}</span><br>
                            💳 <b>Bayar:</b> {bayar}<br>
                            🕐 <b>Pesan:</b> {waktu[11:16]}<br>
                            {"💬 <b>Catatan:</b> " + catatan if catatan else ""}
                        </div>""", unsafe_allow_html=True)
 
                        # Download file
                        conn = sqlite3.connect(DB_PATH)
                        cur = conn.cursor()
                        cur.execute("SELECT path_file FROM antrian WHERE id=?", (rid,))
                        pf = cur.fetchone()
                        conn.close()
                        if pf and os.path.exists(pf[0]):
                            with open(pf[0],"rb") as f:
                                st.download_button(f"⬇️ Download {nama_file}", f.read(),
                                                   file_name=nama_file, key=f"dl_{rid}")
 
                        # Edit harga manual (kalau perlu koreksi)
                        with st.expander("✏️ Koreksi Harga"):
                            harga_edit = st.number_input("Harga (Rp)", value=int(harga or 0),
                                                          step=500, key=f"harga_{rid}")
                            if st.button("Simpan Harga", key=f"saveh_{rid}"):
                                update_harga_antrian(rid, harga_edit)
                                st.success("Harga diperbarui!")
                                st.rerun()
 
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
                                wa_clean = wa.replace("-","").replace(" ","")
                                if not wa_clean.startswith("62"):
                                    wa_clean = "62" + wa_clean.lstrip("0")
                                pesan = (f"Halo {nama}! 👋%0A"
                                         f"Pesanan kamu ({jenis}) sudah selesai dikerjakan.%0A"
                                         f"Total: {rupiah(harga)}%0A"
                                         f"Silakan ambil di tempat Pak Hadi ya! 🙏%0A%0A"
                                         f"Terima kasih sudah percaya pada Hadi Prana Percetakan ✨")
                                link_wa = f"https://wa.me/{wa_clean}?text={pesan}"
                                st.success(f"Selesai! Kirim notif ke {nama}:")
                                st.markdown(f'<a href="{link_wa}" target="_blank"><button style="width:100%;background:linear-gradient(135deg,#25D366,#128C7E);color:white;border:none;border-radius:10px;padding:0.5rem 1rem;font-weight:700;cursor:pointer;margin-top:0.5rem;">📲 Kirim WA ke {nama}</button></a>', unsafe_allow_html=True)
                                st.rerun()
                        if status not in ["Selesai","Dibatalkan"]:
                            if st.button("❌ Batalkan", key=f"batal_{rid}", use_container_width=True):
                                update_status(rid, "Dibatalkan")
                                st.rerun()
 
    # ── TAB HARGA & QRIS ──────────────────────────────────────────────────────
    with tab_harga:
        st.markdown("#### 💰 Atur Harga per Lembar")
        st.info("Harga ini akan otomatis dihitung ke tagihan customer saat mereka memesan.")
 
        col1, col2 = st.columns(2)
        with col1:
            h_bw = st.number_input("🖤 Print Hitam Putih (Rp/lembar)",
                                    value=int(get_setting("harga_print_bw") or 500), step=100)
            h_scan = st.number_input("📠 Scan Dokumen (Rp/lembar)",
                                      value=int(get_setting("harga_scan") or 1000), step=100)
        with col2:
            h_warna = st.number_input("🌈 Print Warna (Rp/lembar)",
                                       value=int(get_setting("harga_print_warna") or 1500), step=100)
            h_lain = st.number_input("📦 Lainnya (Rp/lembar)",
                                      value=int(get_setting("harga_lainnya") or 1000), step=100)
 
        if st.button("💾 Simpan Harga", use_container_width=True):
            set_setting("harga_print_bw",    h_bw)
            set_setting("harga_print_warna", h_warna)
            set_setting("harga_scan",        h_scan)
            set_setting("harga_lainnya",     h_lain)
            st.success("✅ Harga berhasil disimpan! Akan langsung berlaku untuk pesanan berikutnya.")
 
        st.markdown("---")
        st.markdown("#### 🖼️ Upload Foto QRIS Pak Hadi")
        st.markdown("""
        <div style="font-size:0.85rem;color:#a0a0c0;line-height:1.8;margin-bottom:1rem;">
            Foto QRIS ini akan muncul di halaman pembayaran customer.<br>
            Cara upload foto QRIS ke internet:<br>
            1️⃣ Buka <b>imgur.com</b> → klik "New post" → upload foto QRIS<br>
            2️⃣ Klik kanan gambar → <b>Copy image address</b><br>
            3️⃣ Paste URL di bawah lalu klik Simpan
        </div>
        """, unsafe_allow_html=True)
 
        current_qris = get_setting("qris_url")
        qris_url_input = st.text_input("URL Foto QRIS", value=current_qris,
                                        placeholder="https://i.imgur.com/xxxxxxx.jpg")
 
        if qris_url_input:
            st.markdown(f"""
            <div style="text-align:center;margin:1rem 0;">
                <img src="{qris_url_input}" style="max-width:200px;border-radius:12px;border:3px solid #ffd200;" />
                <div style="font-size:0.75rem;color:#8b8bab;margin-top:0.5rem;">Preview QRIS</div>
            </div>""", unsafe_allow_html=True)
 
        if st.button("💾 Simpan URL QRIS", use_container_width=True):
            set_setting("qris_url", qris_url_input)
            st.success("✅ URL QRIS berhasil disimpan!")
 
    # ── TAB QR CODE & WA ──────────────────────────────────────────────────────
    with tab_qr:
        st.markdown("#### 📱 QR Code untuk Ditempel di Kasir")
        url_input = st.text_input("URL Website", value="https://hadipranaprint.streamlit.app")
        if url_input:
            qr_buf = generate_qr(url_input)
            b64 = img_to_b64(qr_buf)
            st.markdown(f"""
            <div style="text-align:center;margin:1.5rem 0;">
                <div style="display:inline-block;background:white;padding:1.5rem;border-radius:16px;box-shadow:0 8px 32px rgba(255,210,0,0.3);">
                    <img src="data:image/png;base64,{b64}" style="width:220px;height:220px;"/>
                    <div style="margin-top:0.75rem;font-size:0.75rem;color:#302b63;font-weight:700;letter-spacing:1px;">SCAN UNTUK ORDER PRINT</div>
                    <div style="font-size:0.65rem;color:#8b8bab;margin-top:0.25rem;">Hadi Prana · Tanah Baru, Bogor</div>
                </div>
            </div>""", unsafe_allow_html=True)
            st.download_button("⬇️ Download QR Code (PNG)", qr_buf.getvalue(),
                               file_name="qr_hadiPrana.png", mime="image/png", use_container_width=True)
 
        st.markdown("---")
        st.markdown("#### 💬 Template WA Business")
        st.markdown(f"""
        <div class="card">
            <div class="card-title">Away Message / Quick Reply</div>
            <div style="background:rgba(37,211,102,0.1);border:1px solid rgba(37,211,102,0.3);border-radius:10px;padding:1rem;font-size:0.85rem;color:#c0c0d8;line-height:1.8;font-family:monospace;">
            Halo! 👋 Terima kasih sudah menghubungi Hadi Prana Percetakan.<br><br>
            Untuk pesan <b>Print / Scan</b>, silakan lanjut melalui website antrian kami:<br>
            🔗 <span style="color:#ffd200;">{url_input}</span><br><br>
            Upload file, lihat tagihan, & bayar di sana. ✅<br>
            Pak Hadi akan kirim notifikasi WA kalau dokumennya sudah selesai! 📲<br><br>
            Untuk <b>Fotocopy</b>, silakan datang langsung ke tempat. 📍
            </div>
        </div>""", unsafe_allow_html=True)
 
# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    init_db()
    inject_css()
 
    mode = st.query_params.get("mode", "customer")
 
    if mode == "admin":
        if "admin_ok" not in st.session_state:
            st.markdown('<div class="brand-header"><div class="brand-title">🔐 Login Admin</div></div>', unsafe_allow_html=True)
            pin = st.text_input("Masukkan PIN Admin", type="password", placeholder="Masukkan PIN")
            if st.button("🔓 Masuk", use_container_width=True):
                if pin == ADMIN_PIN:
                    st.session_state["admin_ok"] = True
                    st.rerun()
                else:
                    st.error("❌ PIN salah!")
            st.markdown('<div style="text-align:center;margin-top:1rem;font-size:0.78rem;color:#8b8bab;">Akses khusus Pak Hadi · Hadi Prana</div>', unsafe_allow_html=True)
        else:
            halaman_admin()
            if st.sidebar.button("🚪 Logout"):
                del st.session_state["admin_ok"]
                st.rerun()
    else:
        halaman_customer()
        st.markdown("""<div style="text-align:center;margin-top:2rem;font-size:0.72rem;color:#8b8bab;">
            Status antrian diperbarui otomatis · Hadi Prana © 2026</div>""", unsafe_allow_html=True)
        time.sleep(30)
        st.rerun()
 
if __name__ == "__main__":
    main()

