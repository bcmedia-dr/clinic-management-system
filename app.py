from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os, re
from collections import Counter
from io import BytesIO
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from werkzeug.utils import secure_filename
from export import export_clinics
from import_data import import_clinics, import_health_mall

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-only-for-local')

# 資料庫設定
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///clinics.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://')

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ── 資料模型 ─────────────────────────────────────────────────

class Clinic(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    region         = db.Column(db.String(50))
    district       = db.Column(db.String(50))
    name           = db.Column(db.String(200))
    media_items    = db.Column(db.String(500))                    # 舊欄位（保留）
    specialties    = db.Column(db.String(500))
    address        = db.Column(db.String(300))
    phone          = db.Column(db.String(50))
    contact_person = db.Column(db.String(100))
    business_hours = db.Column(db.String(200))
    note           = db.Column(db.Text)
    col_yaodai     = db.Column(db.Boolean, default=False)
    col_haibao     = db.Column(db.Boolean, default=False)
    col_paiyang    = db.Column(db.Boolean, default=False)
    col_baiwei     = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HealthMall(db.Model):
    __tablename__ = 'health_mall'
    id             = db.Column(db.Integer, primary_key=True)
    clinic_id      = db.Column(db.Integer, db.ForeignKey('clinic.id'), nullable=True)
    region         = db.Column(db.String(50))
    district       = db.Column(db.String(50))
    name           = db.Column(db.String(200))
    phone          = db.Column(db.String(50))
    contact_person = db.Column(db.String(100))
    specialties    = db.Column(db.String(500))
    address        = db.Column(db.String(300))
    status         = db.Column(db.String(20), default='合作中')
    start_date     = db.Column(db.Date)
    note           = db.Column(db.Text)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clinic = db.relationship('Clinic', backref=db.backref('health_mall_records', lazy=True))


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

@app.route('/campaign-match')
def campaign_match_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('campaign_match.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        if username == 'admin' and password == os.environ.get('ADMIN_PASSWORD', 'local-admin'):
            session['user'] = 'admin'
            session['role'] = 'admin'
            return jsonify({'success': True})
        elif username == 'user' and password == os.environ.get('USER_PASSWORD', 'local-user'):
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
    search    = request.args.get('search', '')
    region    = request.args.get('region', '')
    specialty = request.args.get('specialty', '')
    col_item  = request.args.get('col_item', '')

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
        'id':             c.id,
        'region':         c.region,
        'district':       c.district,
        'name':           c.name,
        'col_yaodai':     c.col_yaodai or False,
        'col_haibao':     c.col_haibao or False,
        'col_paiyang':    c.col_paiyang or False,
        'col_baiwei':     c.col_baiwei or False,
        'specialties':    c.specialties,
        'address':        c.address,
        'phone':          c.phone,
        'contact_person': c.contact_person,
        'business_hours': c.business_hours,
        'note':           c.note,
        'created_at':     c.created_at.strftime('%Y-%m-%d %H:%M:%S') if c.created_at else None
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
        clinic.region         = data.get('region')
        clinic.district       = data.get('district')
        clinic.name           = data.get('name')
        clinic.col_yaodai     = data.get('col_yaodai', False)
        clinic.col_haibao     = data.get('col_haibao', False)
        clinic.col_paiyang    = data.get('col_paiyang', False)
        clinic.col_baiwei     = data.get('col_baiwei', False)
        clinic.specialties    = data.get('specialties')
        clinic.address        = data.get('address')
        clinic.phone          = data.get('phone')
        clinic.contact_person = data.get('contact_person')
        clinic.business_hours = data.get('business_hours')
        clinic.note           = data.get('note')
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

@app.route('/api/clinics/search')
def search_clinics_for_hm():
    """供健康醫購新增時，從診所總表搜尋帶入資料"""
    q = request.args.get('q', '').strip()
    query = Clinic.query
    if q:
        query = query.filter(
            Clinic.name.contains(q) | Clinic.phone.contains(q)
        )
    clinics = query.order_by(Clinic.name).limit(30).all()
    return jsonify([{
        'id':             c.id,
        'region':         c.region or '',
        'district':       c.district or '',
        'name':           c.name or '',
        'phone':          c.phone or '',
        'contact_person': c.contact_person or '',
        'specialties':    c.specialties or '',
        'address':        c.address or '',
    } for c in clinics])


# ── 健康醫購 API ─────────────────────────────────────────────

@app.route('/api/health-mall', methods=['GET'])
def get_health_mall():
    search    = request.args.get('search', '')
    region    = request.args.get('region', '')
    specialty = request.args.get('specialty', '')
    status    = request.args.get('status', '')

    query = HealthMall.query

    if search:
        query = query.filter(
            HealthMall.name.contains(search) |
            HealthMall.contact_person.contains(search)
        )
    if region:
        query = query.filter(HealthMall.region == region)
    if specialty:
        query = query.filter(HealthMall.specialties.contains(specialty))
    if status:
        query = query.filter(HealthMall.status == status)

    items = query.all()
    return jsonify([_hm_json(h) for h in items])

@app.route('/api/health-mall/stats')
def get_health_mall_stats():
    total  = HealthMall.query.count()
    active = HealthMall.query.filter(HealthMall.status == '合作中').count()
    return jsonify({'total': total, 'active': active})

@app.route('/api/health-mall', methods=['POST'])
def create_health_mall():
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    try:
        data = request.get_json()
        clinic_id_raw = data.get('clinic_id')
        hm = HealthMall(
            clinic_id      = int(clinic_id_raw) if clinic_id_raw else None,
            region         = data.get('region'),
            district       = data.get('district'),
            name           = data.get('name'),
            specialties    = data.get('specialties'),
            address        = data.get('address'),
            phone          = data.get('phone'),
            contact_person = data.get('contact_person'),
            status         = data.get('health_mall_status', '合作中'),
            start_date     = _parse_date(data.get('health_mall_start_date')),
            note           = data.get('health_mall_note'),
        )
        db.session.add(hm)
        db.session.commit()
        return jsonify({'success': True, 'id': hm.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'儲存失敗: {str(e)}'}), 500

@app.route('/api/health-mall/<int:hm_id>', methods=['PUT'])
def update_health_mall(hm_id):
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    try:
        hm = HealthMall.query.get_or_404(hm_id)
        data = request.get_json()
        clinic_id_raw = data.get('clinic_id')
        hm.clinic_id      = int(clinic_id_raw) if clinic_id_raw else hm.clinic_id
        hm.region         = data.get('region')
        hm.district       = data.get('district')
        hm.name           = data.get('name')
        hm.specialties    = data.get('specialties')
        hm.address        = data.get('address')
        hm.phone          = data.get('phone')
        hm.contact_person = data.get('contact_person')
        hm.status         = data.get('health_mall_status', '合作中')
        hm.start_date     = _parse_date(data.get('health_mall_start_date'))
        hm.note           = data.get('health_mall_note')
        hm.updated_at     = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'更新失敗: {str(e)}'}), 500

