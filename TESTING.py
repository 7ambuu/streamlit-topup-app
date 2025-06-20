import streamlit as st
import hashlib
import uuid
from PIL import Image
from streamlit_autorefresh import st_autorefresh
from supabase import create_client, Client
from io import BytesIO
import numpy as np
import time
from collections import Counter
from datetime import datetime
import pandas as pd

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
    with st.status("Mengunggah bukti pembayaran..."):
        proof_url = upload_image_to_storage(uploaded_file, "product-images") 
    if proof_url:
        supabase.table("transactions").update({"payment_proof_url": proof_url, "status": "Diproses"}).eq("id", transaction_id).execute()
        st.success("Bukti pembayaran berhasil diunggah!")
        st.session_state.pop('pending_payment', None)
        if f"proof_direct_{transaction_id}" in st.session_state: del st.session_state[f"proof_direct_{transaction_id}"]
        if f"proof_history_{transaction_id}" in st.session_state: del st.session_state[f"proof_history_{transaction_id}"]
        time.sleep(1)
        st.rerun()

@st.cache_data(ttl=300)
def to_excel(data: list) -> bytes:
    df = pd.DataFrame(data)
    for col in df.columns:
        if data and df[col].iloc[0] and isinstance(df[col].iloc[0], (dict, list)):
            df[col] = df[col].astype(str)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    processed_data = output.getvalue()
    return processed_data

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
    response = supabase.table("users").select("*").eq("username", username).limit(1).single().execute()
    return response.data
def update_user_password(username, new_password):
    supabase.table("users").update({"password_hash": hash_password(new_password)}).eq("username", username).execute()
def update_user_email(username, email):
    return supabase.table("users").update({"email": email}).eq("username", username).execute()
def get_all_users_for_admin():
    return supabase.table("users").select("id, username, role, email, created_at").neq("role", "admin").order("created_at", desc=True).execute().data
def delete_user_by_id(user_id):
    return supabase.table("users").delete().eq("id", user_id).execute()

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
def update_transaction_status(trans_id, status, reason=None):
    update_data = {"status": status}
    if status == 'Gagal':
        update_data['failure_reason'] = reason
    else:
        update_data['failure_reason'] = None
    supabase.table("transactions").update(update_data).eq("id", trans_id).execute()

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

# --- Fungsi CRUD untuk Kotak Pesan ---
def send_message(sender, recipient, content):
    if content:
        message_data = {"sender": sender, "recipient": recipient, "content": content}
        return supabase.table("messages").insert(message_data).execute()
def get_conversation(user1, user2):
    response1 = supabase.table("messages").select("*").eq("sender", user1).eq("recipient", user2).execute().data
    response2 = supabase.table("messages").select("*").eq("sender", user2).eq("recipient", user1).execute().data
    conversation = sorted(response1 + response2, key=lambda x: x['created_at'])
    return conversation
def get_conversations_for_admin():
    messages = supabase.table("messages").select("*").or_(f"recipient.eq.admin,sender.eq.admin").order("created_at", desc=True).execute().data
    conversations_summary = {}
    ordered_users = []
    for msg in messages:
        other_user = msg['sender'] if msg['recipient'] == 'admin' else msg['recipient']
        if other_user not in ordered_users:
            ordered_users.append(other_user)
            conversations_summary[other_user] = {"unread_count": 0, "last_message_time": msg['created_at']}
        if msg['recipient'] == 'admin' and not msg['is_read']:
            conversations_summary[other_user]['unread_count'] += 1
    sorted_users = sorted(conversations_summary.keys(), key=lambda u: conversations_summary[u]['last_message_time'], reverse=True)
    return conversations_summary, sorted_users
def mark_messages_as_read(recipient, sender):
    supabase.table("messages").update({"is_read": True}).eq("recipient", recipient).eq("sender", sender).execute()

# --- MANAJEMEN SESSION STATE ---
def clear_session():
    keys_to_clear = ["user", "role", "user_selected_game", "selected_product", "last_statuses", "pending_payment", "editing_game_id", "editing_product_id", "show_review_form", "visible_reviews_count", "selected_chat_user", "confirming_delete_user"]
    for key in keys_to_clear:
        if key in st.session_state: del st.session_state[key]

