from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
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
    region = db.Column(db.String(50))
    district = db.Column(db.String(50))
    name = db.Column(db.String(200))
    health_mall = db.Column(db.String(10), default='否')        # 保留舊欄位
    hundred_position = db.Column(db.String(10), default='否')   # 保留舊欄位
    media_items = db.Column(db.String(500))                     # 保留舊欄位（供匯出用）
    specialties = db.Column(db.String(500))
    address = db.Column(db.String(300))
    phone = db.Column(db.String(50))
    contact_person = db.Column(db.String(100))
    business_hours = db.Column(db.String(200))
    note = db.Column(db.Text)
    col_yaodai = db.Column(db.Boolean, default=False)
    col_haibao = db.Column(db.Boolean, default=False)
    col_paiyang = db.Column(db.Boolean, default=False)
    col_baiwei = db.Column(db.Boolean, default=False)
    health_mall_status = db.Column(db.String(20), default='否')     # 合作中/暫停/結束/否
    health_mall_start_date = db.Column(db.Date)
    health_mall_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── 頁面路由 ────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/health-mall')
def health_mall_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('health_mall.html')

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


# ── 診所管理 API ─────────────────────────────────────────────

@app.route('/api/clinics', methods=['GET'])
def get_clinics():
    search   = request.args.get('search', '')
    region   = request.args.get('region', '')
    specialty = request.args.get('specialty', '')
    col_item = request.args.get('col_item', '')

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
    if col_item == 'yaodai':
        query = query.filter(Clinic.col_yaodai == True)
    elif col_item == 'haibao':
        query = query.filter(Clinic.col_haibao == True)
    elif col_item == 'paiyang':
        query = query.filter(Clinic.col_paiyang == True)
    elif col_item == 'baiwei':
        query = query.filter(Clinic.col_baiwei == True)

    clinics = query.all()
    return jsonify([{
        'id': c.id,
        'region': c.region,
        'district': c.district,
        'name': c.name,
        'col_yaodai': c.col_yaodai or False,
        'col_haibao': c.col_haibao or False,
        'col_paiyang': c.col_paiyang or False,
        'col_baiwei': c.col_baiwei or False,
        'specialties': c.specialties,
        'address': c.address,
        'phone': c.phone,
        'contact_person': c.contact_person,
        'business_hours': c.business_hours,
        'note': c.note,
        'created_at': c.created_at.strftime('%Y-%m-%d %H:%M:%S') if c.created_at else None
    } for c in clinics])

@app.route('/api/clinics', methods=['POST'])
def create_clinic():
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    try:
        data = request.get_json()
        clinic = Clinic(
            region=data.get('region'),
            district=data.get('district'),
            name=data.get('name'),
            col_yaodai=data.get('col_yaodai', False),
            col_haibao=data.get('col_haibao', False),
            col_paiyang=data.get('col_paiyang', False),
            col_baiwei=data.get('col_baiwei', False),
            specialties=data.get('specialties'),
            address=data.get('address'),
            phone=data.get('phone'),
            contact_person=data.get('contact_person'),
            business_hours=data.get('business_hours'),
            note=data.get('note')
        )
        db.session.add(clinic)
        db.session.commit()
        return jsonify({'success': True, 'id': clinic.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'儲存失敗: {str(e)}'}), 500

@app.route('/api/clinics/<int:clinic_id>', methods=['PUT'])
def update_clinic(clinic_id):
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    try:
        clinic = Clinic.query.get_or_404(clinic_id)
        data = request.get_json()
        clinic.region = data.get('region')
        clinic.district = data.get('district')
        clinic.name = data.get('name')
        clinic.col_yaodai = data.get('col_yaodai', False)
        clinic.col_haibao = data.get('col_haibao', False)
        clinic.col_paiyang = data.get('col_paiyang', False)
        clinic.col_baiwei = data.get('col_baiwei', False)
        clinic.specialties = data.get('specialties')
        clinic.address = data.get('address')
        clinic.phone = data.get('phone')
        clinic.contact_person = data.get('contact_person')
        clinic.business_hours = data.get('business_hours')
        clinic.note = data.get('note')
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'更新失敗: {str(e)}'}), 500

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
    return jsonify({'total': total})


# ── 健康醫購 API ─────────────────────────────────────────────

HM_STATUSES = ('合作中', '暫停', '結束')

@app.route('/api/health-mall', methods=['GET'])
def get_health_mall():
    search    = request.args.get('search', '')
    region    = request.args.get('region', '')
    specialty = request.args.get('specialty', '')
    status    = request.args.get('status', '')

    query = Clinic.query.filter(Clinic.health_mall_status.in_(HM_STATUSES))

    if search:
        query = query.filter(
            (Clinic.name.contains(search)) |
            (Clinic.contact_person.contains(search))
        )
    if region:
        query = query.filter(Clinic.region == region)
    if specialty:
        query = query.filter(Clinic.specialties.contains(specialty))
    if status:
        query = query.filter(Clinic.health_mall_status == status)

    clinics = query.all()
    return jsonify([_hm_json(c) for c in clinics])

@app.route('/api/health-mall/stats')
def get_health_mall_stats():
    total  = Clinic.query.filter(Clinic.health_mall_status.in_(HM_STATUSES)).count()
    active = Clinic.query.filter(Clinic.health_mall_status == '合作中').count()
    return jsonify({'total': total, 'active': active})