@app.route('/api/health-mall/<int:hm_id>', methods=['DELETE'])
def delete_health_mall(hm_id):
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    hm = HealthMall.query.get_or_404(hm_id)
    db.session.delete(hm)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/health-mall/export')
def export_health_mall():
    search    = request.args.get('search', '')
    region    = request.args.get('region', '')
    specialty = request.args.get('specialty', '')
    status    = request.args.get('status', '')

    query = HealthMall.query
    if search:
        query = query.filter(
            HealthMall.name.contains(search) |
            HealthMall.contact_person.contains(search)
        )
    if region:
        query = query.filter(HealthMall.region == region)
    if specialty:
        query = query.filter(HealthMall.specialties.contains(specialty))
    if status:
        query = query.filter(HealthMall.status == status)

    items = query.all()
    if not items:
        return jsonify({'error': '沒有符合條件的資料'}), 400

    wb = Workbook()
    ws = wb.active
    ws.title = '健康醫購'

    headers = ['縣市', '區域', '診所名稱', '科別', '地址', '電話', '負責人', '合作狀態', '開始日期', '備註']
    ws.append(headers)

    header_fill = PatternFill(start_color='11998E', end_color='11998E', fill_type='solid')
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    for h in items:
        ws.append([
            h.region or '', h.district or '', h.name or '',
            h.specialties or '', h.address or '',
            h.phone or '', h.contact_person or '',
            h.status or '',
            h.start_date.strftime('%Y-%m-%d') if h.start_date else '',
            h.note or '',
        ])

    col_widths = [10, 10, 22, 18, 32, 15, 10, 10, 12, 24]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f'健康醫購_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


