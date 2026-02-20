import os
from supabase import create_client
from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib
import json

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # INI HARUS SERVICE_ROLE KEY
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# DEBUG: Cek key yang dipakai
print(f"URL: {SUPABASE_URL}")
print(f"KEY (first 20 chars): {SUPABASE_KEY[:20] if SUPABASE_KEY else 'None'}")
print(f"Key length: {len(SUPABASE_KEY) if SUPABASE_KEY else 0}")

# PASTIKAN menggunakan service_role key, BUKAN anon key
if SUPABASE_KEY and 'service_role' in SUPABASE_KEY:
    print("✅ Using SERVICE_ROLE key")
else:
    print("⚠️ WARNING: Not using service_role key!")

# Inisialisasi Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
CORS(app)

@app.route('/issue-sertifikat', methods=['POST'])
def issue_sertifikat():
    try:
        data = request.json
        print("📨 Data received:", data)
        
        # Generate hash
        hash_string = hashlib.sha256(json.dumps(data).encode()).hexdigest()
        
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
        
        # INSERT dengan service_role
        result = supabase.table("sertifikat_digital").insert(insert_data).execute()
        print("✅ Insert success:", result)
        
        return jsonify({
            "success": True,
            "hash": hash_string
        }), 201
        
    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/')
def home():
    return jsonify({"message": "VeriZh API"})

if __name__ == '__main__':
    app.run()