@app.route('/api/health-mall', methods=['POST'])
def create_health_mall():
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    try:
        data = request.get_json()
        clinic = Clinic(
            region=data.get('region'),
            district=data.get('district'),
            name=data.get('name'),
            specialties=data.get('specialties'),
            address=data.get('address'),
            phone=data.get('phone'),
            contact_person=data.get('contact_person'),
            health_mall_status=data.get('health_mall_status', '合作中'),
            health_mall_start_date=_parse_date(data.get('health_mall_start_date')),
            health_mall_note=data.get('health_mall_note'),
        )
        db.session.add(clinic)
        db.session.commit()
        return jsonify({'success': True, 'id': clinic.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'儲存失敗: {str(e)}'}), 500

@app.route('/api/health-mall/<int:clinic_id>', methods=['PUT'])
def update_health_mall(clinic_id):
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    try:
        clinic = Clinic.query.get_or_404(clinic_id)
        data = request.get_json()
        clinic.region = data.get('region')
        clinic.district = data.get('district')
        clinic.name = data.get('name')
        clinic.specialties = data.get('specialties')
        clinic.address = data.get('address')
        clinic.phone = data.get('phone')
        clinic.contact_person = data.get('contact_person')
        clinic.health_mall_status = data.get('health_mall_status', '合作中')
        clinic.health_mall_start_date = _parse_date(data.get('health_mall_start_date'))
        clinic.health_mall_note = data.get('health_mall_note')
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'更新失敗: {str(e)}'}), 500

@app.route('/api/health-mall/<int:clinic_id>', methods=['DELETE'])
def delete_health_mall(clinic_id):
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    clinic = Clinic.query.get_or_404(clinic_id)
    db.session.delete(clinic)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/health-mall/export')
def export_health_mall():
    search    = request.args.get('search', '')
    region    = request.args.get('region', '')
    specialty = request.args.get('specialty', '')
    status    = request.args.get('status', '')

    query = Clinic.query.filter(Clinic.health_mall_status.in_(HM_STATUSES))
    if search:
        query = query.filter(
            (Clinic.name.contains(search)) |
            (Clinic.contact_person.contains(search))
        )
    if region:
        query = query.filter(Clinic.region == region)
    if specialty:
        query = query.filter(Clinic.specialties.contains(specialty))
    if status:
        query = query.filter(Clinic.health_mall_status == status)

    clinics = query.all()
    if not clinics:
        return jsonify({'error': '沒有符合條件的資料'}), 400

    output = export_clinics(clinics)
    filename = f'健康醫購_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


# ── 分析 API ─────────────────────────────────────────────────

@app.route('/api/analytics/regions')
def get_region_stats():
    clinics = Clinic.query.all()
    region_count = Counter(c.region for c in clinics if c.region)
    return jsonify({'regions': list(region_count.keys()), 'counts': list(region_count.values())})

@app.route('/api/analytics/specialties')
def get_specialty_stats():
    clinics = Clinic.query.all()
    specialty_list = []
    for clinic in clinics:
        if clinic.specialties:
            specialty_list.extend(s.strip() for s in clinic.specialties.split(','))
    specialty_count = Counter(specialty_list)
    return jsonify({'specialties': list(specialty_count.keys()), 'counts': list(specialty_count.values())})

@app.route('/api/analytics/taiwan_map')
def get_taiwan_map_data():
    clinics = Clinic.query.all()
    region_count = Counter(c.region for c in clinics if c.region)
    return jsonify([{'name': r, 'value': v} for r, v in region_count.items()])


# ── 匯出/匯入 ────────────────────────────────────────────────

@app.route('/api/export', methods=['GET'])
def export_data():
    search    = request.args.get('search', '')
    region    = request.args.get('region', '')
    specialty = request.args.get('specialty', '')
    col_item  = request.args.get('col_item', '')

    query = Clinic.query
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
    if col_item == 'yaodai':
        query = query.filter(Clinic.col_yaodai == True)
    elif col_item == 'haibao':
        query = query.filter(Clinic.col_haibao == True)
    elif col_item == 'paiyang':
        query = query.filter(Clinic.col_paiyang == True)
    elif col_item == 'baiwei':
        query = query.filter(Clinic.col_baiwei == True)

    clinics = query.all()
    if not clinics:
        return jsonify({'error': '沒有符合條件的資料'}), 400

    output = export_clinics(clinics)
    filename = f'診所清單_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/import', methods=['POST'])
def import_data():
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    if 'file' not in request.files:
        return jsonify({'error': '沒有上傳檔案'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '沒有選擇檔案'}), 400
    if not file.filename.endswith('.xlsx'):
        return jsonify({'error': '只接受 .xlsx 格式'}), 400

    filename = secure_filename(file.filename)
    temp_path = os.path.join('/tmp', filename)
    file.save(temp_path)
    with app.app_context():
        result = import_clinics(temp_path, db, Clinic)
    os.remove(temp_path)
    return jsonify(result)


# ── 工具函式 ─────────────────────────────────────────────────

def _parse_date(s):
    if s:
        try:
            return datetime.strptime(s, '%Y-%m-%d').date()
        except ValueError:
            return None
    return None

def _hm_json(c):
    return {
        'id': c.id,
        'region': c.region,
        'district': c.district,
        'name': c.name,
        'specialties': c.specialties,
        'address': c.address,
        'phone': c.phone,
        'contact_person': c.contact_person,
        'health_mall_status': c.health_mall_status or '否',
        'health_mall_start_date': c.health_mall_start_date.strftime('%Y-%m-%d') if c.health_mall_start_date else '',
        'health_mall_note': c.health_mall_note or '',
    }


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8081, debug=True)