# ── 分析 API ─────────────────────────────────────────────────

@app.route('/api/analytics/stats')
def get_analytics_stats():
    """整合統計 API：診所 + 健康醫購"""
    clinics = Clinic.query.all()
    hm_all  = HealthMall.query.all()

    # 診所總數與縣市分布
    total = len(clinics)
    region_count = Counter(c.region for c in clinics if c.region)
    top_region = region_count.most_common(1)[0] if region_count else ('N/A', 0)

    # 科別分布
    specialty_list = []
    for c in clinics:
        if c.specialties:
            specialty_list.extend(s.strip() for s in c.specialties.split(',') if s.strip())
    specialty_count = Counter(specialty_list)

    # 合作項目分布
    col_items = {
        '藥袋':     sum(1 for c in clinics if c.col_yaodai),
        '海報/立牌': sum(1 for c in clinics if c.col_haibao),
        '派樣':     sum(1 for c in clinics if c.col_paiyang),
        '百位':     sum(1 for c in clinics if c.col_baiwei),
    }

    # 健康醫購（從獨立 table）
    hm_total  = len(hm_all)
    hm_active = sum(1 for h in hm_all if h.status == '合作中')
    hm_paused = sum(1 for h in hm_all if h.status == '暫停')
    hm_ended  = sum(1 for h in hm_all if h.status == '結束')
    hm_region_count = Counter(h.region for h in hm_all if h.region)

    return jsonify({
        'total':            total,
        'hm_total':         hm_total,
        'hm_active':        hm_active,
        'top_region':       top_region[0],
        'top_region_count': top_region[1],
        'regions':      dict(region_count),
        'specialties':  dict(specialty_count),
        'col_items':    col_items,
        'hm_status':    {'合作中': hm_active, '暫停': hm_paused, '結束': hm_ended},
        'hm_regions':   dict(hm_region_count),
    })

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
            Clinic.name.contains(search) |
            Clinic.address.contains(search) |
            Clinic.contact_person.contains(search)
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

@app.route('/api/health-mall/import', methods=['POST'])
def import_health_mall_data():
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
        result = import_health_mall(temp_path, db, HealthMall)
    os.remove(temp_path)
    return jsonify(result)


# ── 活動比對 API ─────────────────────────────────────────────