# --- UI: HALAMAN LOGIN & REGISTRASI ---
def login_register_menu():
    st.sidebar.title("✨ ARRA")
    st.sidebar.info("Silakan Login atau Register untuk melanjutkan.")
    st.title("Selamat Datang di ✨ ARRA")
    st.markdown("""
    **ARRA** hadir sebagai platform top up game terpercaya, 
    didirikan oleh **Azzam Risky Refando Arif** untuk memenuhi kebutuhan para gamer di Indonesia. 
    Kami berkomitmen untuk menyediakan layanan top up yang **cepat, aman, dan terjangkau** untuk berbagai game favorit Anda.

    Nikmati pengalaman top up tanpa ribet, dengan pilihan pembayaran yang beragam 
    dan dukungan pelanggan yang siap membantu. Bergabunglah dengan ribuan gamer lainnya 
    yang telah mempercayakan kebutuhan top up mereka kepada ARRA!
    """)
    st.divider()
    login_tab, register_tab = st.tabs(["🔑 Login", "✍️ Register"])
    with login_tab:
        with st.form("login_form"):
            st.markdown("##### Silakan login ke akun Anda")
            username = st.text_input("Username", placeholder="Masukkan username Anda")
            password = st.text_input("Password", type="password", placeholder="Masukkan password Anda")
            if st.form_submit_button("Login", use_container_width=True, type="primary"):
                with st.spinner("Mencocokkan data..."):
                    user = login_user(username, password)
                if user:
                    st.session_state["user"] = user['username']
                    st.session_state["role"] = user['role']
                    st.rerun()
                else:
                    st.error("Username atau password salah.")
    with register_tab:
        with st.form("register_form"):
            st.markdown("##### Belum punya akun? Daftar di sini!")
            reg_username = st.text_input("Username Baru", key="reg_username")
            reg_password = st.text_input("Password Baru", type="password", key="reg_password")
            if st.form_submit_button("Daftar Sekarang", use_container_width=True):
                if not reg_username or not reg_password:
                    st.error("Username dan password tidak boleh kosong.")
                else:
                    with st.spinner("Membuat akun baru..."):
                        success = register_user(reg_username, reg_password)
                    if success:
                        st.success("Registrasi berhasil! Silakan pindah ke tab Login untuk masuk.")
                        time.sleep(2)
                    else:
                        st.error("Username tersebut mungkin sudah digunakan.")

