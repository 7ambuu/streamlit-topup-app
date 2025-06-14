import streamlit as st
import hashlib
import os
import uuid
from PIL import Image
from streamlit_autorefresh import st_autorefresh
from supabase import create_client, Client # <-- IMPORT BARU

# --- KONFIGURASI APLIKASI ---
# Tidak ada lagi DB_NAME dan IMAGE_DIR, karena semua online.

# === PERUBAHAN BESAR: INISIALISASI KONEKSI SUPABASE ===
# Mengambil kunci rahasia dari file .streamlit/secrets.toml
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except KeyError:
    st.error("Kesalahan: Kunci Supabase tidak ditemukan. Harap tambahkan ke .streamlit/secrets.toml")
    st.stop()
# =======================================================


# --- FUNGSI HELPER & CRUD (DIUBAH TOTAL UNTUK SUPABASE) ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def save_uploaded_file(uploaded_file):
    """Menyimpan file ke Supabase Storage dan mengembalikan URL publiknya."""
    try:
        # Baca file sebagai bytes
        file_bytes = uploaded_file.getvalue()
        # Buat nama file unik
        unique_filename = f"{uuid.uuid4().hex}.jpg"
        
        # Upload ke Supabase Storage di bucket 'product-images'
        supabase.storage.from_("product-images").upload(unique_filename, file_bytes)
        
        # Dapatkan URL publik dari file yang baru diupload
        res = supabase.storage.from_("product-images").get_public_url(unique_filename)
        return res
    except Exception as e:
        st.error(f"Error saat mengupload file: {e}")
        return None

# Fungsi CRUD Users
def register_user(username, password):
    try:
        user_data = {
            "username": username,
            "password_hash": hash_password(password),
            "role": "user"
        }
        supabase.table("users").insert(user_data).execute()
        return True
    except Exception as e:
        # Jika username sudah ada, Supabase akan melempar error
        st.error(f"Username '{username}' sudah digunakan.")
        return False

def login_user(username, password):
    hashed_password = hash_password(password)
    response = supabase.table("users").select("*").eq("username", username).eq("password_hash", hashed_password).execute()
    if response.data:
        return response.data[0]
    return None

def get_user_data(username):
    response = supabase.table("users").select("*").eq("username", username).execute()
    if response.data:
        return response.data[0]
    return None

def update_user_password(username, new_password):
    hashed_password = hash_password(new_password)
    supabase.table("users").update({"password_hash": hashed_password}).eq("username", username).execute()

def update_user_game_ids(username, ml_id, ff_id):
    supabase.table("users").update({"default_ml_id": ml_id, "default_ff_id": ff_id}).eq("username", username).execute()

# Fungsi CRUD Products
def add_product(game, paket, harga, image_path):
    product_data = {"game": game, "paket": paket, "harga": harga, "image_path": image_path}
    supabase.table("products").insert(product_data).execute()

def get_products():
    response = supabase.table("products").select("*").order("game").order("harga").execute()
    return response.data

def update_product(product_id, paket, harga, image_path):
    update_data = {"paket": paket, "harga": harga, "image_path": image_path}
    supabase.table("products").update(update_data).eq("id", product_id).execute()

def delete_product(product_id):
    supabase.table("products").delete().eq("id", product_id).execute()

# Fungsi CRUD Transactions
def add_transaction(username, game, paket, harga, user_nickname, user_game_id, status="Menunggu"):
    trans_data = {
        "username": username, "game": game, "paket": paket, "harga": harga,
        "user_nickname": user_nickname, "user_game_id": user_game_id, "status": status
    }
    supabase.table("transactions").insert(trans_data).execute()

def get_user_transactions(username):
    response = supabase.table("transactions").select("*").eq("username", username).order("waktu", desc=True).execute()
    return response.data

def get_all_transactions():
    response = supabase.table("transactions").select("*").order("waktu", desc=True).execute()
    return response.data

def update_transaction_status(trans_id, status):
    supabase.table("transactions").update({"status": status}).eq("id", trans_id).execute()

