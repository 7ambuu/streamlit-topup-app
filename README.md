# ✨ ARRA - Aplikasi Top Up Game Berbasis Streamlit & Supabase

Selamat datang di ARRA, sebuah aplikasi web top-up game dinamis yang dibangun sepenuhnya menggunakan Python dengan framework Streamlit dan didukung oleh backend Supabase. Aplikasi ini dirancang sebagai platform jual-beli item game yang fungsional, mencakup manajemen user, produk, transaksi, hingga fitur interaktif seperti ulasan dan kotak pesan.

Proyek ini adalah demonstrasi membangun aplikasi web yang *stateful* (menyimpan data) dan interaktif dengan arsitektur modern yang mudah dikembangkan.

## 🚀 Fitur Utama

Aplikasi ini memiliki dua peran utama dengan fungsionalitas yang berbeda: Pengguna (User) dan Administrator (Admin).

### Fitur untuk Pengguna
* **🏡 Beranda Dinamis:** Halaman depan yang menyambut pengguna dan menampilkan game-game populer dengan fitur pencarian.
* **🔑 Otentikasi:** Sistem pendaftaran (Register) dan masuk (Login) yang aman menggunakan hashing password.
* **🛍️ Katalog Produk:** Melihat daftar game dan produk top-up yang tersedia dalam tampilan tab yang rapi dan modern.
* **🛒 Proses Pemesanan:** Alur pemesanan yang mudah, mulai dari memilih produk, mengisi data game, hingga mendapatkan instruksi pembayaran.
* **💳 Upload Bukti Bayar:** Pengguna dapat langsung mengunggah bukti pembayaran setelah memesan untuk mempercepat proses verifikasi.
* **📜 Riwayat Transaksi:** Halaman khusus untuk melihat semua riwayat pembelian beserta statusnya (Menunggu, Diproses, Selesai, Gagal) dan alasan jika transaksi gagal.
* **⭐ Ulasan & Rating:** Pengguna dapat memberikan rating (1-5 bintang) dan menulis ulasan untuk setiap game.
* **💬 Kotak Pesan:** Fitur komunikasi langsung dengan admin untuk bertanya atau meminta bantuan, dengan tampilan seperti aplikasi chat.
* **👤 Halaman Profil:**
    * Melihat ringkasan statistik pribadi (total transaksi, total pengeluaran, game favorit).
    * Mengubah password akun.
* **🔔 Notifikasi Real-time:** Mendapatkan notifikasi `toast` secara otomatis ketika status pesanan diubah oleh admin.

### Fitur untuk Administrator
* **👑 Panel Admin:** Dasbor terpusat untuk mengelola seluruh aspek aplikasi.
* **🎮 Manajemen Game (CRUD):** Kemampuan untuk menambah, melihat, mengubah, dan menghapus game yang dijual secara dinamis.
* **🛍️ Manajemen Produk (CRUD):** Kemampuan untuk menambah, melihat, mengubah, dan menghapus produk top-up untuk setiap game.
* **🧾 Manajemen Transaksi:** Melihat semua transaksi yang masuk, memverifikasi bukti pembayaran, dan mengubah status pesanan (lengkap dengan alasan jika gagal).
* **📝 Moderasi Ulasan:** Mengelola semua ulasan yang masuk dengan opsi untuk menyembunyikan/menampilkan atau menghapus ulasan yang tidak pantas.
* **👥 Manajemen Pengguna:** Melihat daftar semua pengguna yang terdaftar dan menghapus pengguna jika diperlukan.
* **💬 Kotak Pesan Admin:** Melihat dan membalas semua pesan dari pengguna dalam satu antarmuka yang terorganisir.
* **📊 Unduh Laporan:** Mengunduh data penting seperti transaksi dan pengguna dalam format file Excel (.xlsx) untuk analisis atau backup.

---

## 🛠️ Teknologi yang Digunakan

* **Frontend:** [Streamlit](https://streamlit.io/)
* **Backend & Database:** [Supabase](https://supabase.com/) (PostgreSQL Database, Storage for images, Auth)
* **Library Python Utama:** `pandas`, `numpy`, `Pillow`, `streamlit-autorefresh`, `supabase-py`

---

Dibuat dengan ❤️ oleh **Azzam**.
