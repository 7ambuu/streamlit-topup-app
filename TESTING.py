import streamlit as st
import hashlib
import uuid
from PIL import Image
from streamlit_autorefresh import st_autorefresh
from supabase import create_client, Client
from io import BytesIO
import numpy as np

# --- KONFIGURASI APLIKASI ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except (KeyError, AttributeError):
    st.error("Kesalahan: Kunci Supabase tidak ditemukan. Harap tambahkan ke .streamlit/secrets.toml dan di pengaturan Streamlit Cloud.")
    st.stop()

# --- FUNGSI HELPER & CRUD ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def upload_image_to_storage(file_uploader_object, bucket_name):
    try:
        file_bytes = file_uploader_object.getvalue()
        unique_filename = f"{uuid.uuid4().hex}.jpg"
        img = Image.open(file_uploader_object)
        if img.mode == 'RGBA': img = img.convert('RGB')
        buf = BytesIO()
        img.save(buf, format='JPEG')
        file_bytes = buf.getvalue()
        supabase.storage.from_(bucket_name).upload(unique_filename, file_bytes, {'contentType': 'image/jpeg'})
        return supabase.storage.from_(bucket_name).get_public_url(unique_filename)
    except Exception as e:
        st.error(f"Error saat mengupload file: {e}")
        return None

def upload_payment_proof(transaction_id, uploaded_file):
    proof_url = upload_image_to_storage(uploaded_file, "product-images") 
    if proof_url:
        supabase.table("transactions").update({"payment_proof_url": proof_url, "status": "Diproses"}).eq("id", transaction_id).execute()
        st.success("Bukti pembayaran berhasil diunggah!")
        if f"proof_{transaction_id}" in st.session_state: del st.session_state[f"proof_{transaction_id}"]
        st.rerun()

# --- Fungsi CRUD untuk Game ---
def get_games():
    return supabase.table("games").select("*").order("name").execute().data
def add_game(name, description, logo_url):
    return supabase.table("games").insert({"name": name, "description": description, "logo_url": logo_url}).execute()
def update_game(game_id, name, description, logo_url):
    return supabase.table("games").update({"name": name, "description": description, "logo_url": logo_url}).eq("id", game_id).execute()
def delete_game(game_id):
    return supabase.table("games").delete().eq("id", game_id).execute()

# --- Fungsi CRUD untuk User ---
def register_user(username, password):
    try:
        supabase.table("users").insert({"username": username, "password_hash": hash_password(password), "role": "user"}).execute()
        return True
    except Exception: return False
def login_user(username, password):
    response = supabase.table("users").select("*").eq("username", username).eq("password_hash", hash_password(password)).execute()
    return response.data[0] if response.data else None
def get_user_data(username):
    response = supabase.table("users").select("*").eq("username", username).execute()
    return response.data[0] if response.data else None
def update_user_password(username, new_password):
    supabase.table("users").update({"password_hash": hash_password(new_password)}).eq("username", username).execute()
def update_user_game_ids(username, ml_id, ff_id):
    supabase.table("users").update({"default_ml_id": ml_id, "default_ff_id": ff_id}).eq("username", username).execute()

# --- Fungsi CRUD untuk Produk ---
def add_product(game_id, paket, harga):
    supabase.table("products").insert({"game_id": game_id, "paket": paket, "harga": harga}).execute()
def get_products_with_game_info():
    return supabase.table("products").select("*, games(name, logo_url)").order("id", desc=True).execute().data
def update_product(product_id, game_id, paket, harga):
    return supabase.table("products").update({"game_id": game_id, "paket": paket, "harga": harga}).eq("id", product_id).execute()
def delete_product(product_id):
    supabase.table("products").delete().eq("id", product_id).execute()