# --- SISA KODE (UI, DLL) SEBAGIAN BESAR TETAP SAMA ---
# --- PERUBAHAN MINOR PADA BEBERAPA BAGIAN UI ---
def clear_session():
    keys_to_clear = ["user", "role", "user_selected_game", "selected_product", "last_statuses"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

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
            st.subheader("Login ke Akun Anda")
            with st.form("LoginForm"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    user = login_user(username, password)
                    if user:
                        st.session_state["user"] = user['username'] # PERUBAHAN: Mengakses data seperti dict
                        st.session_state["role"] = user['role']     # PERUBAHAN: Mengakses data seperti dict
                        st.rerun()
                    else:
                        st.error("Username atau password salah.")

def admin_page():
    st.sidebar.title("👑 ADMIN PANEL")
    sub_menu = st.sidebar.radio("Menu", ["Kelola Produk", "Daftar Transaksi"]) # Kelola User dihapus sementara
    if st.sidebar.button("Logout", use_container_width=True):
        clear_session()
        st.rerun()
    st.title("Admin Dashboard")

    # (Sisa UI Admin Page sebagian besar sama, hanya perlu penyesuaian akses data)
    # Contoh untuk Kelola Produk:
    if sub_menu == "Kelola Produk":
        st.subheader("Tambah Produk Baru")
        with st.form("AddProduct", clear_on_submit=True):
            game = st.selectbox("Pilih Game", ["Mobile Legends", "Free Fire"])
            paket = st.text_input("Nama Paket")
            harga = st.number_input("Harga (Rp)", min_value=1000, step=500)
            uploaded_image = st.file_uploader("Upload Gambar Produk", type=["png", "jpg", "jpeg"])
            submitted = st.form_submit_button("Tambah Produk")
            if submitted:
                if not all([game, paket, harga, uploaded_image]):
                    st.warning("Semua kolom dan gambar wajib diisi.")
                else:
                    image_url = save_uploaded_file(uploaded_image)
                    if image_url:
                        add_product(game, paket, harga, image_url)
                        st.success(f"Produk '{paket}' berhasil ditambahkan.")
                        st.rerun()
        st.markdown("---")
        st.subheader("Daftar Produk Saat Ini")
        products = get_products()
        if not products:
            st.info("Belum ada produk.")
        else:
            for p in products:
                with st.expander(f"**{p['game']}** - {p['paket']} (Rp {p['harga']:,})"):
                    # ... (UI untuk edit dan hapus disesuaikan dengan akses dict p['nama_kolom'])
                     col1, col2 = st.columns([1, 3])
                     with col1:
                        st.image(p['image_path'], width=100)
                     # ... Sisa UI Form Edit/Hapus
    # UI Daftar Transaksi juga disesuaikan
    elif sub_menu == "Daftar Transaksi":
        st.subheader("Semua Transaksi User")
        transactions = get_all_transactions()
        if not transactions:
            st.info("Belum ada transaksi.")
        else:
            for t in transactions:
                # PERUBAHAN: Akses data menggunakan key dict
                nickname, metode = (t['user_nickname'].split("|", 1) + ["-"])[:2] if t['user_nickname'] and "|" in t['user_nickname'] else (t['user_nickname'], "-")
                with st.expander(f"**{t['username']}** | {t['game']} - {t['paket']} | Status: **{t['status']}**"):
                    #... Sisa UI disesuaikan dengan akses dict t['nama_kolom']

def user_page():
    # === BLOK AUTO-REFRESH DAN NOTIFIKASI (SAMA SEPERTI SEBELUMNYA) ===
    st_autorefresh(interval=5000, key="global_user_refresh")
    def check_and_notify(username):
        if 'last_statuses' not in st.session_state:
            st.session_state.last_statuses = {str(t['id']): t['status'] for t in get_user_transactions(username)}
            return
        latest_transactions = get_user_transactions(username)
        current_statuses = {str(t['id']): t['status'] for t in latest_transactions}
        for trans_id, new_status in current_statuses.items():
            old_status = st.session_state.last_statuses.get(trans_id)
            if old_status != new_status:
                if old_status is not None:
                    st.toast(f"🎉 Pesanan #{trans_id} kini berstatus: **{new_status}**", icon="🔔")
                st.session_state.last_statuses[trans_id] = new_status
    check_and_notify(st.session_state['user'])
    
    # Sisa UI Halaman User sebagian besar sama, hanya penyesuaian akses data dict
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
        with st.form("save_id_form"):
            default_ml_id = user_data.get('default_ml_id', '') if user_data else ""
            default_ff_id = user_data.get('default_ff_id', '') if user_data else ""
            ml_id = st.text_input("ID Game Mobile Legends", value=default_ml_id)
            ff_id = st.text_input("ID Game Free Fire", value=default_ff_id)
            submit_id = st.form_submit_button("Simpan ID")
            if submit_id:
                update_user_game_ids(st.session_state['user'], ml_id, ff_id)
                st.success("ID Game berhasil disimpan!")

    # Sisa halaman user lainnya (Pesan Top Up, Riwayat) juga perlu penyesuaian
    # dalam cara mengakses data dari list of dictionaries.
    # Contoh: `t[0]` menjadi `t['id']`, `p[1]` menjadi `p['game']`, dst.

def main():
    st.set_page_config(page_title="TopUpGame Online", layout="wide", initial_sidebar_state="expanded")
    
    # Hapus create_tables() dan seed_admin() karena sudah di-handle di Supabase
    # create_tables()
    # seed_admin()

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