from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from collections import Counter
from werkzeug.utils import secure_filename
from export import export_clinics
from import_data import import_clinics

app = Flask(__name__)
app.secret_key = 'clinic-secret-key-bcmedia-2026'

# 資料庫設定
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///clinics.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://')

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 診所資料模型
class Clinic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(50))  # 縣市
    district = db.Column(db.String(50))  # 區域
    name = db.Column(db.String(200))  # 診所名稱
    media_items = db.Column(db.String(500))  # 媒體項目
    specialties = db.Column(db.String(500))  # 科別
    address = db.Column(db.String(300))  # 地址
    phone = db.Column(db.String(50))  # 電話
    contact_person = db.Column(db.String(100))  # 負責人
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 登入路由
@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/analytics')
def analytics():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('analytics.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if username == 'admin' and password == 'Bcm13011579!@':
            session['user'] = 'admin'
            session['role'] = 'admin'
            return jsonify({'success': True})
        elif username == 'user' and password == 'Bcm13011579':
            session['user'] = 'user'
            session['role'] = 'user'
            return jsonify({'success': True})
        else:
            return jsonify({'error': '帳號或密碼錯誤'}), 401
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 診所 API
@app.route('/api/clinics', methods=['GET'])
def get_clinics():
    search = request.args.get('search', '')
    region = request.args.get('region', '')
    specialty = request.args.get('specialty', '')
    
    query = Clinic.query
    
    if search:
        query = query.filter(
            (Clinic.name.contains(search)) |
            (Clinic.contact_person.contains(search))
        )
    
    if region:
        query = query.filter(Clinic.region == region)
    
    if specialty:
        query = query.filter(Clinic.specialties.contains(specialty))
    
    clinics = query.all()
    
    return jsonify([{
        'id': c.id,
        'region': c.region,
        'district': c.district,
        'name': c.name,
        'media_items': c.media_items,
        'specialties': c.specialties,
        'address': c.address,
        'phone': c.phone,
        'contact_person': c.contact_person,
        'created_at': c.created_at.strftime('%Y-%m-%d %H:%M:%S') if c.created_at else None
    } for c in clinics])

@app.route('/api/clinics', methods=['POST'])
def create_clinic():
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    
    data = request.get_json()
    
    clinic = Clinic(
        region=data.get('region'),
        district=data.get('district'),
        name=data.get('name'),
        media_items=data.get('media_items'),
        specialties=data.get('specialties'),
        address=data.get('address'),
        phone=data.get('phone'),
        contact_person=data.get('contact_person')
    )
    
    db.session.add(clinic)
    db.session.commit()
    
    return jsonify({'success': True, 'id': clinic.id})

@app.route('/api/clinics/<int:clinic_id>', methods=['PUT'])
def update_clinic(clinic_id):
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    
    clinic = Clinic.query.get_or_404(clinic_id)
    data = request.get_json()
    
    clinic.region = data.get('region')
    clinic.district = data.get('district')
    clinic.name = data.get('name')
    clinic.media_items = data.get('media_items')
    clinic.specialties = data.get('specialties')
    clinic.address = data.get('address')
    clinic.phone = data.get('phone')
    clinic.contact_person = data.get('contact_person')
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/clinics/<int:clinic_id>', methods=['DELETE'])
def delete_clinic(clinic_id):
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    
    clinic = Clinic.query.get_or_404(clinic_id)
    db.session.delete(clinic)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/stats')
def get_stats():
    total = Clinic.query.count()
    
    # 計算有媒體項目的診所數量
    media_clinics = Clinic.query.filter(Clinic.media_items != None, Clinic.media_items != '').count()
    
    return jsonify({
        'total': total,
        'media_clinics': media_clinics,
        'no_media_clinics': total - media_clinics
    })

@app.route('/api/analytics/regions')
def get_region_stats():
    """各縣市診所數量統計"""
    clinics = Clinic.query.all()
    region_count = Counter(c.region for c in clinics if c.region)
    
    return jsonify({
        'regions': list(region_count.keys()),
        'counts': list(region_count.values())
    })

@app.route('/api/analytics/specialties')
def get_specialty_stats():
    """科別統計（處理複選）"""
    clinics = Clinic.query.all()
    specialty_list = []
    
    for clinic in clinics:
        if clinic.specialties:
            specs = [s.strip() for s in clinic.specialties.split(',')]
            specialty_list.extend(specs)
    
    specialty_count = Counter(specialty_list)
    
    return jsonify({
        'specialties': list(specialty_count.keys()),
        'counts': list(specialty_count.values())
    })

@app.route('/api/analytics/taiwan_map')
def get_taiwan_map_data():
    """台灣地圖資料（縣市對應）"""
    clinics = Clinic.query.all()
    region_count = Counter(c.region for c in clinics if c.region)
    
    # ECharts 台灣地圖的縣市名稱對應
    map_data = []
    for region, count in region_count.items():
        map_data.append({
            'name': region,
            'value': count
        })
    
    return jsonify(map_data)

# 匯出路由
@app.route('/api/export', methods=['GET'])
def export_data():
    """匯出診所資料"""
    search = request.args.get('search', '')
    region = request.args.get('region', '')
    specialty = request.args.get('specialty', '')
    media_item = request.args.get('media_item', '')
    
    query = Clinic.query
    
    # 套用篩選條件（與列表頁相同的邏輯）
    if search:
        query = query.filter(
            (Clinic.name.contains(search)) |
            (Clinic.address.contains(search)) |
            (Clinic.contact_person.contains(search))
        )
    
    if region:
        query = query.filter(Clinic.region == region)
    
    if specialty:
        query = query.filter(Clinic.specialties.contains(specialty))
    
    if media_item:
        query = query.filter(Clinic.media_items.contains(media_item))
    
    clinics = query.all()
    
    if not clinics:
        return jsonify({'error': '沒有符合條件的資料'}), 400
    
    # 產生 Excel
    output = export_clinics(clinics)
    
    # 產生檔名
    filename = f'診所清單_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

# 匯入路由
@app.route('/api/import', methods=['POST'])
def import_data():
    """匯入診所資料"""
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': '沒有上傳檔案'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': '沒有選擇檔案'}), 400
    
    if not file.filename.endswith('.xlsx'):
        return jsonify({'error': '只接受 .xlsx 格式'}), 400
    
    # 儲存暫存檔案
    filename = secure_filename(file.filename)
    temp_path = os.path.join('/tmp', filename)
    file.save(temp_path)
    
    # 匯入資料
    with app.app_context():
        result = import_clinics(temp_path, db, Clinic)
    
    # 刪除暫存檔案
    os.remove(temp_path)
    
    return jsonify(result)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8081, debug=True)
