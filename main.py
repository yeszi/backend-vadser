import hashlib
import json
import os
from time import time
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

# --- 1. KONFIGURASI DAN KONEKSI DATABASE ---
load_dotenv()

# Ambil URL dan Key dari Environment Variables (Vercel)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Inisialisasi Client Supabase
supabase: Client = None
try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️ Peringatan: Supabase Credential belum di-set di Environment Variable.")
    else:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Berhasil terkoneksi ke Supabase Cloud")
except Exception as e:
    print(f"❌ Gagal koneksi Supabase: {e}")

# Konfigurasi Admin
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

app = Flask(__name__)
# Aktifkan CORS agar frontend (jika ada) bisa akses
CORS(app, resources={r"/*": {"origins": "*"}})


# --- 2. KELAS BLOCKCHAIN ---
class Blockchain:
    def __init__(self):
        self.chain = []
        # Saat server nyala, langsung tarik data dari Supabase
        self.load_data()

    def create_block(self, pdf_hash, nama, nim, prodi, ipk):
        """
        Membuat blok baru:
        1. Hitung Hash
        2. Simpan ke List (Memori)
        3. Simpan ke Supabase (Database Permanen)
        """
        if len(self.chain) > 0:
            previous_hash = self.chain[-1]['hash']
        else:
            previous_hash = '0'

        # Struktur Data (Sesuai Konsep JSON)
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

        # Hitung Hash SHA-256
        block['hash'] = self.hash(block)

        # Simpan ke Memori Python
        self.chain.append(block)

        # Simpan ke Cloud (Supabase) agar tidak hilang
        self.save_block_to_db(block)
        
        return block

    @staticmethod
    def hash(block):
        """
        Membuat SHA-256 hash dari blok.
        PENTING: Kita hapus field 'id' (jika ada dari database) agar hash konsisten.
        """
        block_copy = block.copy()
        
        # Bersihkan field internal database yang tidak perlu di-hash
        if 'id' in block_copy: del block_copy['id']
        if 'hash' in block_copy: del block_copy['hash']

        # Dump ke string JSON yang terurut (sort_keys=True)
        block_string = json.dumps(block_copy, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @staticmethod
    def calculate_file_hash(file_stream):
        """Menghitung SHA-256 dari file fisik PDF"""
        sha256_hash = hashlib.sha256()
        for byte_block in iter(lambda: file_stream.read(4096), b""):
            sha256_hash.update(byte_block)
        file_stream.seek(0) # Reset pointer file ke awal
        return sha256_hash.hexdigest()

    def save_block_to_db(self, block):
        """Mengirim data blok ke tabel Supabase"""
        if supabase is not None:
            try:
                # Insert ke tabel 'chain'
                supabase.table("chain").insert(block).execute()
            except Exception as e:
                print(f"Gagal menyimpan ke Supabase: {e}")

    def load_data(self):
        """Mengambil semua data blok dari Supabase saat aplikasi mulai"""
        if supabase is not None:
            try:
                # Select semua data, urutkan berdasarkan index
                response = supabase.table("chain").select("*").order("index").execute()
                data = response.data
                
                if data:
                    self.chain = data
                else:
                    # Jika database kosong, buat Genesis Block otomatis
                    self.create_block('0', 'System Genesis', '000', 'Root', '0.00')
            except Exception as e:
                print(f"Error loading DB: {e}")
                self.chain = []

    def find_block_by_file(self, pdf_hash):
        """Mencari blok berdasarkan hash PDF"""
        for block in self.chain:
            if block.get('pdf_hash') == pdf_hash:
                return block
        return None

    def is_nim_registered(self, nim_to_check):
        """Mengecek apakah NIM sudah ada di blockchain"""
        for block in self.chain:
            if block['pdf_hash'] == '0': continue # Skip Genesis
            # Akses nested json student_data
            if block['student_data'].get('nim') == nim_to_check:
                return True
        return False

    def check_integrity(self):
        """Validasi rantai blok (Anti-Tamper Check)"""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            prev = self.chain[i-1]

            # Cek 1: Link Hash Putus?
            if current['previous_hash'] != prev['hash']: 
                return False
            
            # Cek 2: Data Dimodifikasi? (Re-hash)
            if current['hash'] != self.hash(current): 
                return False     
        return True

# Inisialisasi Objek Blockchain
blockchain = Blockchain()


# --- 3. ROUTES / API ENDPOINTS ---

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "status": "Running on Vercel",
        "storage": "Supabase Cloud Database",
        "total_blocks": len(blockchain.chain),
        "message": "Lightweight Blockchain System is Active"
    })

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if data.get('username') == ADMIN_USERNAME and data.get('password') == ADMIN_PASSWORD:
        return jsonify({"success": True, "token": "dummy-token-access"}), 200
    return jsonify({"success": False, "message": "Invalid Credentials"}), 401

@app.route('/upload_ijazah', methods=['POST'])
def upload_ijazah():
    # Validasi Input
    if 'file' not in request.files: 
        return jsonify({'message': 'File PDF wajib diupload'}), 400

    file = request.files['file']
    nama = request.form.get('nama')
    nim = request.form.get('nim')
    prodi = request.form.get('prodi')
    ipk = request.form.get('ipk')

    if not all([nama, nim, prodi, ipk]): 
        return jsonify({'message': 'Data mahasiswa tidak lengkap!'}), 400

    # Refresh data dari cloud (penting utk Vercel Serverless)
    blockchain.load_data() 

    # Cek Duplikasi
    if blockchain.is_nim_registered(nim):
        return jsonify({'message': f'NIM {nim} sudah terdaftar di sistem!'}), 403

    pdf_hash = blockchain.calculate_file_hash(file)

    if blockchain.find_block_by_file(pdf_hash):
        return jsonify({'message': 'Dokumen ijazah ini sudah ada di sistem.'}), 400

    # Buat Blok Baru & Simpan
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
    pdf_hash = blockchain.calculate_file_hash(file)
    
    # Refresh data agar dapat update terbaru
    blockchain.load_data()
    
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
            'message': 'Data TIDAK DITEMUKAN. File palsu atau belum terdaftar.'
        }), 404

@app.route('/chain', methods=['GET'])
def get_chain():
    """Melihat seluruh rantai blok (JSON)"""
    blockchain.load_data()
    real_chain = [b for b in blockchain.chain if b['pdf_hash'] != '0']
    
    return jsonify({
        'chain': real_chain[::-1], # Urutkan dari yang terbaru
        'length': len(real_chain),
        'integrity_status': blockchain.check_integrity()
    }), 200

# --- FITUR TAMBAHAN KHUSUS SKRIPSI ---
@app.route('/download_json', methods=['GET'])
def download_json():
    """
    Endpoint untuk mendownload database dalam bentuk file JSON fisik.
    Ini membuktikan bahwa sistem tetap berbasis JSON.
    """
    blockchain.load_data()
    
    # Konversi data memory ke string JSON
    json_output = json.dumps(blockchain.chain, indent=4)
    
    return Response(
        json_output,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=blockchain_data.json"}
    )

# Handler untuk Vercel Serverless
if __name__ == '__main__':
    app.run(debug=True)