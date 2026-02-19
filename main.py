import hashlib
import json
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


class Blockchain:
    def __init__(self):
        self.chain = []
        self.load_data()

    def load_data(self):
        """Tarik data terbaru dari Supabase Cloud"""
        try:

            response = supabase.table("sertifikat_digital").select("*").order("id").execute()
            self.chain = response.data if response.data else []
            
            if not self.chain:
                self.create_genesis_block()
        except Exception as e:
            print(f"Error loading DB: {e}")

    def create_genesis_block(self):
        """Membuat blok awal sistem (Blok 0)"""
        genesis_data = {
            "nama_event": "System Start",
            "nama_peserta": "Genesis Block",
            "previous_hash": "0",
            "cert_hash": "0"
        }
        supabase.table("sertifikat_digital").insert(genesis_data).execute()
        self.load_data()

    def get_previous_hash(self):
        """Mengambil hash dari blok terakhir yang ada di database"""
        return self.chain[-1]['cert_hash'] if self.chain else "0"

    @staticmethod
    def calculate_hash(block_data):
        """
        Menghash 6 Metadata + Previous Hash menggunakan SHA-256.
        Inti dari integritas data (Anti-Tamper).
        """

        encoded_block = json.dumps(block_data, sort_keys=True).encode()
        return hashlib.sha256(encoded_block).hexdigest() [cite: 1]

    def add_block(self, metadata):
        """
        Proses pembuatan blok baru sesuai metadata dari Pak Hendra
        """
        prev_hash = self.get_previous_hash()
        
        block_content = {
            "nama_event": metadata['nama_event'],
            "lokasi_nama": metadata['lokasi_nama'],
            "latitude": metadata['latitude'],
            "longitude": metadata['longitude'],
            "waktu_mulai": metadata['waktu_mulai'],
            "keterangan": metadata['keterangan'], 
            "nama_peserta": metadata['nama_peserta'],
            "previous_hash": prev_hash
        }
        
        current_hash = self.calculate_hash(block_content) [cite: 1]
        block_content['cert_hash'] = current_hash
        
        supabase.table("sertifikat_digital").insert(block_content).execute()
        self.load_data() # Refresh memori lokal
        return current_hash

blockchain = Blockchain()


@app.route('/login', methods=['POST'])
def login():
    """Validasi Admin berdasarkan file .env"""
    data = request.json
    if data.get('username') == ADMIN_USERNAME and data.get('password') == ADMIN_PASSWORD:
        return jsonify({"success": True, "token": "access-granted-umrah"}), 200
    return jsonify({"success": False, "message": "Login Gagal"}), 401

@app.route('/issue-sertifikat', methods=['POST'])
def issue_sertifikat():
    """Endpoint untuk Admin membuat sertifikat baru"""
    metadata = request.json
    
    required = ['nama_event', 'lokasi_nama', 'latitude', 'longitude', 'waktu_mulai', 'keterangan', 'nama_peserta']
    if not all(k in metadata for k in required):
        return jsonify({"message": "Data metadata tidak lengkap!"}), 400
    
    new_hash = blockchain.add_block(metadata)
    return jsonify({
        "success": True, 
        "hash": new_hash,
        "message": "Sertifikat berhasil diamankan ke Blockchain"
    }), 201

@app.route('/verify/<cert_hash>', methods=['GET'])
def verify(cert_hash):
    """Endpoint untuk Publik memverifikasi sertifikat lewat QR Code"""
    blockchain.load_data() # Pastikan data paling update
    
    match = next((b for b in blockchain.chain if b['cert_hash'] == cert_hash), None)
    
    if match:
        return jsonify({
            "status": "VALID", 
            "message": "Sertifikat Terdaftar dan ASLI",
            "data": match
        }), 200
    else:
        return jsonify({
            "status": "INVALID", 
            "message": "Sertifikat TIDAK DITEMUKAN"
        }), 404

if __name__ == '__main__':

    app.run(debug=True)