# --- Fungsi CRUD untuk Transaksi ---
def add_transaction(username, game_name, paket, harga, user_nickname, user_game_id, status="Menunggu"):
    trans_data = {"username": username, "game": game_name, "paket": paket, "harga": harga, "user_nickname": user_nickname, "user_game_id": user_game_id, "status": status}
    return supabase.table("transactions").insert(trans_data).execute().data[0]
def get_user_transactions(username):
    return supabase.table("transactions").select("*").eq("username", username).order("waktu", desc=True).execute().data
def get_all_transactions():
    return supabase.table("transactions").select("*").order("waktu", desc=True).execute().data
def update_transaction_status(trans_id, status):
    supabase.table("transactions").update({"status": status}).eq("id", trans_id).execute()

# --- Fungsi CRUD untuk Ulasan ---
def add_review(game_id, username, rating, comment):
    review_data = {"game_id": game_id, "username": username, "rating": rating, "comment": comment}
    return supabase.table("reviews").insert(review_data).execute()
def get_reviews_for_game(game_id):
    return supabase.table("reviews").select("*").eq("game_id", game_id).eq("is_visible", True).order("created_at", desc=True).execute().data
def get_all_reviews():
    return supabase.table("reviews").select("*, games(name)").order("created_at", desc=True).execute().data
def toggle_review_visibility(review_id, new_visibility):
    return supabase.table("reviews").update({"is_visible": new_visibility}).eq("id", review_id).execute()
def delete_review(review_id):
    return supabase.table("reviews").delete().eq("id", review_id).execute()

