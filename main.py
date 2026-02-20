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
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

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
                print("Chain kosong, membuat genesis block...")
                self.create_genesis_block()
            else:
                print(f"Chain terload: {len(self.chain)} blocks")
        except Exception as e:
            print(f"Error loading DB: {e}")

    def create_genesis_block(self):
        """Membuat blok awal sistem (Blok 0) dengan 8 field lengkap"""
        try:
            genesis_data = {
                "nama_event": "System Start",
                "nama_lokasi": "System Location",  # ← PERBAIKAN: nama_lokasi
                "latitude": 0.0,
                "longitude": 0.0,
                "waktu_mulai": "2024-01-01T00:00",
                "waktu_selesai": "2024-01-01T00:00",
                "nama_peserta": "Genesis Block",
                "keterangan": "Genesis Block of VeriZh Chain",
                "previous_hash": "0",
                "cert_hash": "0"
            }
            
            print("Membuat genesis block:", genesis_data)
            result = supabase.table("sertifikat_digital").insert(genesis_data).execute()
            print("Genesis block created:", result)
            
            self.load_data()
        except Exception as e:
            print(f"Error creating genesis block: {e}")

    def get_previous_hash(self):
        """Mengambil hash dari blok terakhir yang ada di database"""
        return self.chain[-1]['cert_hash'] if self.chain else "0"

    @staticmethod
    def calculate_hash(block_data):
        """Menghash 8 Metadata + Previous Hash menggunakan SHA-256"""
        encoded_block = json.dumps(block_data, sort_keys=True).encode()
        return hashlib.sha256(encoded_block).hexdigest()

    def add_block(self, metadata):
        """Proses pembuatan blok baru dengan 8 field"""
        try:
            prev_hash = self.get_previous_hash()
            
            # PERBAIKAN PENTING: gunakan nama_lokasi, BUKAN lokasi_nama
            block_content = {
                "nama_event": metadata['nama_event'],
                "nama_lokasi": metadata['nama_lokasi'],  
                "latitude": float(metadata['latitude']),
                "longitude": float(metadata['longitude']),
                "waktu_mulai": metadata['waktu_mulai'],
                "waktu_selesai": metadata['waktu_selesai'],
                "nama_peserta": metadata['nama_peserta'],
                "keterangan": metadata['keterangan'],
                "previous_hash": prev_hash
            }
            
            print("Block content:", block_content)
            
            current_hash = self.calculate_hash(block_content)
            block_content['cert_hash'] = current_hash
            
            result = supabase.table("sertifikat_digital").insert(block_content).execute()
            print("Block saved:", result)
            
            self.load_data() 
            return current_hash
            
        except Exception as e:
            print(f"Error adding block: {e}")
            raise e

blockchain = Blockchain()

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    if data.get('username') == ADMIN_USERNAME and data.get('password') == ADMIN_PASSWORD:
        return jsonify({"success": True, "token": "access-granted-umrah"}), 200
    return jsonify({"success": False, "message": "Login Gagal"}), 401

@app.route('/issue-sertifikat', methods=['POST'])
def issue_sertifikat():
    try:
        metadata = request.json
        print("Received data:", metadata)
        
        # PERBAIKAN: required fields dengan nama_lokasi
        required = ['nama_event', 'nama_lokasi', 'latitude', 'longitude', 
                   'waktu_mulai', 'waktu_selesai', 'nama_peserta', 'keterangan']
        
        # Cek kelengkapan data
        missing = [field for field in required if field not in metadata]
        if missing:
            return jsonify({
                "success": False, 
                "message": f"Data tidak lengkap! Missing: {missing}"
            }), 400
        
        # Validasi tipe data
        try:
            float(metadata['latitude'])
            float(metadata['longitude'])
        except ValueError:
            return jsonify({
                "success": False,
                "message": "Latitude dan Longitude harus berupa angka"
            }), 400
        
        new_hash = blockchain.add_block(metadata)
        
        return jsonify({
            "success": True, 
            "hash": new_hash,
            "message": "Sertifikat berhasil diamankan ke Blockchain"
        }), 201
        
    except Exception as e:
        print(f"Error in issue_sertifikat: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/verify/<cert_hash>', methods=['GET'])
def verify(cert_hash):
    blockchain.load_data()
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

@app.route('/chain', methods=['GET'])
def get_chain():
    """Endpoint untuk melihat seluruh isi blockchain"""
    try:
        blockchain.load_data()
        return jsonify({
            "status": "success",
            "length": len(blockchain.chain),
            "chain": blockchain.chain
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/reset-chain', methods=['POST'])
def reset_chain():
    """RESET DARURAT - Hanya untuk testing!"""
    try:
        # Hapus semua data
        supabase.table("sertifikat_digital").delete().neq("id", 0).execute()
        # Buat genesis block baru
        blockchain.chain = []
        blockchain.create_genesis_block()
        return jsonify({"success": True, "message": "Chain direset!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "VeriZh Chain API",
        "status": "online",
        "endpoints": ["/login", "/issue-sertifikat", "/verify/<hash>", "/chain", "/reset-chain"]
    })

if __name__ == '__main__':
    app.run(debug=True)