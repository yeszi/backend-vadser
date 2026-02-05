import hashlib
import json
import os
import shutil # Library untuk copy file
from datetime import datetime
from time import time
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_FILE = 'blockchain_data.json'
BACKUP_DIR = 'blockchain_backups' # Folder khusus backup

class Blockchain:
    def __init__(self):
        self.chain = []
        # Buat folder backup jika belum ada
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
            
        if os.path.exists(DB_FILE):
            self.load_data()
        else:
            self.create_block(pdf_hash='0', nama='System', nim='000', prodi='Root', ipk='0.00', save=True)

    def create_block(self, pdf_hash, nama, nim, prodi, ipk, save=True):
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
            'previous_hash': self.hash(self.chain[-1]) if self.chain else '0'
        }
        block['hash'] = self.hash(block)
        
        self.chain.append(block)
        
        if save: self.save_data()
        return block

    def save_data(self):
        # 1. Simpan ke File Utama
        with open(DB_FILE, 'w') as f:
            json.dump(self.chain, f, indent=4)
        
        # 2. MEKANISME BACKUP (Mirroring)
        # Buat nama file unik: backup_2026-01-31_10-30-55.json
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"{BACKUP_DIR}/chain_backup_{timestamp}.json"
        
        # Copy file utama ke file backup
        try:
            shutil.copy2(DB_FILE, backup_filename)
            
            # Opsional: Hapus backup lama jika sudah lebih dari 50 file (agar storage tidak penuh)
            self.cleanup_old_backups()
            
        except Exception as e:
            print(f"Gagal backup: {e}")

    def cleanup_old_backups(self):
        # Hapus backup terlama jika jumlah file > 50
        files = sorted(os.listdir(BACKUP_DIR))
        if len(files) > 50:
            os.remove(os.path.join(BACKUP_DIR, files[0]))

    def load_data(self):
        try:
            with open(DB_FILE, 'r') as f:
                self.chain = json.load(f)
        except:
            # FITUR RECOVERY:
            # Jika file utama rusak/hilang, coba cari backup terakhir
            print("⚠️ File utama rusak/hilang! Mencoba restore dari backup...")
            try:
                files = sorted(os.listdir(BACKUP_DIR))
                if files:
                    last_backup = files[-1] # Ambil yang paling baru
                    print(f"♻️ Merestore dari: {last_backup}")
                    with open(os.path.join(BACKUP_DIR, last_backup), 'r') as f:
                        self.chain = json.load(f)
                    # Simpan balik ke file utama
                    self.save_data()
                else:
                    self.chain = []
                    self.create_block(pdf_hash='0', nama='System', nim='000', prodi='Root', ipk='0.00', save=True)
            except:
                self.chain = []
                self.create_block(pdf_hash='0', nama='System', nim='000', prodi='Root', ipk='0.00', save=True)

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @staticmethod
    def calculate_file_hash(file_stream):
        sha256_hash = hashlib.sha256()
        for byte_block in iter(lambda: file_stream.read(4096), b""):
            sha256_hash.update(byte_block)
        file_stream.seek(0)
        return sha256_hash.hexdigest()

    def find_block_by_file(self, pdf_hash):
        for block in self.chain:
            if block.get('pdf_hash') == pdf_hash:
                return block
        return None

    def is_nim_registered(self, nim_to_check):
        for block in self.chain:
            if block['pdf_hash'] == '0': continue
            if block['student_data']['nim'] == nim_to_check:
                return True
        return False
    
    def check_integrity(self):
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i-1]
            if current['previous_hash'] != self.hash(previous):
                return False
        return True

blockchain = Blockchain()

# --- ROUTES ---

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if data.get('username') == "admin" and data.get('password') == "admin123":
        return jsonify({"success": True}), 200
    return jsonify({"success": False}), 401

@app.route('/upload_ijazah', methods=['POST'])
def upload_ijazah():
    if 'file' not in request.files: return jsonify({'message': 'No file'}), 400
    
    file = request.files['file']
    nama = request.form.get('nama')
    nim = request.form.get('nim')
    prodi = request.form.get('prodi')
    ipk = request.form.get('ipk')

    if not all([nama, nim, prodi, ipk]): return jsonify({'message': 'Data tidak lengkap!'}), 400

    if blockchain.is_nim_registered(nim):
        return jsonify({'message': f'NIM {nim} sudah terdaftar permanen!'}), 403

    pdf_hash = blockchain.calculate_file_hash(file)
    if blockchain.find_block_by_file(pdf_hash):
        return jsonify({'message': 'File ijazah ini sudah ada.'}), 400

    new_block = blockchain.create_block(pdf_hash, nama, nim, prodi, ipk)

    return jsonify({
        'message': 'Ijazah berhasil diamankan dan dibackup.',
        'hash': new_block['hash']
    }), 201

@app.route('/verify_ijazah', methods=['POST'])
def verify_ijazah():
    file = request.files['file']
    pdf_hash = blockchain.calculate_file_hash(file)
    block = blockchain.find_block_by_file(pdf_hash)

    if block:
        return jsonify({
            'status': 'VALID',
            'message': 'Ijazah ASLI & TERVERIFIKASI.',
            'data': block['student_data'],
            'timestamp': block['timestamp']
        }), 200
    else:
        return jsonify({'status': 'INVALID', 'message': 'Data tidak ditemukan.'}), 404

@app.route('/chain', methods=['GET'])
def get_chain():
    real_chain = [b for b in blockchain.chain if b['pdf_hash'] != '0']
    return jsonify({
        'chain': real_chain[::-1],
        'integrity': blockchain.check_integrity()
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)