# --- MANAJEMEN SESSION STATE ---
def clear_session():
    keys_to_clear = ["user", "role", "user_selected_game", "selected_product", "last_statuses", "pending_payment", "editing_game_id", "editing_product_id"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

# --- UI: HALAMAN LOGIN & REGISTRASI ---
def login_register_menu():
    st.sidebar.title("🎮 TopUpGame")
    menu = st.sidebar.selectbox("Menu", ["Login", "Register"])
    st.title("Selamat Datang di TopUpGame")
    st.write("Platform Top Up Game Terpercaya")
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
                    if not username or not password: st.error("Username dan password tidak boleh kosong.")
                    elif register_user(username, password): st.success("Registrasi berhasil! Silakan pindah ke menu Login.")
                    else: st.error("Username mungkin sudah digunakan.")
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
    sub_menu = st.sidebar.radio("Menu", ["Daftar Transaksi", "Kelola Produk", "Kelola Game", "Kelola Ulasan"])
    if st.sidebar.button("Logout", use_container_width=True): clear_session(); st.rerun()
    st.title("Admin Dashboard")

    if 'editing_game_id' not in st.session_state: st.session_state.editing_game_id = None
    if 'editing_product_id' not in st.session_state: st.session_state.editing_product_id = None

    if sub_menu == "Kelola Ulasan":
        st.subheader("📝 Moderasi Ulasan Pengguna")
        st.write("Anda bisa menyembunyikan atau menghapus ulasan yang tidak pantas.")
        all_reviews = get_all_reviews()
        if not all_reviews:
            st.info("Belum ada ulasan dari pengguna.")
        else:
            for review in all_reviews:
                game_name = review['games']['name'] if review.get('games') else "N/A"
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{review['username']}** @ **{game_name}** ({'⭐' * review['rating']})")
                        st.caption(f"Komentar: *{review['comment']}*")
                        if not review['is_visible']:
                            st.warning("Ulasan ini sedang disembunyikan.", icon="⚠️")
                    with col2:
                        if review['is_visible']:
                            if st.button("Sembunyikan", key=f"hide_{review['id']}", use_container_width=True):
                                toggle_review_visibility(review['id'], False); st.rerun()
                        else:
                            if st.button("Tampilkan", key=f"show_{review['id']}", use_container_width=True):
                                toggle_review_visibility(review['id'], True); st.rerun()
                        if st.button("Hapus", key=f"del_rev_{review['id']}", type="primary", use_container_width=True):
                            delete_review(review['id']); st.rerun()

    elif sub_menu == "Kelola Game":
        st.subheader("🎮 Manajemen Game")
        with st.form("AddGameForm", clear_on_submit=True):
            st.markdown("**Tambah Game Baru**")
            game_name = st.text_input("Nama Game")
            game_desc = st.text_area("Deskripsi Singkat")
            game_logo = st.file_uploader("Upload Logo Game", type=["png", "jpg", "jpeg"])
            if st.form_submit_button("Tambah Game", type="primary"):
                if not all([game_name, game_logo]): st.warning("Nama Game dan Logo wajib diisi.")
                else:
                    logo_url = upload_image_to_storage(game_logo, "product-images")
                    if logo_url: add_game(game_name, game_desc, logo_url); st.success(f"Game '{game_name}' berhasil ditambahkan."); st.rerun()
        st.markdown("---")
        st.subheader("Daftar Game Saat Ini")
        games = get_games()
        if not games: st.info("Belum ada game yang ditambahkan.")
        else:
            for game in games:
                if st.session_state.editing_game_id == game['id']:
                    with st.container(border=True):
                        with st.form(key=f"edit_game_{game['id']}"):
                            st.write(f"**Mengubah Game: {game['name']}**")
                            new_name = st.text_input("Nama Game", value=game['name'])
                            new_desc = st.text_area("Deskripsi", value=game['description'])
                            new_logo = st.file_uploader("Ganti Logo (Kosongkan jika tidak ingin diubah)")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("Simpan", type="primary", use_container_width=True):
                                    logo_url = game['logo_url']
                                    if new_logo: logo_url = upload_image_to_storage(new_logo, "product-images")
                                    update_game(game['id'], new_name, new_desc, logo_url)
                                    st.success("Game diperbarui."); st.session_state.editing_game_id = None; st.rerun()
                            with col2:
                                if st.form_submit_button("Batal", use_container_width=True):
                                    st.session_state.editing_game_id = None; st.rerun()
                else:
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([1, 4, 1.2])
                        with col1: st.image(game['logo_url'], width=70)
                        with col2: st.markdown(f"**{game['name']}**"); st.caption(game['description'] or "Tidak ada deskripsi.")
                        with col3:
                            if st.button("Ubah", key=f"edit_game_{game['id']}", use_container_width=True): st.session_state.editing_game_id = game['id']; st.rerun()
                            if st.button("Hapus", key=f"del_game_{game['id']}", type="primary", use_container_width=True): delete_game(game['id']); st.success(f"Game {game['name']} dihapus."); st.rerun()

    elif sub_menu == "Kelola Produk":
        st.subheader("🛍️ Manajemen Produk")
        games_list = get_games()
        game_options = {game['id']: game['name'] for game in games_list}
        if not game_options: st.warning("Tidak bisa menambah produk. Silakan tambah data game di menu 'Kelola Game'.")
        else:
            with st.form("AddProductForm", clear_on_submit=True):
                st.markdown("**Tambah Produk Baru**")
                selected_game_id = st.selectbox("Pilih Game", options=list(game_options.keys()), format_func=lambda x: game_options[x])
                paket = st.text_input("Nama Paket (e.g., 100 Diamonds)")
                harga = st.number_input("Harga (Rp)", min_value=1000, step=500)
                if st.form_submit_button("Tambah Produk", type="primary"):
                    if not all([selected_game_id, paket, harga]): st.warning("Semua kolom wajib diisi.")
                    else: add_product(selected_game_id, paket, harga); st.success("Produk berhasil ditambahkan."); st.rerun()
            st.markdown("---")
            st.subheader("Daftar Produk Saat Ini")
            all_products = get_products_with_game_info()
            if not all_products: st.info("Belum ada produk.")
            else:
                for p in all_products:
                    if st.session_state.editing_product_id == p['id']:
                        with st.container(border=True):
                             with st.form(key=f"edit_prod_{p['id']}"):
                                st.write(f"**Mengubah Produk: {p['paket']}**")
                                game_ids = list(game_options.keys())
                                current_game_index = game_ids.index(p['game_id']) if p.get('game_id') in game_ids else 0
                                new_game_id = st.selectbox("Game", options=game_ids, format_func=lambda x: game_options[x], index=current_game_index)
                                new_paket = st.text_input("Nama Paket", value=p['paket'])
                                new_harga = st.number_input("Harga", value=p['harga'])
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("Simpan", type="primary", use_container_width=True):
                                        update_product(p['id'], new_game_id, new_paket, new_harga); st.success("Produk diperbarui."); st.session_state.editing_product_id = None; st.rerun()
                                with col2:
                                    if st.form_submit_button("Batal", use_container_width=True): st.session_state.editing_product_id = None; st.rerun()
                    else:
                        game_name = p['games']['name'] if p.get('games') else "Tanpa Game"
                        with st.container(border=True):
                            st.write(f"**{game_name}** - {p['paket']}")
                            st.write(f"Harga: Rp {p['harga']:,} | ID Produk: {p['id']}")
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                if st.button("Ubah", key=f"edit_prod_{p['id']}", use_container_width=True): st.session_state.editing_product_id = p['id']; st.rerun()
                            with col2:
                                if st.button("Hapus", key=f"del_prod_{p['id']}", use_container_width=True, type="primary"): delete_product(p['id']); st.rerun()

    elif sub_menu == "Daftar Transaksi":
        st.subheader("🧾 Daftar Transaksi")
        transactions = get_all_transactions()
        if not transactions: st.info("Belum ada transaksi.")
        else:
            for t in transactions:
                nickname, metode = (t['user_nickname'].split("|", 1) + ["-"])[:2] if t.get('user_nickname') else (t.get('user_nickname'), "-")
                expander_title = f"ID: {t['id']} | User: {t['username']} | Game: {t.get('game', 'N/A')} | Status: {t['status']}"
                with st.expander(expander_title):
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.markdown("**Bukti Pembayaran:**")
                        if t.get('payment_proof_url'): st.image(t['payment_proof_url'], use_container_width=True)
                        else: st.caption("Belum ada bukti bayar.")
                    with col2:
                        st.markdown(f"**Waktu Pesan:** `{t['waktu']}`")
                        st.markdown(f"**Nickname:** `{nickname}` ({t['user_game_id']})")
                        st.markdown(f"**Paket:** {t['paket']} (Rp {t['harga']:,})")
                        st.markdown(f"**Metode Bayar:** {metode}")
                    st.markdown("---")
                    st.markdown("**Update Status Pesanan:**")
                    form_col1, form_col2 = st.columns(2)
                    with form_col1:
                        status_options = ["Menunggu", "Diproses", "Selesai", "Gagal"]
                        current_index = status_options.index(t['status']) if t['status'] in status_options else 0
                        new_status = st.selectbox("Ubah Status ke:", options=status_options, index=current_index, key=f"status_{t['id']}")
                    with form_col2:
                        st.write("") 
                        st.write("")
                        if st.button("Simpan Perubahan", key=f"up_{t['id']}", use_container_width=True, type="primary"): update_transaction_status(t['id'], new_status); st.rerun()

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
            if old_status is not None and old_status != new_status: st.toast(f"🎉 Pesanan #{trans_id} kini berstatus: **{new_status}**", icon="🔔")
            st.session_state.last_statuses[trans_id] = new_status
    check_and_notify(st.session_state['user'])
    
    st.sidebar.title("MENU PENGGUNA")
    page = st.sidebar.radio("Navigasi", ["Pesan Top Up", "Riwayat Transaksi", "Profil Saya"])
    if st.sidebar.button("Logout", use_container_width=True): clear_session(); st.rerun()

    if page == "Profil Saya":
        st.title("👤 Profil Saya")
        user_data = get_user_data(st.session_state['user'])
        st.subheader("Ubah Password")
        with st.form("change_password_form", clear_on_submit=True):
            new_pass = st.text_input("Password Baru", type="password")
            if st.form_submit_button("Ganti Password"): update_user_password(st.session_state['user'], new_pass); st.success("Password berhasil diubah!")
        st.markdown("---")
        st.subheader("Simpan ID Game Default")
        with st.form("save_id_form"):
            default_ml_id = user_data.get('default_ml_id', '') if user_data else ""
            default_ff_id = user_data.get('default_ff_id', '') if user_data else ""
            ml_id = st.text_input("ID Game Mobile Legends", value=default_ml_id)
            ff_id = st.text_input("ID Game Free Fire", value=default_ff_id)
            if st.form_submit_button("Simpan ID"): update_user_game_ids(st.session_state['user'], ml_id, ff_id); st.success("ID Game berhasil disimpan!")
    
    elif page == "Pesan Top Up":
        st.title("🛒 Pilih & Pesan Top Up")
        if 'pending_payment' in st.session_state:
            pending_trans = st.session_state.pending_payment
            st.success(f"Pesanan (ID: {pending_trans['id']}) berhasil dibuat!")
            st.info("Langkah Terakhir: Lakukan Pembayaran")
            st.markdown(f"Silakan transfer sejumlah **Rp {pending_trans['harga']:,}** ke nomor **DANA/GOPAY** di bawah ini:\n### 📞 **089633436959**\n**PENTING:** Setelah transfer, buka menu **Riwayat Transaksi** dan unggah bukti pembayaran Anda.")
            if st.button("Saya Mengerti"): del st.session_state.pending_payment; st.rerun()
            return

        if "user_selected_game" not in st.session_state: st.session_state.user_selected_game = None
        if st.session_state.user_selected_game is None:
            st.subheader("1. Pilih Game Anda")
            games = get_games()
            if not games: st.warning("Belum ada game yang tersedia."); return
            cols = st.columns(len(games) or 1)
            for i, game in enumerate(games):
                with cols[i]:
                    st.image(game['logo_url']);
                    if st.button(game['name'], use_container_width=True, key=f"game_{game['id']}"): st.session_state.user_selected_game = game; st.rerun()
            return

        selected_game = st.session_state.user_selected_game
        st.info(f"Anda memilih: **{selected_game['name']}**.")
        if st.button("⬅️ Pilih Game Lain"): st.session_state.user_selected_game = None; st.session_state.selected_product = None; st.rerun()
        st.markdown("---")
        
        # Tampilkan Ulasan SEBELUM daftar produk
        st.subheader(f"Ulasan untuk {selected_game['name']}")
        game_reviews = get_reviews_for_game(selected_game['id'])
        if not game_reviews:
            st.info("Jadilah yang pertama memberikan ulasan untuk game ini!")
        else:
            ratings = [r['rating'] for r in game_reviews]
            avg_rating = np.mean(ratings) if ratings else 0
            st.write(f"**Rating Rata-rata:** {'⭐' * int(round(avg_rating))} ({avg_rating:.1f}/5 dari {len(ratings)} ulasan)")
            for review in game_reviews:
                with st.container(border=True):
                    st.markdown(f"**{review['username']}** - `{'⭐' * review['rating']}`")
                    st.caption(f"Komentar: *{review['comment']}*")

        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("2. Pilih Paket Top Up")
            all_products = get_products_with_game_info()
            game_products = [p for p in all_products if p.get('game_id') == selected_game['id']]
            if not game_products: st.warning("Produk untuk game ini belum tersedia.")
            else:
                for p in game_products:
                    if st.button(f"{p['paket']} - Rp {p['harga']:,}", key=f"choose_{p['id']}", use_container_width=True): st.session_state.selected_product = p; st.rerun()
        with col2:
            st.subheader("3. Isi Data & Pesan")
            if "selected_product" in st.session_state and st.session_state.selected_product:
                product = st.session_state.selected_product
                st.write(f"Pilihan: **{product['paket']}** | Harga: **Rp {product['harga']:,}**")
                with st.form("form_topup"):
                    nickname = st.text_input("Nickname Game")
                    game_id = st.text_input("User ID (Zone ID jika ada)")
                    pay_method = st.radio("Metode Pembayaran", ["DANA", "GOPAY"], horizontal=True)
                    if st.form_submit_button("Pesan Sekarang", use_container_width=True):
                        if not nickname or not game_id: st.warning("Nickname dan User ID harus diisi!")
                        else:
                            new_transaction = add_transaction(st.session_state["user"], selected_game['name'], product['paket'], product['harga'], f"{nickname}|{pay_method}", game_id)
                            st.session_state.pending_payment = new_transaction
                            del st.session_state.selected_product
                            st.rerun()
            else: st.info("Pilih paket di sebelah kiri untuk melanjutkan.")
        
        st.markdown("---")
        with st.expander("Tulis Ulasan Anda untuk Game Ini"):
            with st.form("review_form", clear_on_submit=True):
                rating_options = {1: "1 Bintang ⭐", 2: "2 Bintang ⭐⭐", 3: "3 Bintang ⭐⭐⭐", 4: "4 Bintang ⭐⭐⭐⭐", 5: "5 Bintang ⭐⭐⭐⭐⭐"}
                rating = st.selectbox("Beri Rating:", options=list(rating_options.keys()), format_func=lambda x: rating_options[x])
                comment = st.text_area("Komentar Anda:")
                if st.form_submit_button("Kirim Ulasan", type="primary"):
                    if rating and comment:
                        add_review(selected_game['id'], st.session_state['user'], rating, comment)
                        st.success("Terima kasih atas ulasan Anda!"); st.rerun()
                    else: st.warning("Harap isi rating dan komentar.")
    
    elif page == "Riwayat Transaksi":
        st.title("📜 Riwayat Transaksi Anda")
        transactions = get_user_transactions(st.session_state["user"])
        if not transactions: st.info("Anda belum memiliki riwayat transaksi.")
        else:
            for t in transactions:
                nickname, metode = (t['user_nickname'].split("|", 1) + ["-"])[:2] if t.get('user_nickname') else (t.get('user_nickname'), "-")
                with st.container(border=True):
                    st.write(f"#### {t['paket']} (ID Transaksi: {t['id']})")
                    st.write(f"**Game:** {t['game']} | **Harga:** Rp {t['harga']:,}")
                    status_color = {"Selesai": "green", "Diproses": "orange", "Gagal": "red"}.get(t['status'], "gray")
                    st.write(f"Status: **<span style='color:{status_color};'>{t['status']}</span>**", unsafe_allow_html=True)
                    if t['status'] == 'Menunggu':
                        st.markdown("**Aksi Dibutuhkan:**")
                        uploaded_proof = st.file_uploader("Unggah Bukti Pembayaran Anda", type=["png", "jpg", "jpeg"], key=f"proof_{t['id']}")
                        if uploaded_proof: upload_payment_proof(t['id'], uploaded_proof)
                    if t.get('payment_proof_url'):
                        with st.expander("Lihat Bukti Pembayaran"): st.image(t['payment_proof_url'])

# --- LOGIKA UTAMA APLIKASI ---
def main():
    st.set_page_config(page_title="TopUpGame Online", layout="wide", initial_sidebar_state="expanded")
    if "user" not in st.session_state: login_register_menu()
    else:
        st.sidebar.success(f"Login sebagai: **{st.session_state['user']}**")
        st.sidebar.caption(f"Role: {st.session_state['role']}")
        st.sidebar.markdown("---")
        if st.session_state["role"] == "admin": admin_page()
        else: user_page()

if __name__ == "__main__":
    main()
