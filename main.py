import os
import hashlib
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Konfigurasi dari .env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

print("=" * 50)
print("🚀 VeriZh Chain Backend Starting...")
print(f"📡 SUPABASE_URL: {SUPABASE_URL}")
print(f"🔑 SUPABASE_KEY (first 10 chars): {SUPABASE_KEY[:10] if SUPABASE_KEY else 'None'}...")
print(f"👤 ADMIN_USERNAME: {ADMIN_USERNAME}")
print("=" * 50)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase client created successfully")
    
    # Test koneksi ke Supabase
    test_query = supabase.table("sertifikat_digital").select("*").limit(1).execute()
    print(f"📊 Test query successful: {len(test_query.data)} rows found")
except Exception as e:
    print(f"❌ Supabase initialization error: {e}")
    supabase = None

# ✅ CORS UPDATED with new frontend URL
app = Flask(__name__)
CORS(app, origins=[
    "http://localhost:3000", 
    "http://localhost:5173", 
    "https://vadser.vercel.app"  # FRONTEND BARU
])

def calculate_hash(block_data):
    """
    Menghitung SHA-256 hash dari block data
    Args:
        block_data (dict): Data blok yang akan di-hash
    Returns:
        str: Hash SHA-256 dalam format hex
    """
    try:
        # Urutkan keys agar konsisten
        block_string = json.dumps(block_data, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()
    except Exception as e:
        print(f"❌ Error calculating hash: {e}")
        return None

def get_last_block_hash():
    """
    Mengambil hash dari blok terakhir di blockchain
    Returns:
        str: Hash dari blok terakhir, atau "0" jika belum ada blok
    """
    try:
        if supabase is None:
            print("❌ Supabase client not initialized")
            return "0"
            
        # Ambil blok terakhir berdasarkan ID (descending)
        result = supabase.table("sertifikat_digital") \
            .select("cert_hash") \
            .order("id", desc=True) \
            .limit(1) \
            .execute()
        
        if result.data and len(result.data) > 0:
            last_hash = result.data[0]['cert_hash']
            print(f"🔗 Last block hash: {last_hash}")
            return last_hash
        else:
            print("🔗 No blocks found, this is genesis block")
            return "0"  # Genesis block
            
    except Exception as e:
        print(f"❌ Error getting last block hash: {e}")
        return "0"

def validate_certificate_data(data):
    """
    Validasi data sertifikat yang diterima dari frontend
    Args:
        data (dict): Data yang akan divalidasi
    Returns:
        tuple: (is_valid, error_message)
    """
    # Daftar field yang wajib ada
    required_fields = [
        'nama_event', 'nama_lokasi', 'latitude', 'longitude',
        'waktu_mulai', 'waktu_selesai', 'nama_peserta', 'keterangan'
    ]
    
    # Cek kelengkapan field
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    
    if missing_fields:
        return False, f"Field wajib tidak lengkap: {', '.join(missing_fields)}"
    
    # Validasi tipe data latitude/longitude
    try:
        lat = float(data['latitude'])
        lng = float(data['longitude'])
        
        # Validasi range
        if lat < -90 or lat > 90:
            return False, "Latitude harus antara -90 dan 90"
        if lng < -180 or lng > 180:
            return False, "Longitude harus antara -180 dan 180"
            
    except ValueError:
        return False, "Latitude dan Longitude harus berupa angka"
    
    try:
        waktu_mulai = data['waktu_mulai']
        waktu_selesai = data['waktu_selesai']
        
        # Bisa ditambahkan validasi format tanggal jika perlu
        if waktu_selesai <= waktu_mulai:
            return False, "Waktu selesai harus setelah waktu mulai"
            
    except Exception as e:
        print(f"⚠️ Warning: {e}")
    
    return True, None


@app.route('/', methods=['GET'])
def home():
    """Endpoint utama untuk mengecek status API"""
    return jsonify({
        "message": "VeriZh Chain API",
        "status": "online",
        "version": "1.0.0",
        "endpoints": [
            "/login [POST]",
            "/issue-sertifikat [POST]",
            "/verify/<cert_hash> [GET]",
            "/chain [GET]",
            "/reset-chain [POST] (admin only)"
        ]
    }), 200

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if username == "grayesi" and password == "anakkeren":
            return jsonify({
                "success": True,
                "token": "access-granted-umrah",
                "message": "Login berhasil !"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Salah , coba lagi"
            }), 401
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@app.route('/issue-sertifikat', methods=['POST'])
def issue_sertifikat():
    """
    Endpoint untuk membuat sertifikat baru
    Request body: 8 field lengkap
    Response: { "success": true, "hash": "...", "previous_hash": "...", "message": "..." }
    """
    try:

        if supabase is None:
            return jsonify({
                "success": False,
                "message": "Database connection error"
            }), 500
        

        data = request.json
        print("\n" + "="*50)
        print("📨 New certificate request received:")
        print(json.dumps(data, indent=2))
        

        is_valid, error_message = validate_certificate_data(data)
        if not is_valid:
            return jsonify({
                "success": False,
                "message": error_message
            }), 400
        

        previous_hash = get_last_block_hash()
        print(f"🔗 Previous hash: {previous_hash}")
        

        block_data = {
            "nama_event": data['nama_event'].strip(),
            "nama_lokasi": data['nama_lokasi'].strip(),
            "latitude": float(data['latitude']),
            "longitude": float(data['longitude']),
            "waktu_mulai": data['waktu_mulai'],
            "waktu_selesai": data['waktu_selesai'],
            "nama_peserta": data['nama_peserta'].strip(),
            "keterangan": data['keterangan'].strip(),
            "previous_hash": previous_hash
        }
        

        cert_hash = calculate_hash(block_data)
        if not cert_hash:
            return jsonify({
                "success": False,
                "message": "Error generating hash"
            }), 500
            
        print(f"🔐 New hash generated: {cert_hash}")
        

        insert_data = {
            **block_data,  # Semua field termasuk previous_hash
            "cert_hash": cert_hash
        }
        

        print("💾 Inserting to Supabase...")
        result = supabase.table("sertifikat_digital").insert(insert_data).execute()
        print("✅ Insert successful!")
        

        return jsonify({
            "success": True,
            "hash": cert_hash,
            "previous_hash": previous_hash,
            "message": "Sertifikat berhasil ditambahkan ke blockchain"
        }), 201
        
    except Exception as e:
        print(f"❌ Error in issue_sertifikat: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/verify/<cert_hash>', methods=['GET'])
def verify(cert_hash):
    """
    Endpoint untuk verifikasi sertifikat berdasarkan hash
    Args:
        cert_hash (str): Hash sertifikat yang akan diverifikasi
    Returns:
        JSON: Data sertifikat jika ditemukan
    """
    try:
        print(f"🔍 Verifying hash: {cert_hash}")
        
        if supabase is None:
            return jsonify({
                "status": "ERROR",
                "message": "Database connection error"
            }), 500
        
        result = supabase.table("sertifikat_digital") \
            .select("*") \
            .eq("cert_hash", cert_hash) \
            .execute()
        
        if result.data and len(result.data) > 0:
            certificate = result.data[0]
            print(f"✅ Certificate found: {certificate['nama_peserta']}")
            
            return jsonify({
                "status": "VALID",
                "message": "Sertifikat terdaftar dan ASLI",
                "data": certificate
            }), 200
        else:
            print(f"❌ Certificate not found for hash: {cert_hash}")
            return jsonify({
                "status": "INVALID",
                "message": "Sertifikat tidak ditemukan"
            }), 404
            
    except Exception as e:
        print(f"❌ Error in verify: {e}")
        return jsonify({
            "status": "ERROR",
            "message": str(e)
        }), 500

@app.route('/chain', methods=['GET'])
def get_chain():
    """
    Endpoint untuk melihat seluruh blockchain
    Returns:
        JSON: Seluruh data blockchain
    """
    try:
        print("📊 Fetching entire blockchain...")
        
        if supabase is None:
            return jsonify({
                "status": "error",
                "message": "Database connection error"
            }), 500
        
        result = supabase.table("sertifikat_digital") \
            .select("*") \
            .order("id") \
            .execute()
        
        chain_data = result.data if result.data else []
        
        print(f"📊 Blockchain length: {len(chain_data)} blocks")
        
        return jsonify({
            "status": "success",
            "length": len(chain_data),
            "chain": chain_data
        }), 200
        
    except Exception as e:
        print(f"❌ Error in get_chain: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/reset-chain', methods=['POST'])
def reset_chain():
    """
    ENDPOINT DARURAT - Hanya untuk development!
    Mereset seluruh blockchain dengan menghapus semua data
    """
    try:
        print("⚠️⚠️⚠️ RESET CHAIN REQUESTED ⚠️⚠️⚠️")
        
        # Verifikasi token (sederhana)
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != 'Bearer access-granted-umrah':
            return jsonify({
                "success": False,
                "message": "Unauthorized"
            }), 401
        
        if supabase is None:
            return jsonify({
                "success": False,
                "message": "Database connection error"
            }), 500
        
        # Hapus semua data
        supabase.table("sertifikat_digital").delete().neq("id", 0).execute()
        print("✅ All data deleted")
        
        # Buat genesis block baru
        genesis_data = {
            "nama_event": "System Genesis",
            "nama_lokasi": "System",
            "latitude": 0,
            "longitude": 0,
            "waktu_mulai": "2024-01-01T00:00",
            "waktu_selesai": "2024-01-01T00:00",
            "nama_peserta": "System",
            "keterangan": "Genesis Block",
            "previous_hash": "0",
            "cert_hash": "0"
        }
        
        supabase.table("sertifikat_digital").insert(genesis_data).execute()
        print("✅ Genesis block created")
        
        return jsonify({
            "success": True,
            "message": "Chain has been reset"
        }), 200
        
    except Exception as e:
        print(f"❌ Error in reset_chain: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handler untuk endpoint yang tidak ditemukan"""
    return jsonify({
        "status": "error",
        "message": "Endpoint tidak ditemukan"
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handler untuk method yang tidak diizinkan"""
    return jsonify({
        "status": "error",
        "message": "Method tidak diizinkan"
    }), 405

@app.errorhandler(500)
def internal_error(error):
    """Handler untuk internal server error"""
    return jsonify({
        "status": "error",
        "message": "Internal server error"
    }), 500


if __name__ == '__main__':
    print("\n" + "="*50)
    print("✅ VeriZh Chain Backend Ready!")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)