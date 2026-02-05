import hashlib
import json
import os
import shutil
from datetime import datetime
from time import time
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
# Izinkan akses dari Vue.js (biasanya port 5173 atau 8080)
CORS(app, resources={r"/*": {"origins": "*"}})

# Konfigurasi File Penyimpanan
DB_FILE = 'blockchain_data.json'
BACKUP_DIR = 'blockchain_backups'

class Blockchain:
    def __init__(self):
        self.chain = []
        
        # 1. Pastikan folder backup ada
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)

        # 2. Load data jika ada, atau buat Genesis Block
        if os.path.exists(DB_FILE):
            self.load_data()
        else:
            # Genesis Block (Blok Pertama)
            self.create_block(
                pdf_hash='0', 
                nama='System Genesis', 
                nim='000', 
                prodi='Root', 
                ipk='0.00', 
                save=True
            )

    def create_block(self, pdf_hash, nama, nim, prodi, ipk, save=True):
        """
        Membuat blok baru dan menambahkannya ke rantai.
        """
        # --- PERBAIKAN LOGIKA CHAINING (PENTING) ---
        if len(self.chain) > 0:
            # Ambil hash string langsung dari blok terakhir (bukan di-hash ulang)
            previous_hash = self.chain[-1]['hash']
        else:
            # Jika ini blok pertama (Genesis)
            previous_hash = '0'
        # -------------------------------------------

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'pdf_hash': pdf_hash,
            'student_data': {
                'nama': nama,
                'nim': nim,
                'prodi': prodi,
                'ipk': ipk
            },
            'previous_hash': previous_hash
        }

        # Hitung hash blok saat ini (Digital Signature)
        block['hash'] = self.hash(block)

        self.chain.append(block)

        if save: 
            self.save_data()
        
        return block

    @staticmethod
    def hash(block):
        """
        Membuat SHA-256 hash dari sebuah blok.
        PENTING: Kita harus membuang key 'hash' jika ada, agar tidak terjadi circular logic.
        """
        block_copy = block.copy()
        
        # Hapus field 'hash' dari dictionary sebelum dihitung
        if 'hash' in block_copy:
            del block_copy['hash']

        # sort_keys=True PENTING agar urutan JSON selalu konsisten
        block_string = json.dumps(block_copy, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @staticmethod
    def calculate_file_hash(file_stream):
        """
        Menghitung SHA-256 dari file fisik (PDF).
        """
        sha256_hash = hashlib.sha256()
        # Baca file per 4KB chunk agar memori hemat
        for byte_block in iter(lambda: file_stream.read(4096), b""):
            sha256_hash.update(byte_block)
        
        # Kembalikan cursor file ke awal agar bisa dibaca lagi jika perlu
        file_stream.seek(0)
        return sha256_hash.hexdigest()

    def save_data(self):
        """
        Menyimpan rantai ke file JSON dan melakukan Backup otomatis.
        """
        try:
            # 1. Simpan ke File Utama
            with open(DB_FILE, 'w') as f:
                json.dump(self.chain, f, indent=4)

            # 2. Auto Backup (Mirroring)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_filename = f"{BACKUP_DIR}/chain_backup_{timestamp}.json"
            shutil.copy2(DB_FILE, backup_filename)

            # 3. Bersihkan backup lama (sisakan 20 terakhir saja)
            self.cleanup_old_backups()
            
        except Exception as e:
            print(f"Error saving data: {e}")

    def cleanup_old_backups(self):
        """Hapus file backup lama agar storage tidak penuh."""
        try:
            files = sorted(os.listdir(BACKUP_DIR))
            if len(files) > 20:
                for f in files[:-20]: # Hapus semua kecuali 20 terakhir
                    os.remove(os.path.join(BACKUP_DIR, f))
        except Exception:
            pass

    def load_data(self):
        """Load data dari JSON dengan fitur Auto-Recovery."""
        try:
            with open(DB_FILE, 'r') as f:
                self.chain = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print("⚠️ File utama rusak/hilang! Mencoba restore dari backup...")
            self.recover_from_backup()

    def recover_from_backup(self):
        """Mencoba mengembalikan data dari file backup terakhir."""
        try:
            files = sorted(os.listdir(BACKUP_DIR))
            if files:
                last_backup = files[-1]
                print(f"♻️ Merestore dari: {last_backup}")
                with open(os.path.join(BACKUP_DIR, last_backup), 'r') as f:
                    self.chain = json.load(f)
                # Simpan ulang ke file utama agar normal kembali
                with open(DB_FILE, 'w') as f:
                    json.dump(self.chain, f, indent=4)
            else:
                # Jika tidak ada backup sama sekali, reset ke awal
                self.chain = []
                self.create_block('0', 'System', '000', 'Root', '0.00', save=True)
        except Exception as e:
            print(f"Critical Error: {e}")
            self.chain = []

    def find_block_by_file(self, pdf_hash):
        for block in self.chain:
            if block.get('pdf_hash') == pdf_hash:
                return block
        return None

    def is_nim_registered(self, nim_to_check):
        for block in self.chain:
            # Skip Genesis Block
            if block['pdf_hash'] == '0': continue
            if block['student_data']['nim'] == nim_to_check:
                return True
        return False

    def check_integrity(self):
        """
        Memeriksa apakah rantai valid (Tamper-Proof Check).
        """
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]

            # 1. Cek Link: Apakah previous_hash blok ini == hash blok sebelumnya?
            if current_block['previous_hash'] != previous_block['hash']:
                print(f"Broken Link at Block {i}")
                return False

            # 2. Cek Isi: Apakah hash blok ini valid jika dihitung ulang?
            # (Mendeteksi jika data diedit tapi hash tidak diupdate)
            recalculated_hash = self.hash(current_block)
            if current_block['hash'] != recalculated_hash:
                print(f"Data Modified at Block {i}")
                return False
                
        return True