# --- UI: HALAMAN ADMIN ---
def admin_page():
    st.sidebar.title("✨ ARRA")
    st.sidebar.header("👑 ADMIN PANEL")
    sub_menu = st.sidebar.radio("Menu", ["📊 Laporan & Unduh Data", "🧾 Daftar Transaksi", "🛍️ Kelola Produk", "🎮 Kelola Game", "📝 Kelola Ulasan", "💬 Kotak Pesan", "👥 Kelola User"])
    if st.sidebar.button("Logout", use_container_width=True): clear_session(); st.rerun()
    st.header(f"{sub_menu}")
    st.divider()

    if 'editing_game_id' not in st.session_state: st.session_state.editing_game_id = None
    if 'editing_product_id' not in st.session_state: st.session_state.editing_product_id = None
    if 'selected_chat_user' not in st.session_state: st.session_state.selected_chat_user = None
    if 'confirming_delete_user' not in st.session_state: st.session_state.confirming_delete_user = None
    
    if sub_menu == "📊 Laporan & Unduh Data":
        st.write("Pilih dan unduh data dari database Anda dalam format Excel (.xlsx).")
        with st.container(border=True):
            st.subheader("Laporan Transaksi")
            with st.spinner("Menyiapkan data transaksi..."):
                transactions_data = get_all_transactions()
            if transactions_data:
                st.download_button(label="📥 Unduh Data Transaksi", data=to_excel(transactions_data),
                    file_name=f"laporan_transaksi_arra_{time.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            else: st.info("Belum ada data transaksi untuk diunduh.")
        with st.container(border=True):
            st.subheader("Data Produk (Termasuk Info Game)")
            with st.spinner("Menyiapkan data produk..."):
                products_data = get_products_with_game_info()
            if products_data:
                st.download_button(label="📥 Unduh Data Produk", data=to_excel(products_data),
                    file_name=f"data_produk_arra_{time.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            else: st.info("Belum ada data produk untuk diunduh.")
        with st.container(border=True):
            st.subheader("Data Pengguna")
            st.write("Berisi semua data pengguna yang terdaftar (termasuk email).")
            with st.spinner("Menyiapkan data pengguna..."):
                users_data = get_all_users_for_admin()
            if users_data:
                st.download_button(label="📥 Unduh Data Pengguna", data=to_excel(users_data),
                    file_name=f"data_pengguna_arra_{time.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            else: st.info("Belum ada data pengguna untuk diunduh.")

    elif sub_menu == "👥 Kelola User":
        st.write("Cari, lihat, dan hapus pengguna dari sistem.")
        search_user = st.text_input("🔍 Cari username pengguna...")
        all_users = get_all_users_for_admin()
        if search_user: all_users = [user for user in all_users if search_user.lower() in user['username'].lower()]
        if not all_users: st.info("Tidak ada pengguna yang cocok dengan pencarian Anda.")
        else:
            for user in all_users:
                with st.container(border=True):
                    if st.session_state.confirming_delete_user == user['id']:
                        st.warning(f"**Anda yakin ingin menghapus pengguna `{user['username']}` secara permanen?**")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("YA, HAPUS", key=f"confirm_del_{user['id']}", type="primary", use_container_width=True):
                                with st.status(f"Menghapus user {user['username']}..."): delete_user_by_id(user['id'])
                                st.session_state.confirming_delete_user = None; st.rerun()
                        with col2:
                             if st.button("Batal", key=f"cancel_del_{user['id']}", use_container_width=True): st.session_state.confirming_delete_user = None; st.rerun()
                    else:
                        col1, col2, col3, col4 = st.columns([2, 2, 2, 1.5])
                        with col1: st.markdown(f"**Username:** `{user['username']}`")
                        with col2: st.markdown(f"**Email:** `{user.get('email') or 'Belum diisi'}`")
                        with col3: st.caption(f"Daftar: {user.get('created_at', 'N/A')}")
                        with col4:
                            if st.button("Hapus User", key=f"del_user_{user['id']}", use_container_width=True):
                                st.session_state.confirming_delete_user = user['id']; st.rerun()
                                
    elif sub_menu == "💬 Kotak Pesan":
        conversations, ordered_users = get_conversations_for_admin()
        if not conversations: st.info("Belum ada pesan yang masuk dari pengguna."); return
        col1, col2 = st.columns([1, 2.5])
        with col1:
            st.markdown("**Percakapan Terbaru**")
            if st.session_state.selected_chat_user is None and ordered_users:
                st.session_state.selected_chat_user = ordered_users[0]
            selected_user_from_radio = st.radio("Pilih pengguna:", options=ordered_users,
                format_func=lambda u: f"💬 {u} ({conversations[u]['unread_count']} baru)" if conversations.get(u, {}).get('unread_count', 0) > 0 else f"✅ {u}",
                label_visibility="collapsed", index=ordered_users.index(st.session_state.selected_chat_user) if st.session_state.selected_chat_user in ordered_users else 0)
            if selected_user_from_radio != st.session_state.get('selected_chat_user'):
                st.session_state.selected_chat_user = selected_user_from_radio; st.rerun()
        with col2:
            chat_user = st.session_state.selected_chat_user
            if chat_user:
                st.info(f"Anda sedang membalas pesan dari **{chat_user}**.")
                mark_messages_as_read(recipient="admin", sender=chat_user)
                conversation = get_conversation("admin", chat_user)
                chat_container = st.container(height=400, border=True)
                with chat_container:
                    for msg in conversation:
                        role = "assistant" if msg['sender'] == 'admin' else "user"
                        avatar_icon = "👑" if role == "assistant" else "🧑‍💻"
                        with st.chat_message(role, avatar=avatar_icon):
                            st.write(msg['content']); st.caption(f"{datetime.fromisoformat(msg['created_at']).strftime('%d %b %Y, %H:%M')}")
                with st.form(key=f"reply_form_{chat_user}", clear_on_submit=True):
                    reply_content = st.text_area("Ketik balasan Anda:", height=100, label_visibility="collapsed", placeholder="Ketik balasan...")
                    if st.form_submit_button("Kirim Balasan", use_container_width=True, type="primary"):
                        send_message(sender="admin", recipient=chat_user, content=reply_content); st.rerun()
            else:
                st.write("Pilih percakapan untuk ditampilkan.")
    
    elif sub_menu == "📝 Kelola Ulasan":
        games = get_games(); game_options = {game['id']: game['name'] for game in games}; game_options[0] = "Semua Game"
        selected_game_id = st.selectbox("Filter ulasan berdasarkan game:", options=list(game_options.keys()), format_func=lambda x: game_options[x])
        st.divider()
        all_reviews = get_all_reviews()
        filtered_reviews = [r for r in all_reviews if selected_game_id == 0 or r.get('game_id') == selected_game_id]
        if not filtered_reviews: st.info("Tidak ada ulasan yang cocok dengan filter ini.")
        else:
            for review in filtered_reviews:
                game_name = review['games']['name'] if review.get('games') else "N/A"
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1]);
                    with col1:
                        st.markdown(f"**{review['username']}** @ **{game_name}** ({'⭐' * review['rating']})")
                        st.caption(f"Komentar: *{review['comment']}*")
                        if not review['is_visible']: st.warning("Ulasan ini sedang disembunyikan.", icon="⚠️")
                    with col2:
                        if review['is_visible']:
                            if st.button("Sembunyikan", key=f"hide_{review['id']}", use_container_width=True): toggle_review_visibility(review['id'], False); st.rerun()
                        else:
                            if st.button("Tampilkan", key=f"show_{review['id']}", use_container_width=True): toggle_review_visibility(review['id'], True); st.rerun()
                        if st.button("Hapus", key=f"del_rev_{review['id']}", type="primary", use_container_width=True): delete_review(review['id']); st.rerun()
                            
    elif sub_menu == "🎮 Kelola Game":
        list_tab, add_tab = st.tabs(["Daftar Game", "➕ Tambah Game Baru"])
        with add_tab:
            with st.form("AddGameForm", clear_on_submit=True):
                st.markdown("**Formulir Game Baru**"); game_name = st.text_input("Nama Game")
                game_desc = st.text_area("Deskripsi Singkat"); game_logo = st.file_uploader("Upload Logo Game", type=["png", "jpg", "jpeg"])
                if st.form_submit_button("Tambah Game", type="primary", use_container_width=True):
                    if not all([game_name, game_logo]): st.warning("Nama Game dan Logo wajib diisi.")
                    else:
                        with st.status("Menambahkan game baru...", expanded=False) as status:
                            logo_url = upload_image_to_storage(game_logo, "product-images")
                            if logo_url: add_game(game_name, game_desc, logo_url); status.update(label=f"Game '{game_name}' berhasil ditambahkan.", state="complete")
                            else: status.update(label="Gagal mengupload logo.", state="error")
                        time.sleep(1); st.rerun()
        with list_tab:
            st.markdown("**Daftar Game Saat Ini**"); games = get_games()
            if not games: st.info("Belum ada game yang ditambahkan.")
            else:
                for game in games:
                    if st.session_state.editing_game_id == game['id']:
                        with st.container(border=True):
                            with st.form(key=f"edit_game_{game['id']}"):
                                st.write(f"**Mengubah Game: {game['name']}**"); new_name = st.text_input("Nama Game", value=game['name'])
                                new_desc = st.text_area("Deskripsi", value=game['description']); new_logo = st.file_uploader("Ganti Logo (Kosongkan jika tidak ingin diubah)")
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("Simpan", type="primary", use_container_width=True):
                                        with st.status("Memperbarui data...", expanded=False) as status:
                                            logo_url = game['logo_url']
                                            if new_logo: logo_url = upload_image_to_storage(new_logo, "product-images")
                                            update_game(game['id'], new_name, new_desc, logo_url); status.update(label="Game diperbarui.", state="complete")
                                        st.session_state.editing_game_id = None; time.sleep(1); st.rerun()
                                with col2:
                                    if st.form_submit_button("Batal", use_container_width=True): st.session_state.editing_game_id = None; st.rerun()
                    else:
                        with st.container(border=True):
                            col1, col2, col3 = st.columns([1, 4, 1.5]);
                            with col1: st.image(game['logo_url'], width=70)
                            with col2: st.markdown(f"**{game['name']}**"); st.caption(game['description'] or "Tidak ada deskripsi.")
                            with col3:
                                if st.button("Ubah", key=f"edit_game_{game['id']}", use_container_width=True): st.session_state.editing_game_id = game['id']; st.rerun()
                                if st.button("Hapus", key=f"del_game_{game['id']}", type="primary", use_container_width=True): delete_game(game['id']); st.success(f"Game {game['name']} dihapus."); st.rerun()

    elif sub_menu == "🛍️ Kelola Produk":
        list_tab, add_tab = st.tabs(["Daftar Produk", "➕ Tambah Produk Baru"])
        games_list = get_games(); game_options = {game['id']: game['name'] for game in games_list}
        if not game_options: st.warning("Tidak bisa mengelola produk. Silakan tambah data game terlebih dahulu di menu 'Kelola Game'.")
        else:
            with add_tab:
                with st.form("AddProductForm", clear_on_submit=True):
                    st.markdown("**Formulir Produk Baru**"); selected_game_id = st.selectbox("Pilih Game untuk Produk Ini", options=list(game_options.keys()), format_func=lambda x: game_options[x])
                    paket = st.text_input("Nama Paket (e.g., 100 Diamonds)"); harga = st.number_input("Harga (Rp)", min_value=1000, step=500)
                    if st.form_submit_button("Tambah Produk", type="primary", use_container_width=True):
                        if not all([selected_game_id, paket, harga]): st.warning("Semua kolom wajib diisi.")
                        else: 
                            with st.status("Menambahkan produk..."): add_product(selected_game_id, paket, harga)
                            st.success("Produk berhasil ditambahkan."); time.sleep(1); st.rerun()
            with list_tab:
                filter_options = {0: "Semua Game"}; filter_options.update(game_options)
                selected_filter_id = st.selectbox("Tampilkan produk untuk game:", options=list(filter_options.keys()), format_func=lambda x: filter_options[x], key="product_filter")
                st.markdown("**Daftar Produk Saat Ini**"); all_products = get_products_with_game_info()
                if selected_filter_id != 0: all_products = [p for p in all_products if p.get('game_id') == selected_filter_id]
                if not all_products: st.info("Tidak ada produk yang cocok dengan filter ini.")
                else:
                    for p in all_products:
                        if st.session_state.editing_product_id == p['id']:
                            with st.container(border=True):
                                 with st.form(key=f"edit_prod_{p['id']}"):
                                    st.write(f"**Mengubah Produk: {p['paket']}**")
                                    game_ids = list(game_options.keys()); current_game_index = game_ids.index(p['game_id']) if p.get('game_id') in game_ids else 0
                                    new_game_id = st.selectbox("Game", options=game_ids, format_func=lambda x: game_options[x], index=current_game_index)
                                    new_paket = st.text_input("Nama Paket", value=p['paket']); new_harga = st.number_input("Harga", value=p['harga'])
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.form_submit_button("Simpan", type="primary", use_container_width=True):
                                            with st.status("Memperbarui produk..."): update_product(p['id'], new_game_id, new_paket, new_harga)
                                            st.success("Produk diperbarui."); st.session_state.editing_product_id = None; time.sleep(1); st.rerun()
                                    with col2:
                                        if st.form_submit_button("Batal", use_container_width=True): st.session_state.editing_product_id = None; st.rerun()
                        else:
                            game_name = p['games']['name'] if p.get('games') else "Tanpa Game"
                            with st.container(border=True):
                                col1, col2 = st.columns([4, 1.5]);
                                with col1: st.markdown(f"**{game_name}** - {p['paket']}"); st.caption(f"Harga: Rp {p['harga']:,} | ID Produk: {p['id']}")
                                with col2:
                                    if st.button("Ubah", key=f"edit_prod_{p['id']}", use_container_width=True): st.session_state.editing_product_id = p['id']; st.rerun()
                                    if st.button("Hapus", key=f"del_prod_{p['id']}", use_container_width=True, type="primary"): delete_product(p['id']); st.rerun()
                                    
    elif sub_menu == "🧾 Daftar Transaksi":
        with st.expander("🔍 Filter & Cari Transaksi"):
            status_options = ["Semua Status", "Menunggu", "Diproses", "Selesai", "Gagal"]
            selected_status = st.selectbox("Filter berdasarkan status:", options=status_options)
            search_username = st.text_input("Cari berdasarkan username:")
        transactions = get_all_transactions()
        if selected_status != "Semua Status": transactions = [t for t in transactions if t['status'] == selected_status]
        if search_username: transactions = [t for t in transactions if search_username.lower() in t['username'].lower()]
        if not transactions: st.info("Tidak ada transaksi yang cocok dengan filter ini.")
        else:
            for t in transactions:
                nickname, metode = (t['user_nickname'].split("|", 1) + ["-"])[:2] if t.get('user_nickname') else (t.get('user_nickname'), "-")
                expander_title = f"ID: {t['id']} | User: {t['username']} | Game: {t.get('game', 'N/A')} | Status: {t['status']}"
                with st.expander(expander_title):
                    col1, col2 = st.columns([1, 2]);
                    with col1:
                        st.markdown("**Bukti Pembayaran:**")
                        if t.get('payment_proof_url'): st.image(t['payment_proof_url'], use_container_width=True)
                        else: st.caption("Belum ada bukti bayar.")
                    with col2:
                        st.markdown(f"**Waktu Pesan:** `{t['waktu']}`"); st.markdown(f"**Nickname:** `{nickname}` ({t['user_game_id']})")
                        st.markdown(f"**Paket:** {t['paket']} (Rp {t['harga']:,})"); st.markdown(f"**Metode Bayar:** {metode}")
                    st.divider()
                    st.markdown("**Update Status Pesanan:**")
                    with st.form(key=f"update_status_form_{t['id']}"):
                        status_options_form = ["Diproses", "Selesai", "Gagal"]
                        try: current_index_form = status_options_form.index(t['status'])
                        except ValueError: current_index_form = 0
                        new_status = st.selectbox("Ubah Status ke:", options=status_options_form, index=current_index_form, key=f"status_{t['id']}")
                        reason_input = st.text_area("Alasan Kegagalan (hanya diisi jika status Gagal):", key=f"reason_{t['id']}", value=t.get('failure_reason', '')) if new_status == 'Gagal' else ""
                        if st.form_submit_button("Simpan Perubahan", use_container_width=True, type="primary"):
                            if new_status == 'Gagal' and not reason_input.strip():
                                st.warning("Harap isi alasan mengapa transaksi ini digagalkan.")
                            else:
                                update_transaction_status(t['id'], new_status, reason_input)
                                st.toast(f"Status transaksi ID {t['id']} diubah ke {new_status}!", icon="✅")
                                time.sleep(1); st.rerun()

# --- UI: HALAMAN USER ---
def user_page():
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
    
    st.sidebar.title("✨ ARRA")
    st.sidebar.header("MENU PENGGUNA")
    page = st.sidebar.radio("Navigasi", ["🛒 Beranda & Top Up", "📜 Riwayat Transaksi", "👤 Profil Saya", "💬 Kotak Pesan"])
    if st.sidebar.button("Logout", use_container_width=True): clear_session(); st.rerun()

    if page == "💬 Kotak Pesan":
        st.header("💬 Kotak Pesan")
        st.write("Kirim pesan atau lihat balasan dari Admin di sini.")
        st.divider()
        username = st.session_state['user']
        mark_messages_as_read(recipient=username, sender="admin")
        conversation = get_conversation(username, "admin")
        if not conversation:
            st.info("Belum ada percakapan. Mulai percakapan pertama Anda dengan Admin di bawah ini!")
        
        with st.container(height=500, border=True):
            for msg in conversation:
                role = "user" if msg['sender'] == username else "assistant"
                avatar_icon = "🧑‍💻" if role == "user" else "👑"
                with st.chat_message(role, avatar=avatar_icon):
                    st.write(msg['content'])
                    dt_object = datetime.fromisoformat(msg['created_at'])
                    st.caption(f"{dt_object.strftime('%d %b %Y, %H:%M')}")
        
        with st.form("message_form", clear_on_submit=True):
            user_message = st.text_area("Ketik pesan Anda untuk Admin:", height=100, label_visibility="collapsed", placeholder="Ketik pesan Anda...")
            if st.form_submit_button("Kirim Pesan", use_container_width=True, type="primary"):
                with st.spinner("Mengirim pesan..."): send_message(sender=username, recipient="admin", content=user_message)
                st.success("Pesan Anda telah terkirim!"); st.rerun()

    elif page == "👤 Profil Saya":
        st.header(f"Profil Saya")
        user_data = get_user_data(st.session_state['user'])
        
        email = user_data.get('email') if user_data else None
        st.write(f"Selamat datang kembali, **{st.session_state['user']}**!")
        st.caption(f"Email terdaftar: **{email or 'Belum diatur'}**")
        st.divider()
        st.subheader("Ringkasan Aktivitas Anda")
        transactions = get_user_transactions(st.session_state['user'])
        completed_trans = [t for t in transactions if t['status'] == 'Selesai']
        total_completed_trans = len(completed_trans)
        total_spending = sum(t['harga'] for t in completed_trans)
        fav_game = "Belum ada"
        if completed_trans:
            game_list = [t['game'] for t in completed_trans]
            if game_list: fav_game = Counter(game_list).most_common(1)[0][0]
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Transaksi Selesai", f"{total_completed_trans} Pesanan")
        with col2: st.metric("Total Pengeluaran", f"Rp {total_spending:,}")
        with col3: st.metric("Game Favorit", fav_game)
        st.divider()
        st.subheader("Pengaturan Akun")
        
        with st.form("update_email_form"):
            st.markdown("**Perbarui Alamat Email**")
            st.caption("Digunakan untuk potensi fitur pengiriman struk di masa depan.")
            current_email = user_data.get('email', '') if user_data else ""
            new_email = st.text_input("Email Anda", value=current_email, placeholder="contoh@email.com", label_visibility="collapsed")
            if st.form_submit_button("Simpan Email", use_container_width=True, type="primary"):
                with st.spinner("Memperbarui email..."):
                    update_user_email(st.session_state['user'], new_email)
                st.success("Alamat email berhasil diperbarui!"); time.sleep(1); st.rerun()

        with st.form("change_password_form", clear_on_submit=True):
            st.markdown("**Ubah Password**")
            new_pass = st.text_input("Password Baru", type="password")
            if st.form_submit_button("Ganti Password", type="primary"): 
                with st.spinner("Menyimpan password baru..."): update_user_password(st.session_state['user'], new_pass)
                st.success("Password berhasil diubah!")
    
    elif page == "🛒 Beranda & Top Up":
        if 'pending_payment' in st.session_state:
            pending_trans = st.session_state.pending_payment
            st.title("Langkah Terakhir!")
            st.success(f"Pesanan (ID: {pending_trans['id']}) untuk **{pending_trans['paket']}** berhasil dibuat!")
            st.info("Silakan selesaikan pembayaran Anda.")
            with st.container(border=True):
                st.markdown("#### 1. Lakukan Pembayaran")
                st.markdown(f"Silakan transfer sejumlah **Rp {pending_trans['harga']:,}** ke nomor **DANA/GOPAY** di bawah ini:")
                st.code("089633436959", language="text")
                st.markdown("#### 2. Unggah Bukti Pembayaran")
                st.write("Setelah transfer berhasil, unggah screenshot bukti pembayaran di bawah ini. Status pesanan akan otomatis berubah menjadi 'Diproses'.")
                uploaded_proof = st.file_uploader("Pilih file bukti pembayaran Anda...", type=["png", "jpg", "jpeg"], key=f"proof_direct_{pending_trans['id']}")
                if uploaded_proof: upload_payment_proof(pending_trans['id'], uploaded_proof)
            st.divider()
            if st.button("Lakukan Pesanan Lain"): del st.session_state.pending_payment; st.rerun()
            return

        if "user_selected_game" not in st.session_state: st.session_state.user_selected_game = None
        if 'show_review_form' not in st.session_state: st.session_state.show_review_form = False
        
        if st.session_state.user_selected_game is None:
            st.title("✨ Beranda ARRA")
            st.subheader(f"Selamat Datang, {st.session_state['user']}!")
            st.write("Mau top up apa hari ini?")
            search_term = st.text_input("🔍 Cari game favoritmu...", key="game_search", placeholder="Ketik nama game...")
            st.divider()
            st.subheader("Game Populer")
            games = get_games()
            if not games: st.warning("Belum ada game yang tersedia."); return
            if search_term: games = [g for g in games if search_term.lower() in g['name'].lower()]
            st.session_state.show_review_form = False
            st.session_state.visible_reviews_count = 3
            cols = st.columns(4)
            for i, game in enumerate(games):
                with cols[i % 4]:
                    with st.container(border=True):
                        st.image(game['logo_url'])
                        if st.button(game['name'], use_container_width=True, key=f"game_{game['id']}"): 
                            st.session_state.user_selected_game = game
                            st.session_state.visible_reviews_count = 3
                            st.rerun()
            return

        selected_game = st.session_state.user_selected_game
        st.title(f"{selected_game['name']}")
        if st.button("⬅️ Kembali ke Daftar Game"): 
            st.session_state.user_selected_game = None; st.session_state.selected_product = None; st.rerun()
        
        tab_beli, tab_ulasan, tab_info = st.tabs(["🛍️ Beli Produk", "⭐ Ulasan", "ℹ️ Info"])
        with tab_beli:
            st.subheader("Pilih Paket & Isi Data")
            col1, col2 = st.columns([2,3])
            with col1:
                st.markdown("**Paket Tersedia**")
                all_products = get_products_with_game_info()
                game_products = [p for p in all_products if p.get('game_id') == selected_game['id']]
                if not game_products: st.warning("Produk untuk game ini belum tersedia.")
                else:
                    for p in game_products:
                        if st.button(f"{p['paket']} - Rp {p['harga']:,}", key=f"choose_{p['id']}", use_container_width=True): st.session_state.selected_product = p; st.rerun()
            with col2:
                st.markdown("**Data & Pembayaran**")
                if "selected_product" in st.session_state and st.session_state.selected_product:
                    product = st.session_state.selected_product
                    with st.container(border=True):
                        st.write(f"Pilihan Anda: **{product['paket']}**")
                        st.write(f"Harga: **Rp {product['harga']:,}**")
                        with st.form("form_topup"):
                            nickname = st.text_input("Nickname Game")
                            game_id = st.text_input("User ID (Zone ID jika ada)")
                            pay_method = st.radio("Metode Pembayaran", ["DANA", "GOPAY"], horizontal=True)
                            if st.form_submit_button("Pesan Sekarang", use_container_width=True, type="primary"):
                                if not nickname or not game_id: st.warning("Nickname dan User ID harus diisi!")
                                else:
                                    with st.spinner("Membuat pesanan..."):
                                        new_transaction = add_transaction(st.session_state["user"], selected_game['name'], product['paket'], product['harga'], f"{nickname}|{pay_method}", game_id)
                                    st.session_state.pending_payment = new_transaction
                                    del st.session_state.selected_product; st.rerun()
                else: st.info("Pilih paket di sebelah kiri untuk melanjutkan.")
        
        with tab_ulasan:
            review_col1, review_col2 = st.columns([3,1])
            with review_col1: st.subheader(f"Ulasan Pengguna")
            with review_col2:
                if st.button("✍️ Tulis Ulasan", use_container_width=True):
                    st.session_state.show_review_form = not st.session_state.show_review_form
            if st.session_state.show_review_form:
                with st.form("review_form", clear_on_submit=True, border=True):
                    rating_options = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}
                    rating = st.select_slider("Beri Rating:", options=list(rating_options.keys()), format_func=lambda x: rating_options[x], value=5)
                    comment = st.text_area("Komentar Anda:")
                    if st.form_submit_button("Kirim Ulasan", type="primary"):
                        if rating and comment:
                            with st.spinner("Mengirim ulasan..."):
                                add_review(selected_game['id'], st.session_state['user'], rating, comment)
                            st.success("Terima kasih atas ulasan Anda!"); st.session_state.show_review_form = False; st.rerun()
                        else: st.warning("Harap isi rating dan komentar.")
            game_reviews = get_reviews_for_game(selected_game['id'])
            if not game_reviews: st.info("Jadilah yang pertama memberikan ulasan untuk game ini!")
            else:
                ratings_list = [r['rating'] for r in game_reviews]
                avg_rating = np.mean(ratings_list) if ratings_list else 0
                st.markdown(f"**Rating Rata-rata:** {'⭐' * int(round(avg_rating))} ({avg_rating:.1f} / 5 dari {len(ratings_list)} ulasan)")
                st.divider()
                if 'visible_reviews_count' not in st.session_state: st.session_state.visible_reviews_count = 3
                reviews_to_show = game_reviews[:st.session_state.visible_reviews_count]
                for review in reviews_to_show:
                    with st.container(border=True):
                        st.markdown(f"**{review['username']}** - `{'⭐' * review['rating']}`")
                        st.caption(f"Pada: {datetime.fromisoformat(review['created_at']).strftime('%d %b %Y')}")
                        st.write(f"*{review['comment']}*")
                if len(game_reviews) > st.session_state.visible_reviews_count:
                    if st.button("Lihat Ulasan Lainnya..."):
                        st.session_state.visible_reviews_count += 3; st.rerun()
        with tab_info:
            st.subheader(f"Tentang {selected_game['name']}")
            st.write(selected_game['description'] or "Tidak ada deskripsi untuk game ini.")
            st.divider()
            st.subheader("Cara Menemukan User ID")
            st.info("Setiap game memiliki cara yang berbeda untuk menemukan User ID. Umumnya, Anda bisa menemukannya di dalam halaman profil di dalam game tersebut. Pastikan Anda memasukkan ID dengan benar untuk menghindari kesalahan top up.")
    
    elif page == "📜 Riwayat Transaksi":
        st.header("Riwayat Transaksi Anda")
        transactions = get_user_transactions(st.session_state["user"])
        if not transactions: st.info("Anda belum memiliki riwayat transaksi.")
        else:
            for t in transactions:
                nickname, metode = (t['user_nickname'].split("|", 1) + ["-"])[:2] if t.get('user_nickname') else (t.get('user_nickname'), "-")
                with st.container(border=True):
                    st.write(f"#### {t['paket']} (ID: {t['id']})")
                    st.write(f"**Game:** {t['game']} | **Harga:** Rp {t['harga']:,}")
                    status_color = {"Selesai": "green", "Diproses": "orange", "Gagal": "red", "Menunggu":"blue"}.get(t['status'], "gray")
                    st.write(f"Status: **<span style='color:{status_color};'>{t['status']}</span>**", unsafe_allow_html=True)
                    if t['status'] == 'Gagal' and t.get('failure_reason'):
                        st.error(f"**Alasan Kegagalan:** {t['failure_reason']}", icon="❗")
                    if t['status'] == 'Menunggu' and not t.get('payment_proof_url'):
                        with st.expander("Unggah Bukti Pembayaran"):
                            uploaded_proof = st.file_uploader("Pilih file bukti...", type=["png", "jpg", "jpeg"], key=f"proof_history_{t['id']}")
                            if uploaded_proof: upload_payment_proof(t['id'], uploaded_proof)
                    if t.get('payment_proof_url'):
                        with st.expander("Lihat Bukti Pembayaran"): st.image(t['payment_proof_url'])

# --- LOGIKA UTAMA APLIKASI ---
def main():
    st.set_page_config(page_title="ARRA TopUp", page_icon="✨", layout="wide", initial_sidebar_state="expanded")
    if "user" not in st.session_state:
        login_register_menu()
    else:
        st_autorefresh(interval=7000, key="global_refresh")
        st.sidebar.title("✨ ARRA")
        st.sidebar.success(f"Login sebagai: **{st.session_state['user']}**")
        st.sidebar.caption(f"Role: {st.session_state['role']}")
        st.sidebar.divider()
        if st.session_state["role"] == "admin":
            admin_page()
        else:
            user_page()

if __name__ == "__main__":
    main()
