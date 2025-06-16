import streamlit as st
import hashlib
import uuid
from PIL import Image
from streamlit_autorefresh import st_autorefresh
from supabase import create_client, Client
from io import BytesIO

# --- KONFIGURASI APLIKASI ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except KeyError:
    st.error("Kesalahan: Kunci Supabase tidak ditemukan. Harap tambahkan ke .streamlit/secrets.toml dan refresh halaman.")
    st.stop()

# --- FUNGSI HELPER & CRUD ---
def hash_password(password):
    """Hashing password menggunakan SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def upload_image_to_storage(file_uploader_object, bucket_name):
    """Fungsi generik untuk upload gambar ke Supabase Storage."""
    try:
        file_bytes = file_uploader_object.getvalue()
        unique_filename = f"{uuid.uuid4().hex}.jpg"
        
        img = Image.open(file_uploader_object)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        buf = BytesIO()
        img.save(buf, format='JPEG')
        file_bytes = buf.getvalue()

        supabase.storage.from_(bucket_name).upload(unique_filename, file_bytes, {'contentType': 'image/jpeg'})
        
        res = supabase.storage.from_(bucket_name).get_public_url(unique_filename)
        return res
    except Exception as e:
        st.error(f"Error saat mengupload file: {e}")
        return None

def upload_payment_proof(transaction_id, uploaded_file):
    """Uploads payment proof dan update record transaksi."""
    # Kita bisa gunakan bucket yang sama atau buat bucket baru khusus bukti bayar.
    # Untuk kemudahan, kita gunakan bucket yang sama.
    proof_url = upload_image_to_storage(uploaded_file, "product-images") 
    if proof_url:
        # Update status menjadi 'Diproses' setelah user upload bukti
        supabase.table("transactions").update({
            "payment_proof_url": proof_url, 
            "status": "Diproses"
        }).eq("id", transaction_id).execute()
        st.success("Bukti pembayaran berhasil diunggah! Status pesanan diubah menjadi 'Diproses'.")
        # Hapus state agar tidak memicu upload berulang
        if f"proof_{transaction_id}" in st.session_state:
            del st.session_state[f"proof_{transaction_id}"]
        st.rerun()
    else:
        st.error("Gagal mengunggah bukti pembayaran.")

# ... (Fungsi CRUD lainnya: register_user, login_user, dll) ...
def register_user(username, password):
    try:
        user_data = {"username": username, "password_hash": hash_password(password), "role": "user"}
        supabase.table("users").insert(user_data).execute()
        return True
    except Exception:
        return False
def login_user(username, password):
    hashed_password = hash_password(password)
    response = supabase.table("users").select("*").eq("username", username).eq("password_hash", hashed_password).execute()
    return response.data[0] if response.data else None
def get_user_data(username):
    response = supabase.table("users").select("*").eq("username", username).execute()
    return response.data[0] if response.data else None
def update_user_password(username, new_password):
    supabase.table("users").update({"password_hash": hash_password(new_password)}).eq("username", username).execute()
def update_user_game_ids(username, ml_id, ff_id):
    supabase.table("users").update({"default_ml_id": ml_id, "default_ff_id": ff_id}).eq("username", username).execute()
def add_product(game, paket, harga, image_path):
    supabase.table("products").insert({"game": game, "paket": paket, "harga": harga, "image_path": image_path}).execute()
def get_products():
    return supabase.table("products").select("*").order("game").order("harga").execute().data
def update_product(product_id, paket, harga, image_path):
    supabase.table("products").update({"paket": paket, "harga": harga, "image_path": image_path}).eq("id", product_id).execute()
def delete_product(product_id):
    supabase.table("products").delete().eq("id", product_id).execute()
def add_transaction(username, game, paket, harga, user_nickname, user_game_id, status="Menunggu"):
    trans_data = {"username": username, "game": game, "paket": paket, "harga": harga, "user_nickname": user_nickname, "user_game_id": user_game_id, "status": status}
    return supabase.table("transactions").insert(trans_data).execute().data[0]
def get_user_transactions(username):
    return supabase.table("transactions").select("*").eq("username", username).order("waktu", desc=True).execute().data
def get_all_transactions():
    return supabase.table("transactions").select("*").order("waktu", desc=True).execute().data
def update_transaction_status(trans_id, status):
    supabase.table("transactions").update({"status": status}).eq("id", trans_id).execute()
# ... (akhir blok fungsi CRUD) ...

# --- MANAJEMEN SESSION STATE ---
def clear_session():
    keys_to_clear = ["user", "role", "user_selected_game", "selected_product", "last_statuses", "pending_payment"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

# --- UI: HALAMAN LOGIN & REGISTRASI ---
def login_register_menu():
    st.sidebar.title("🎮 TopUpGame")
    menu = st.sidebar.selectbox("Menu", ["Login", "Register"])
    st.title("Selamat Datang di TopUpGame")
    # ... (sisa UI login & register tidak berubah) ...
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
                        st.error("Username mungkin sudah digunakan.")
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
    sub_menu = st.sidebar.radio("Menu", ["Daftar Transaksi", "Kelola Produk"])
    if st.sidebar.button("Logout", use_container_width=True):
        clear_session()
        st.rerun()
    st.title("Admin Dashboard")

    if sub_menu == "Daftar Transaksi":
        st.subheader("Semua Transaksi User")
        transactions = get_all_transactions()
        if not transactions:
            st.info("Belum ada transaksi.")
        else:
            for t in transactions:
                nickname, metode = (t['user_nickname'].split("|", 1) + ["-"])[:2] if t['user_nickname'] else (t['user_nickname'], "-")
                with st.expander(f"ID: {t['id']} | **{t['username']}** | {t['game']} | Status: **{t['status']}**"):
                    st.write(f"**Waktu:** {t['waktu']}")
                    st.write(f"**Nickname:** {nickname} ({t['user_game_id']})")
                    st.write(f"**Paket:** {t['paket']} (Rp {t['harga']:,})")
                    st.write(f"**Metode Bayar:** {metode}")
                    
                    if t.get('payment_proof_url'):
                        st.markdown("**Bukti Pembayaran:**")
                        st.image(t['payment_proof_url'], width=300)
                    else:
                        st.caption("User belum mengunggah bukti pembayaran.")
                    
                    st.markdown("---")
                    status_options = ["Menunggu", "Diproses", "Selesai", "Gagal"]
                    current_index = status_options.index(t['status']) if t['status'] in status_options else 0
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        new_status = st.selectbox("Update Status", status_options, index=current_index, key=f"status_{t['id']}")
                    with col2:
                        if st.button("Update", key=f"up_{t['id']}", use_container_width=True):
                            update_transaction_status(t['id'], new_status)
                            st.rerun()
    
    elif sub_menu == "Kelola Produk":
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
                    image_url = upload_image_to_storage(uploaded_image, "product-images")
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
            # ... UI Kelola produk tetap sama ...
            pass 

# --- UI: HALAMAN USER ---
def user_page():
    st_autorefresh(interval=7000, key="global_user_refresh")
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
        # ... UI Profil Saya tidak berubah ...
        pass
    
    elif page == "Pesan Top Up":
        st.title("🛒 Pilih & Pesan Top Up")
        
        # Cek jika ada pembayaran yang tertunda
        if 'pending_payment' in st.session_state:
            pending_trans = st.session_state.pending_payment
            st.info("Langkah Terakhir: Lakukan Pembayaran")
            st.markdown(f"""
            Pesanan Anda untuk **{pending_trans['paket']}** telah dibuat.
            Silakan transfer sejumlah **Rp {pending_trans['harga']:,}** ke nomor **DANA/GOPAY** di bawah ini:
            ### 📞 **089633436959**
            
            **PENTING:** Setelah transfer berhasil, buka menu **Riwayat Transaksi** dan unggah bukti pembayaran Anda pada pesanan yang sesuai (ID Transaksi: `{pending_trans['id']}`).
            """)
            if st.button("Saya Sudah Mengerti, Kembali ke Menu"):
                del st.session_state.pending_payment
                st.rerun()
            return # Hentikan eksekusi agar tidak menampilkan pilihan produk lagi

        # ... (sisa UI Pesan Top Up, mulai dari pemilihan game) ...
        # ... (sama seperti kode sebelumnya) ...
        col1, col2 = st.columns(2)
        with col2:
            st.subheader("3. Isi Data & Pesan")
            if "selected_product" in st.session_state and st.session_state.selected_product:
                product = st.session_state.selected_product
                st.write(f"Pilihan Anda: **{product['paket']}**")
                st.write(f"Harga: **Rp {product['harga']:,}**")
                
                with st.form("form_topup"):
                    nickname = st.text_input("Nickname Game")
                    game_id = st.text_input("User ID (Zone ID jika ada)")
                    pay_method = st.radio("Pilih Metode Pembayaran", ["DANA", "GOPAY"], horizontal=True)
                    submit = st.form_submit_button("Pesan Sekarang", use_container_width=True)

                    if submit:
                        if not nickname or not game_id:
                            st.warning("Nickname dan User ID harus diisi!")
                        else:
                            new_transaction = add_transaction(st.session_state["user"], product['game'], product['paket'], product['harga'], f"{nickname}|{pay_method}", game_id)
                            st.session_state.pending_payment = new_transaction # Simpan info transaksi untuk ditampilkan
                            del st.session_state.selected_product
                            st.rerun()
            else:
                st.info("Pilih paket di sebelah kiri untuk melanjutkan.")
    
    elif page == "Riwayat Transaksi":
        st.title("📜 Riwayat Transaksi Anda")
        transactions = get_user_transactions(st.session_state["user"])
        if not transactions:
            st.info("Anda belum memiliki riwayat transaksi.")
        else:
            for t in transactions:
                nickname, metode = (t['user_nickname'].split("|", 1) + ["-"])[:2] if t['user_nickname'] else (t['user_nickname'], "-")
                with st.container(border=True):
                    st.write(f"#### {t['paket']} (ID: {t['id']})")
                    st.write(f"**ID Game:** {t['user_game_id']} ({nickname}) | **Harga:** Rp {t['harga']:,}")
                    
                    status_color = {"Selesai": "green", "Diproses": "orange", "Gagal": "red"}.get(t['status'], "gray")
                    st.write(f"Status: **<span style='color:{status_color};'>{t['status']}</span>**", unsafe_allow_html=True)
                    
                    if t['status'] == 'Menunggu':
                        st.markdown("**Aksi Dibutuhkan:**")
                        uploaded_proof = st.file_uploader(
                            "Unggah Bukti Pembayaran Anda di sini",
                            type=["png", "jpg", "jpeg"],
                            key=f"proof_{t['id']}"
                        )
                        if uploaded_proof:
                            upload_payment_proof(t['id'], uploaded_proof)
                    
                    if t.get('payment_proof_url'):
                        with st.expander("Lihat Bukti Pembayaran Anda"):
                            st.image(t['payment_proof_url'])

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