# --- Inisialisasi Blockchain ---
blockchain = Blockchain()

# --- ROUTE FLASK ---

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "status": "Running",
        "message": "Lightweight Blockchain System API is Active"
    })

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    # Hardcode admin sederhana (bisa diganti database nanti)
    if data.get('username') == "admin" and data.get('password') == "admin123":
        return jsonify({"success": True, "token": "dummy-jwt-token"}), 200
    return jsonify({"success": False, "message": "Invalid Credentials"}), 401

@app.route('/upload_ijazah', methods=['POST'])
def upload_ijazah():
    # 1. Validasi Input
    if 'file' not in request.files: 
        return jsonify({'message': 'File PDF wajib diupload'}), 400

    file = request.files['file']
    nama = request.form.get('nama')
    nim = request.form.get('nim')
    prodi = request.form.get('prodi')
    ipk = request.form.get('ipk')

    if not all([nama, nim, prodi, ipk]): 
        return jsonify({'message': 'Data mahasiswa tidak lengkap!'}), 400

    # 2. Cek apakah NIM sudah ada (Aturan Bisnis: 1 NIM = 1 Ijazah)
    if blockchain.is_nim_registered(nim):
        return jsonify({'message': f'NIM {nim} sudah terdaftar di Blockchain!'}), 403

    # 3. Hitung Hash PDF
    pdf_hash = blockchain.calculate_file_hash(file)

    # 4. Cek apakah file yang sama persis sudah pernah diupload
    if blockchain.find_block_by_file(pdf_hash):
        return jsonify({'message': 'Dokumen ijazah ini sudah ada di sistem.'}), 400

    # 5. Buat Blok Baru
    new_block = blockchain.create_block(pdf_hash, nama, nim, prodi, ipk)

    return jsonify({
        'success': True,
        'message': 'Ijazah berhasil diamankan ke Blockchain.',
        'block_index': new_block['index'],
        'block_hash': new_block['hash']
    }), 201

@app.route('/verify_ijazah', methods=['POST'])
def verify_ijazah():
    if 'file' not in request.files:
        return jsonify({'message': 'Upload file untuk verifikasi'}), 400
    
    file = request.files['file']
    
    # 1. Hitung sidik jari file yang diupload user
    pdf_hash = blockchain.calculate_file_hash(file)
    
    # 2. Cari di Blockchain
    block = blockchain.find_block_by_file(pdf_hash)

    if block:
        return jsonify({
            'status': 'VALID',
            'message': 'Ijazah Terdaftar dan ASLI.',
            'data': block['student_data'],
            'timestamp': block['timestamp'],
            'registered_hash': block['hash']
        }), 200
    else:
        return jsonify({
            'status': 'INVALID',
            'message': 'Data TIDAK DITEMUKAN. Kemungkinan file palsu atau belum terdaftar.'
        }), 404

@app.route('/chain', methods=['GET'])
def get_chain():
    real_chain = [b for b in blockchain.chain if b['pdf_hash'] != '0']
    
    is_valid = blockchain.check_integrity()
    
    return jsonify({
        'chain': real_chain[::-1], 
        'length': len(real_chain),
        'integrity_status': is_valid
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)