import streamlit as st
import sqlite3
import hashlib
import os
import uuid
from PIL import Image
from streamlit_autorefresh import st_autorefresh # Pastikan ini di-import

# --- KONFIGURASI APLIKASI ---
DB_NAME = "topup_app.db"
IMAGE_DIR = "uploaded_images"

# Membuat folder untuk upload gambar jika belum ada
os.makedirs(IMAGE_DIR, exist_ok=True)

# --- FUNGSI DATABASE & KONEKSI ---
def get_conn():
    """Membuat koneksi ke database SQLite."""
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def create_tables():
    """Membuat tabel-tabel yang dibutuhkan jika belum ada."""
    conn = get_conn()
    c = conn.cursor()
    # Tabel Users (dengan kolom untuk simpan ID game)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            default_ml_id TEXT,
            default_ff_id TEXT
        )
    ''')
    # Tabel Products
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game TEXT NOT NULL,
            paket TEXT NOT NULL,
            harga INTEGER NOT NULL,
            image_path TEXT
        )
    ''')
    # Tabel Transactions
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            game TEXT NOT NULL,
            paket TEXT NOT NULL,
            harga INTEGER NOT NULL,
            user_nickname TEXT,
            user_game_id TEXT,
            status TEXT,
            waktu TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def seed_admin():
    """Membuat user admin default jika belum ada."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        password = hash_password('admin123')
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                  ('admin', password, 'admin'))
        conn.commit()
    conn.close()

# --- FUNGSI HELPER & CRUD (Create, Read, Update, Delete) ---
def hash_password(password):
    """Hashing password menggunakan SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def save_uploaded_file(uploaded_file):
    """
    Menyimpan file yang diunggah, mengonversinya ke RGB jika perlu,
    dan menyimpannya sebagai JPEG.
    """
    try:
        img = Image.open(uploaded_file)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        unique_filename = f"{uuid.uuid4().hex}.jpg"
        path = os.path.join(IMAGE_DIR, unique_filename)
        img.save(path, 'jpeg')
        return path
    except Exception as e:
        st.error(f"Error saat menyimpan file: {e}")
        return None

# Fungsi CRUD untuk Users
def register_user(username, password):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                     (username, hash_password(password), "user"))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password_hash=?",
              (username, hash_password(password)))
    user_data = c.fetchone()
    conn.close()
    return user_data

def get_user_data(username):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    user_data = c.fetchone()
    conn.close()
    return user_data

def update_user_password(username, new_password):
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash=? WHERE username=?",
                 (hash_password(new_password), username))
    conn.commit()
    conn.close()

def update_user_game_ids(username, ml_id, ff_id):
    conn = get_conn()
    conn.execute("UPDATE users SET default_ml_id=?, default_ff_id=? WHERE username=?",
                 (ml_id, ff_id, username))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users WHERE username != 'admin' ORDER BY id ASC")
    users = c.fetchall()
    conn.close()
    return users

