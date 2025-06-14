import streamlit as st
import hashlib
import uuid
from PIL import Image
from streamlit_autorefresh import st_autorefresh
from supabase import create_client, Client

# --- KONFIGURASI APLIKASI ---
# Mengambil kunci rahasia dari file .streamlit/secrets.toml
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except KeyError:
    st.error("Kesalahan: Kunci Supabase tidak ditemukan. Harap tambahkan ke .streamlit/secrets.toml dan refresh halaman.")
    st.stop()

# --- FUNGSI HELPER & CRUD (untuk Supabase) ---
def hash_password(password):
    """Hashing password menggunakan SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def save_uploaded_file(uploaded_file):
    """Menyimpan file ke Supabase Storage dan mengembalikan URL publiknya."""
    try:
        file_bytes = uploaded_file.getvalue()
        # Buat nama file unik dengan ekstensi .jpg
        unique_filename = f"{uuid.uuid4().hex}.jpg"
        
        # Konversi gambar ke RGB jika perlu sebelum menyimpan sebagai JPEG
        img = Image.open(uploaded_file)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
            # Simpan ke buffer byte setelah konversi
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, format='JPEG')
            file_bytes = buf.getvalue()

        # Upload ke Supabase Storage di bucket 'product-images'
        supabase.storage.from_("product-images").upload(unique_filename, file_bytes, {'contentType': 'image/jpeg'})
        
        # Dapatkan URL publik dari file yang baru diupload
        res = supabase.storage.from_("product-images").get_public_url(unique_filename)
        return res
    except Exception as e:
        st.error(f"Error saat mengupload file: {e}")
        return None

# Fungsi CRUD untuk Users
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
        st.error(f"Username '{username}' mungkin sudah digunakan atau ada kesalahan lain.")
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

# Fungsi CRUD untuk Products
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

# Fungsi CRUD untuk Transactions
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

# --- MANAJEMEN SESSION STATE ---
def clear_session():
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
            st.subheader("Login ke Akun Anda")
            with st.form("LoginForm"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    user = login_user(username, password)
                    if user:
                        st.session_state["user"] = user['username']
                        st.session_state["role"] = user['role']
                        st.rerun()
                    else:
                        st.error("Username atau password salah.")

# --- UI: HALAMAN ADMIN ---
def admin_page():
    st.sidebar.title("👑 ADMIN PANEL")
    sub_menu = st.sidebar.radio("Menu", ["Kelola Produk", "Daftar Transaksi"])
    if st.sidebar.button("Logout", use_container_width=True):
        clear_session()
        st.rerun()
    st.title("Admin Dashboard")

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
                     col1, col2 = st.columns([1, 3])
                     with col1:
                        st.image(p['image_path'], width=100)
                     with col2:
                        st.markdown(f"**ID Produk:** `{p['id']}`")
                        st.markdown(f"**Paket:** {p['paket']}")
                        st.markdown(f"**Harga:** Rp {p['harga']:,}")
                     st.markdown("##### Edit Produk Ini")
                     with st.form(key=f"edit_form_{p['id']}"):
                        new_paket = st.text_input("Nama Paket Baru", value=p['paket'])
                        new_harga = st.number_input("Harga Baru (Rp)", value=p['harga'], min_value=1000, step=500)
                        new_image = st.file_uploader("Ganti Gambar (Opsional)", type=["png", "jpg", "jpeg"], key=f"img_{p['id']}")
                        b_col1, b_col2 = st.columns(2)
                        with b_col1:
                           update_submitted = st.form_submit_button("Update Produk", use_container_width=True)
                        with b_col2:
                           delete_submitted = st.form_submit_button("Hapus Produk Ini", use_container_width=True, type="primary")
                        if update_submitted:
                            image_path = p['image_path']
                            if new_image is not None:
                                image_path = save_uploaded_file(new_image)
                            update_product(p['id'], new_paket, new_harga, image_path)
                            st.success("Produk berhasil diupdate!")
                            st.rerun()
                        if delete_submitted:
                            delete_product(p['id'])
                            st.success("Produk berhasil dihapus.")
                            st.rerun()
                            
    elif sub_menu == "Daftar Transaksi":
        st.subheader("Semua Transaksi User")
        transactions = get_all_transactions()
        if not transactions:
            st.info("Belum ada transaksi.")
        else:
            for t in transactions:
                nickname, metode = (t['user_nickname'].split("|", 1) + ["-"])[:2] if t['user_nickname'] and "|" in t['user_nickname'] else (t['user_nickname'], "-")
                with st.expander(f"**{t['username']}** | {t['game']} - {t['paket']} | Status: **{t['status']}**"):
                    st.write(f"**Waktu:** {t['waktu']}")
                    st.write(f"**Nickname:** {nickname} ({t['user_game_id']})")
                    st.write(f"**Paket:** {t['paket']} (Rp {t['harga']:,})")
                    st.write(f"**Metode Bayar:** {metode}")
                    status_options = ["Menunggu", "Diproses", "Selesai", "Gagal"]
                    current_index = status_options.index(t['status']) if t['status'] in status_options else 0
                    col1, col2 = st.columns(2)
                    with col1:
                        new_status = st.selectbox("Update Status", status_options, index=current_index, key=f"status_{t['id']}")
                    with col2:
                        if st.button("Update", key=f"up_{t['id']}", use_container_width=True):
                            update_transaction_status(t['id'], new_status)
                            st.rerun()

# --- UI: HALAMAN USER ---
def user_page():
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
            default_ml_id = user_data.get('default_ml_id', '') if user_data else ""
            default_ff_id = user_data.get('default_ff_id', '') if user_data else ""
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
                if p['game'] not in game_images and p['image_path']:
                    game_images[p['game']] = p['image_path']
                if p['game'] not in available_games:
                    available_games.append(p['game'])
            if not available_games:
                st.warning("Saat ini belum ada produk game yang tersedia.")
                return
            cols = st.columns(len(available_games))
            for i, game in enumerate(available_games):
                with cols[i]:
                    if game in game_images:
                        st.image(game_images[game])
                    else:
                        st.image("https://via.placeholder.com/150", caption=f"{game}")
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
            game_products = [p for p in get_products() if p['game'] == selected_game]
            if not game_products:
                st.warning("Produk untuk game ini belum tersedia.")
            else:
                for p in game_products:
                    if st.button(f"{p['paket']} - Rp {p['harga']:,}", key=f"choose_{p['id']}", use_container_width=True):
                        st.session_state.selected_product = p
                        st.rerun()
        with col2:
            st.subheader("3. Isi Data & Bayar")
            if "selected_product" in st.session_state and st.session_state.selected_product:
                product = st.session_state.selected_product
                st.write(f"Pilihan Anda: **{product['paket']}**")
                st.write(f"Harga: **Rp {product['harga']:,}**")
                user_data = get_user_data(st.session_state['user'])
                default_id = ""
                if product['game'] == "Mobile Legends":
                    default_id = user_data.get('default_ml_id', '') if user_data else ""
                elif product['game'] == "Free Fire":
                    default_id = user_data.get('default_ff_id', '') if user_data else ""
                with st.form("form_topup", clear_on_submit=True):
                    nickname = st.text_input("Nickname Game")
                    game_id = st.text_input("User ID (Zone ID jika ada)", value=default_id)
                    pay_method = st.radio("Metode Pembayaran", ["DANA", "GOPAY"], horizontal=True)
                    submit = st.form_submit_button("Beli Sekarang", use_container_width=True)
                    if submit:
                        if not nickname or not game_id:
                            st.warning("Nickname dan User ID harus diisi!")
                        else:
                            add_transaction(st.session_state["user"], product['game'], product['paket'], product['harga'], f"{nickname}|{pay_method}", game_id)
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
                nickname, metode = (t['user_nickname'].split("|", 1) + ["-"])[:2] if t['user_nickname'] and "|" in t['user_nickname'] else (t['user_nickname'], "-")
                with st.container(border=True):
                    st.write(f"#### {t['paket']}")
                    status_color = {"Selesai": "green", "Diproses": "orange", "Gagal": "red"}.get(t['status'], "gray")
                    st.write(f"Status: **<span style='color:{status_color};'>{t['status']}</span>**", unsafe_allow_html=True)
                    st.write(f"**ID Transaksi:** {t['id']}")
                    st.write(f"**ID Game:** {t['user_game_id']} ({nickname})")
                    st.write(f"**Harga:** Rp {t['harga']:,}")
                    st.write(f"**Waktu Pesan:** {t['waktu']}")

# --- LOGIKA UTAMA APLIKASI ---
def main():
    st.set_page_config(page_title="TopUpGame Online", layout="wide", initial_sidebar_state="expanded")
    
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