@app.route('/api/campaign/match', methods=['POST'])
def campaign_match():
    if 'file' not in request.files:
        return jsonify({'error': '沒有上傳檔案'}), 400

    file = request.files['file']
    if not file.filename.endswith('.xlsx'):
        return jsonify({'error': '只接受 .xlsx 格式'}), 400

    filename = secure_filename(file.filename)
    temp_path = os.path.join('/tmp', filename)
    file.save(temp_path)

    try:
        wb = load_workbook(temp_path)
        ws = wb.active
        os.remove(temp_path)

        header = [str(cell.value).strip() if cell.value else '' for cell in ws[1]]
        col = {name: idx for idx, name in enumerate(header)}
        REQUIRED = {'電話'}
        missing = REQUIRED - col.keys()
        if missing:
            return jsonify({'error': f'Excel 缺少必要欄位：{", ".join(missing)}'}), 400

        def _get(row, name):
            idx = col.get(name)
            if idx is None or idx >= len(row):
                return ''
            return str(row[idx]).strip() if row[idx] is not None else ''

        uploaded = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            phone_raw = _get(row, '電話')
            uploaded.append({
                'region':   _get(row, '縣市'),
                'district': _get(row, '區域'),
                'name':     _get(row, '診所名稱'),
                'phone':    phone_raw,
                'phone_n':  _normalize_phone(phone_raw),
            })

        clinics = Clinic.query.all()
        phone_to_clinic = {}
        for c in clinics:
            np = _normalize_phone(c.phone)
            if np:
                phone_to_clinic[np] = c

        uploaded_phones = {u['phone_n'] for u in uploaded if u['phone_n']}

        matched = []
        for u in uploaded:
            if u['phone_n'] and u['phone_n'] in phone_to_clinic:
                matched.append(_clinic_brief(phone_to_clinic[u['phone_n']]))

        not_joined = []
        for c in clinics:
            np = _normalize_phone(c.phone)
            if not np or np not in uploaded_phones:
                not_joined.append(_clinic_brief(c))

        not_in_system = []
        for u in uploaded:
            if not u['phone_n'] or u['phone_n'] not in phone_to_clinic:
                not_in_system.append({
                    'region':   u['region'],
                    'district': u['district'],
                    'name':     u['name'],
                    'phone':    u['phone'],
                })

        return jsonify({
            'matched':       matched,
            'not_joined':    not_joined,
            'not_in_system': not_in_system,
        })

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'error': f'比對失敗: {str(e)}'}), 500


@app.route('/api/campaign/export-not-joined')
def export_not_joined():
    ids_str  = request.args.get('ids', '')
    campaign = request.args.get('campaign', '活動')

    if not ids_str:
        return jsonify({'error': '沒有診所 ID'}), 400

    try:
        ids = [int(i) for i in ids_str.split(',') if i.strip().isdigit()]
    except ValueError:
        return jsonify({'error': '無效的 ID 格式'}), 400

    clinics = Clinic.query.filter(Clinic.id.in_(ids)).all()
    if not clinics:
        return jsonify({'error': '沒有符合條件的資料'}), 400

    wb = Workbook()
    ws = wb.active
    ws.title = '未參加診所'
    ws.append(['縣市', '區域', '診所名稱', '科別', '地址', '電話', '負責人', '備註'])
    for c in clinics:
        ws.append([
            c.region or '', c.district or '', c.name or '',
            c.specialties or '', c.address or '',
            c.phone or '', c.contact_person or '', c.note or '',
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f'{campaign}_未參加診所_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


# ── 工具函式 ─────────────────────────────────────────────────

def _normalize_phone(phone):
    return re.sub(r'\D', '', str(phone)) if phone else ''

def _clinic_brief(c):
    return {
        'id':             c.id,
        'region':         c.region or '',
        'district':       c.district or '',
        'name':           c.name or '',
        'specialties':    c.specialties or '',
        'address':        c.address or '',
        'phone':          c.phone or '',
        'contact_person': c.contact_person or '',
    }

def _parse_date(s):
    if s:
        try:
            return datetime.strptime(s, '%Y-%m-%d').date()
        except ValueError:
            return None
    return None

def _hm_json(h):
    """HealthMall 物件 → JSON dict（保持與前端相容的欄位名稱）"""
    return {
        'id':                   h.id,
        'clinic_id':            h.clinic_id,
        'region':               h.region or '',
        'district':             h.district or '',
        'name':                 h.name or '',
        'specialties':          h.specialties or '',
        'address':              h.address or '',
        'phone':                h.phone or '',
        'contact_person':       h.contact_person or '',
        'health_mall_status':   h.status or '合作中',
        'health_mall_start_date': h.start_date.strftime('%Y-%m-%d') if h.start_date else '',
        'health_mall_note':     h.note or '',
    }


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8081, debug=True)