def delete_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    if row:
        username = row[0]
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.execute("DELETE FROM transactions WHERE username=?", (username,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

# Fungsi CRUD untuk Products
def add_product(game, paket, harga, image_path):
    conn = get_conn()
    conn.execute("INSERT INTO products (game, paket, harga, image_path) VALUES (?, ?, ?, ?)",
                 (game, paket, harga, image_path))
    conn.commit()
    conn.close()

def get_products():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM products ORDER BY game, harga ASC")
    products = c.fetchall()
    conn.close()
    return products

def update_product(product_id, paket, harga, image_path):
    conn = get_conn()
    conn.execute("UPDATE products SET paket=?, harga=?, image_path=? WHERE id=?",
                 (paket, harga, image_path, product_id))
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = get_conn()
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()

# Fungsi CRUD untuk Transactions
def add_transaction(username, game, paket, harga, user_nickname, user_game_id, status="Menunggu"):
    conn = get_conn()
    conn.execute("INSERT INTO transactions (username, game, paket, harga, user_nickname, user_game_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (username, game, paket, harga, user_nickname, user_game_id, status))
    conn.commit()
    conn.close()

def get_user_transactions(username):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE username=? ORDER BY waktu DESC", (username,))
    transactions = c.fetchall()
    conn.close()
    return transactions

def get_all_transactions():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM transactions ORDER BY waktu DESC")
    transactions = c.fetchall()
    conn.close()
    return transactions

def update_transaction_status(trans_id, status):
    conn = get_conn()
    conn.execute("UPDATE transactions SET status=? WHERE id=?", (status, trans_id))
    conn.commit()
    conn.close()

# --- MANAJEMEN SESSION STATE ---
def clear_session():
    """Membersihkan session state saat logout."""
    keys_to_clear = ["user", "role", "user_selected_game", "selected_product", "last_statuses"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

# --- UI: HALAMAN LOGIN & REGISTRASI ---
def login_register_menu():
    st.sidebar.title("🎮 TopUpGame")
    menu = st.sidebar.selectbox("Menu", ["Login", "Register"])
    st.title("Selamat Datang di TopUpGame")
    st.write("Silakan login atau register untuk memulai top up game Anda.")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        if menu == "Register":
            st.subheader("Buat Akun Baru")
            with st.form("RegisterForm"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Register", use_container_width=True)
                if submitted:
                    if not username or not password:
                        st.error("Username dan password tidak boleh kosong.")
                    elif register_user(username, password):
                        st.success("Registrasi berhasil! Silakan pindah ke menu Login.")
                    else:
                        st.error("Username sudah digunakan.")
        else:
            st.subheader("Login ke Akun Anda")
            with st.form("LoginForm"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    user = login_user(username, password)
                    if user:
                        st.session_state["user"] = user[1]
                        st.session_state["role"] = user[3]
                        st.rerun()
                    else:
                        st.error("Username atau password salah.")

# --- UI: HALAMAN ADMIN ---
def admin_page():
    st.sidebar.title("👑 ADMIN PANEL")
    sub_menu = st.sidebar.radio("Menu", ["Kelola Produk", "Daftar Transaksi", "Kelola User"])
    if st.sidebar.button("Logout", use_container_width=True):
        clear_session()
        st.rerun()
    st.title("Admin Dashboard")
    if sub_menu == "Kelola Produk":
        st.subheader("Tambah Produk Baru")
        with st.form("AddProduct", clear_on_submit=True):
            game = st.selectbox("Pilih Game", ["Mobile Legends", "Free Fire"])
            paket = st.text_input("Nama Paket (e.g., 100 Diamonds)")
            harga = st.number_input("Harga (Rp)", min_value=1000, step=500)
            uploaded_image = st.file_uploader("Upload Gambar Produk", type=["png", "jpg", "jpeg"])
            submitted = st.form_submit_button("Tambah Produk")
            if submitted:
                if not all([game, paket, harga, uploaded_image]):
                    st.warning("Semua kolom dan gambar wajib diisi.")
                else:
                    image_path = save_uploaded_file(uploaded_image)
                    if image_path:
                        add_product(game, paket, harga, image_path)
                        st.success(f"Produk '{paket}' berhasil ditambahkan.")
                        st.rerun()
        st.markdown("---")
        st.subheader("Daftar Produk Saat Ini")
        products = get_products()
        if not products:
            st.info("Belum ada produk yang ditambahkan.")
        else:
            for p in products:
                with st.expander(f"**{p[1]}** - {p[2]} (Rp {p[3]:,})"):
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        if p[4] and os.path.isfile(p[4]):
                            st.image(p[4], width=100)
                        else:
                            st.caption("Gambar tidak ada")
                    with col2:
                        st.markdown(f"**ID Produk:** `{p[0]}`")
                        st.markdown(f"**Paket:** {p[2]}")
                        st.markdown(f"**Harga:** Rp {p[3]:,}")
                    st.markdown("##### Edit Produk Ini")
                    with st.form(key=f"edit_form_{p[0]}"):
                        new_paket = st.text_input("Nama Paket Baru", value=p[2])
                        new_harga = st.number_input("Harga Baru (Rp)", value=p[3], min_value=1000, step=500)
                        new_image = st.file_uploader("Ganti Gambar (Opsional)", type=["png", "jpg", "jpeg"], key=f"img_{p[0]}")
                        b_col1, b_col2 = st.columns(2)
                        with b_col1:
                           update_submitted = st.form_submit_button("Update Produk", use_container_width=True)
                        with b_col2:
                           delete_submitted = st.form_submit_button("Hapus Produk Ini", use_container_width=True, type="primary")
                        if update_submitted:
                            image_path = p[4]
                            if new_image is not None:
                                image_path = save_uploaded_file(new_image)
                            update_product(p[0], new_paket, new_harga, image_path)
                            st.success("Produk berhasil diupdate!")
                            st.rerun()
                        if delete_submitted:
                            delete_product(p[0])
                            st.success("Produk berhasil dihapus.")
                            st.rerun()
    elif sub_menu == "Daftar Transaksi":
        st.subheader("Semua Transaksi User")
        transactions = get_all_transactions()
        if not transactions:
            st.info("Belum ada transaksi.")
        else:
            for t in transactions:
                nickname, metode = (t[5].split("|", 1) + ["-"])[:2] if t[5] and "|" in t[5] else (t[5], "-")
                with st.expander(f"**{t[1]}** | {t[2]} - {t[3]} | Status: **{t[7]}**"):
                    st.write(f"**Waktu:** {t[8]}")
                    st.write(f"**Nickname:** {nickname} ({t[6]})")
                    st.write(f"**Paket:** {t[3]} (Rp {t[4]:,})")
                    st.write(f"**Metode Bayar:** {metode}")
                    status_options = ["Menunggu", "Diproses", "Selesai", "Gagal"]
                    current_index = status_options.index(t[7]) if t[7] in status_options else 0
                    col1, col2 = st.columns(2)
                    with col1:
                        new_status = st.selectbox("Update Status", status_options, index=current_index, key=f"status_{t[0]}")
                    with col2:
                        if st.button("Update", key=f"up_{t[0]}", use_container_width=True):
                            update_transaction_status(t[0], new_status)
                            st.rerun()
    elif sub_menu == "Kelola User":
        st.subheader("Daftar User Terdaftar")
        users = get_all_users()
        if not users:
            st.info("Belum ada user yang terdaftar selain admin.")
        else:
            for user in users:
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1: st.write(f"**Username:** {user[1]}")
                with col2: st.write(f"**Role:** {user[2]}")
                with col3:
                    if st.button("Hapus", key=f"deluser_{user[0]}", use_container_width=True, type="primary"):
                        delete_user(user[0])
                        st.success(f"User {user[1]} dan riwayat transaksinya telah dihapus.")
                        st.rerun()

# --- UI: HALAMAN USER (VERSI PERBAIKAN) ---
def user_page():
    # ==================== BLOK PERBAIKAN DIMULAI DI SINI ====================

    # 1. Jalankan auto-refresh secara global di halaman pengguna
    # Interval 5 detik (5000 milidetik)
    st_autorefresh(interval=5000, key="global_user_refresh")

    # 2. Buat fungsi helper untuk cek notifikasi (lebih rapi)
    def check_and_notify(username):
        # Inisialisasi state jika belum ada
        if 'last_statuses' not in st.session_state:
            # Saat pertama kali, isi state dengan data saat ini agar tidak ada notif palsu
            st.session_state.last_statuses = {str(t[0]): t[7] for t in get_user_transactions(username)}
            return # Keluar dari fungsi di pemuatan pertama

        # Ambil transaksi terbaru dari DB
        latest_transactions = get_user_transactions(username)
        current_statuses = {str(t[0]): t[7] for t in latest_transactions}

        # Bandingkan status baru dengan yang tersimpan di session_state
        for trans_id, new_status in current_statuses.items():
            old_status = st.session_state.last_statuses.get(trans_id)

            # Jika transaksi baru atau statusnya berubah
            if old_status != new_status:
                if old_status is not None:  # Ini adalah perubahan status, bukan pesanan baru
                    st.toast(f"🎉 Pesanan #{trans_id} kini berstatus: **{new_status}**", icon="🔔")
                # Perbarui state agar notifikasi tidak muncul berulang kali
                st.session_state.last_statuses[trans_id] = new_status
    
    # 3. Jalankan pengecekan notifikasi di setiap refresh
    check_and_notify(st.session_state['user'])
    
    # ==================== AKHIR BLOK PERBAIKAN ====================

    # Sisa dari UI Halaman Pengguna (tidak berubah)
    st.sidebar.title("MENU PENGGUNA")
    page = st.sidebar.radio("Navigasi", ["Pesan Top Up", "Riwayat Transaksi", "Profil Saya"])
    if st.sidebar.button("Logout", use_container_width=True):
        clear_session()
        st.rerun()

    if page == "Profil Saya":
        st.title("👤 Profil Saya")
        user_data = get_user_data(st.session_state['user'])
        st.subheader("Ubah Password")
        with st.form("change_password_form", clear_on_submit=True):
            new_pass = st.text_input("Password Baru", type="password")
            confirm_pass = st.text_input("Konfirmasi Password Baru", type="password")
            submit_pass = st.form_submit_button("Ganti Password")
            if submit_pass:
                if new_pass and new_pass == confirm_pass:
                    update_user_password(st.session_state['user'], new_pass)
                    st.success("Password berhasil diubah!")
                else:
                    st.error("Password tidak cocok atau kosong!")
        st.markdown("---")
        st.subheader("Simpan ID Game Default")
        st.caption("Isi ID game Anda di sini agar terisi otomatis saat melakukan top up.")
        with st.form("save_id_form"):
            default_ml_id = user_data[4] if user_data and user_data[4] else ""
            default_ff_id = user_data[5] if user_data and user_data[5] else ""
            ml_id = st.text_input("ID Game Mobile Legends", value=default_ml_id)
            ff_id = st.text_input("ID Game Free Fire", value=default_ff_id)
            submit_id = st.form_submit_button("Simpan ID")
            if submit_id:
                update_user_game_ids(st.session_state['user'], ml_id, ff_id)
                st.success("ID Game berhasil disimpan!")

    elif page == "Pesan Top Up":
        st.title("🛒 Pilih & Pesan Top Up")
        if "user_selected_game" not in st.session_state:
            st.session_state.user_selected_game = None
        if st.session_state.user_selected_game is None:
            st.subheader("1. Pilih Game Anda")
            db_products = get_products()
            game_images = {}
            available_games = []
            for p in db_products:
                if p[1] not in game_images and p[4] and os.path.isfile(p[4]):
                    game_images[p[1]] = p[4]
                if p[1] not in available_games:
                    available_games.append(p[1])
            if not available_games:
                st.warning("Saat ini belum ada produk game yang tersedia.")
                return
            cols = st.columns(len(available_games))
            for i, game in enumerate(available_games):
                with cols[i]:
                    if game in game_images:
                        st.image(game_images[game])
                    else:
                        st.image("https://via.placeholder.com/150", caption=f"{game} (Gambar tidak ditemukan)")
                    if st.button(game, use_container_width=True, key=f"game_{game}"):
                        st.session_state.user_selected_game = game
                        st.rerun()
            return
        selected_game = st.session_state.user_selected_game
        st.info(f"Anda memilih: **{selected_game}**. Klik tombol di bawah untuk ganti game.")
        if st.button("⬅️ Pilih Game Lain"):
            st.session_state.user_selected_game = None
            st.session_state.selected_product = None
            st.rerun()
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("2. Pilih Paket Top Up")
            game_products = [p for p in get_products() if p[1] == selected_game]
            if not game_products:
                st.warning("Produk untuk game ini belum tersedia.")
            else:
                for p in game_products:
                    if st.button(f"{p[2]} - Rp {p[3]:,}", key=f"choose_{p[0]}", use_container_width=True):
                        st.session_state.selected_product = p
                        st.rerun()
        with col2:
            st.subheader("3. Isi Data & Bayar")
            if "selected_product" in st.session_state and st.session_state.selected_product:
                product = st.session_state.selected_product
                st.write(f"Pilihan Anda: **{product[2]}**")
                st.write(f"Harga: **Rp {product[3]:,}**")
                user_data = get_user_data(st.session_state['user'])
                default_id = ""
                if product[1] == "Mobile Legends":
                    default_id = user_data[4] if user_data and user_data[4] else ""
                elif product[1] == "Free Fire":
                    default_id = user_data[5] if user_data and user_data[5] else ""
                with st.form("form_topup", clear_on_submit=True):
                    nickname = st.text_input("Nickname Game")
                    game_id = st.text_input("User ID (Zone ID jika ada)", value=default_id)
                    pay_method = st.radio("Metode Pembayaran", ["DANA", "GOPAY"], horizontal=True)
                    submit = st.form_submit_button("Beli Sekarang", use_container_width=True)
                    if submit:
                        if not nickname or not game_id:
                            st.warning("Nickname dan User ID harus diisi!")
                        else:
                            add_transaction(st.session_state["user"], product[1], product[2], product[3], f"{nickname}|{pay_method}", game_id)
                            st.success("Pesanan berhasil dibuat! Cek Riwayat Transaksi untuk status.")
                            del st.session_state.selected_product
            else:
                st.info("Pilih paket di sebelah kiri untuk melanjutkan.")
    
    elif page == "Riwayat Transaksi":
        st.title("📜 Riwayat Transaksi Anda")
        transactions = get_user_transactions(st.session_state["user"])
        if not transactions:
            st.info("Anda belum memiliki riwayat transaksi.")
        else:
            for t in transactions:
                nickname, metode = (t[5].split("|", 1) + ["-"])[:2] if t[5] and "|" in t[5] else (t[5], "-")
                with st.container(border=True):
                    st.write(f"#### {t[2]} - {t[3]}")
                    status_color = {"Selesai": "green", "Diproses": "orange", "Gagal": "red"}.get(t[7], "gray")
                    st.write(f"Status: **<span style='color:{status_color};'>{t[7]}</span>**", unsafe_allow_html=True)
                    st.write(f"**ID Transaksi:** {t[0]}")
                    st.write(f"**ID Game:** {t[6]} ({nickname})")
                    st.write(f"**Harga:** Rp {t[4]:,}")
                    st.write(f"**Waktu Pesan:** {t[8]}")

# --- LOGIKA UTAMA APLIKASI ---
def main():
    """Fungsi utama untuk menjalankan aplikasi."""
    st.set_page_config(page_title="TopUpGame", layout="wide", initial_sidebar_state="expanded")
    create_tables()
    seed_admin()
    if "user" not in st.session_state:
        login_register_menu()
    else:
        st.sidebar.success(f"Login sebagai: **{st.session_state['user']}**")
        st.sidebar.caption(f"Role: {st.session_state['role']}")
        st.sidebar.markdown("---")
        if st.session_state["role"] == "admin":
            admin_page()
        else:
            user_page()

if __name__ == "__main__":
    main()