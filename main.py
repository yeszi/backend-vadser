import os
from supabase import create_client
from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib
import json
from dotenv import load_dotenv  # ← INI KURANG!

load_dotenv()  # ← INI JUGA KURANG!

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

print(f"URL: {SUPABASE_URL}")
print(f"Username: {ADMIN_USERNAME}")

# Inisialisasi Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
CORS(app)

# ========== ENDPOINT LOGIN (INI YANG MISSING!) ==========
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        print(f"Login attempt: {data.get('username')}")
        
        if data.get('username') == ADMIN_USERNAME and data.get('password') == ADMIN_PASSWORD:
            return jsonify({
                "success": True, 
                "token": "access-granted-umrah"
            }), 200
        else:
            return jsonify({
                "success": False, 
                "message": "Username atau password salah"
            }), 401
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/issue-sertifikat', methods=['POST'])
def issue_sertifikat():
    try:
        data = request.json
        print("📨 Data received:", data)
        
        # Validasi data
        required = ['nama_event', 'nama_lokasi', 'latitude', 'longitude', 
                   'waktu_mulai', 'waktu_selesai', 'nama_peserta', 'keterangan']
        
        for field in required:
            if field not in data:
                return jsonify({
                    "success": False,
                    "message": f"Field {field} wajib diisi"
                }), 400
        
        # Generate hash dari semua data
        hash_string = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        
        # Data untuk insert
        insert_data = {
            "nama_event": data['nama_event'],
            "nama_lokasi": data['nama_lokasi'],
            "latitude": float(data['latitude']),
            "longitude": float(data['longitude']),
            "waktu_mulai": data['waktu_mulai'],
            "waktu_selesai": data['waktu_selesai'],
            "nama_peserta": data['nama_peserta'],
            "keterangan": data['keterangan'],
            "previous_hash": "0",
            "cert_hash": hash_string
        }
        
        # INSERT ke Supabase
        result = supabase.table("sertifikat_digital").insert(insert_data).execute()
        print("✅ Insert success")
        
        return jsonify({
            "success": True,
            "hash": hash_string,
            "message": "Sertifikat berhasil dibuat"
        }), 201
        
    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/verify/<cert_hash>', methods=['GET'])
def verify(cert_hash):
    try:
        result = supabase.table("sertifikat_digital").select("*").eq("cert_hash", cert_hash).execute()
        
        if result.data:
            return jsonify({
                "status": "VALID",
                "data": result.data[0]
            }), 200
        else:
            return jsonify({
                "status": "INVALID",
                "message": "Sertifikat tidak ditemukan"
            }), 404
            
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": str(e)
        }), 500

@app.route('/chain', methods=['GET'])
def get_chain():
    try:
        result = supabase.table("sertifikat_digital").select("*").order("id").execute()
        return jsonify({
            "length": len(result.data),
            "chain": result.data
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "VeriZh Chain API",
        "status": "online",
        "endpoints": ["/login", "/issue-sertifikat", "/verify/<hash>", "/chain"]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)