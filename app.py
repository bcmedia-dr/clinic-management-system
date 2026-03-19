from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, date
import os, re
from collections import Counter
from io import BytesIO
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from werkzeug.utils import secure_filename
from export import export_clinics
from import_data import import_clinics, import_health_mall
from import_custom import import_custom_clinics
from phone_utils import format_phone

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
    id               = db.Column(db.Integer, primary_key=True)
    region           = db.Column(db.String(50))
    district         = db.Column(db.String(50))
    name             = db.Column(db.String(200))
    media_items      = db.Column(db.String(500))                    # 舊欄位（保留）
    specialties      = db.Column(db.String(500))
    address          = db.Column(db.String(300))
    phone            = db.Column(db.String(50))
    phone_normalized = db.Column(db.String(50), unique=True)        # 正規化電話（僅數字），用於唯一性約束
    contact_person   = db.Column(db.String(100))
    business_hours   = db.Column(db.String(200))
    note             = db.Column(db.Text)
    col_yaodai       = db.Column(db.Boolean, default=False)
    col_haibao       = db.Column(db.Boolean, default=False)
    col_paiyang      = db.Column(db.Boolean, default=False)
    col_baiwei       = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


class Campaign(db.Model):
    __tablename__ = 'campaign'
    id                 = db.Column(db.Integer, primary_key=True)
    name               = db.Column(db.String(200), nullable=False)
    brand              = db.Column(db.String(100))
    year               = db.Column(db.Integer)
    month              = db.Column(db.Integer)
    note               = db.Column(db.Text)
    cooperation_items  = db.Column(db.String(200))  # 勾選的合作項目，逗號分隔（如 "海報,立牌,派樣"）
    cooperation_other  = db.Column(db.String(200))  # 其他合作項目，自由填寫
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)


class CampaignClinic(db.Model):
    __tablename__ = 'campaign_clinic'
    id          = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    clinic_id   = db.Column(db.Integer, db.ForeignKey('clinic.id'), nullable=False)
    joined_at   = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('campaign_id', 'clinic_id', name='uq_campaign_clinic'),)

    campaign = db.relationship('Campaign', backref=db.backref('clinic_links', lazy=True))
    clinic   = db.relationship('Clinic',   backref=db.backref('campaign_links', lazy=True))


class BaiweiDoctor(db.Model):
    __tablename__ = 'baiwei_doctor'
    id          = db.Column(db.Integer, primary_key=True)
    clinic_id   = db.Column(db.Integer, db.ForeignKey('clinic.id', ondelete='SET NULL'), nullable=True)
    clinic_name = db.Column(db.String(200))
    region      = db.Column(db.String(50))
    district    = db.Column(db.String(50))
    address     = db.Column(db.String(300))
    phone       = db.Column(db.String(50))
    doctor_name = db.Column(db.String(100))
    specialty   = db.Column(db.String(200))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    clinic = db.relationship('Clinic', backref=db.backref('baiwei_doctors', lazy=True))


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

@app.route('/campaign-history')
def campaign_history_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('campaign_history.html')

@app.route('/baiwei')
def baiwei_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('baiwei.html')

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
        phone_val = data.get('phone')
        clinic = Clinic(
            region           = data.get('region'),
            district         = data.get('district'),
            name             = data.get('name'),
            col_yaodai       = data.get('col_yaodai', False),
            col_haibao       = data.get('col_haibao', False),
            col_paiyang      = data.get('col_paiyang', False),
            col_baiwei       = data.get('col_baiwei', False),
            specialties      = data.get('specialties'),
            address          = data.get('address'),
            phone            = phone_val,
            phone_normalized = _normalize_phone(phone_val) or None,  # 同步寫入正規化電話
            contact_person   = data.get('contact_person'),
            business_hours   = data.get('business_hours'),
            note             = data.get('note')
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
        phone_val             = data.get('phone')
        clinic.region         = data.get('region')
        clinic.district       = data.get('district')
        clinic.name           = data.get('name')
        clinic.col_yaodai     = data.get('col_yaodai', False)
        clinic.col_haibao     = data.get('col_haibao', False)
        clinic.col_paiyang    = data.get('col_paiyang', False)
        clinic.col_baiwei     = data.get('col_baiwei', False)
        clinic.specialties    = data.get('specialties')
        clinic.address        = data.get('address')
        clinic.phone          = phone_val
        clinic.phone_normalized = _normalize_phone(phone_val) or None  # 同步更新正規化電話
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

    def _to_brief(c):
        return {
            'id':             c.id,
            'region':         c.region or '',
            'district':       c.district or '',
            'name':           c.name or '',
            'phone':          c.phone or '',
            'contact_person': c.contact_person or '',
            'specialties':    c.specialties or '',
            'address':        c.address or '',
        }

    if not q:
        clinics = Clinic.query.order_by(Clinic.name).limit(30).all()
        return jsonify([_to_brief(c) for c in clinics])

    q_digits = _normalize_phone(q)  # 純數字版搜尋字
    # 判斷是否像電話號碼：只含數字、空格、破折號，且至少 6 位數字
    is_phone_query = (
        bool(q_digits) and
        len(q_digits) >= 6 and
        bool(re.match(r'^[\d\s\-]+$', q))
    )

    if is_phone_query:
        # 電話搜尋：雙邊都 normalize 後做子字串比對，解決新舊格式不一致問題
        # （格式化後 DB 存 "02-2876-6955"，使用者可能搜 "0228766955"，需對齊）
        all_clinics = Clinic.query.order_by(Clinic.name).all()
        clinics = [
            c for c in all_clinics
            if (q in (c.name or '')) or
               (c.phone and q_digits in _normalize_phone(c.phone))
        ][:30]
    else:
        clinics = Clinic.query.filter(
            Clinic.name.contains(q) | Clinic.phone.contains(q)
        ).order_by(Clinic.name).limit(30).all()

    return jsonify([_to_brief(c) for c in clinics])


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

@app.route('/api/import-custom', methods=['POST'])
def import_custom_data():
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
        result = import_custom_clinics(temp_path, db, Clinic)
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


# ── 活動記錄 API ─────────────────────────────────────────────

@app.route('/api/campaigns', methods=['GET'])
def get_campaigns():
    campaigns = Campaign.query.order_by(Campaign.year.desc(), Campaign.created_at.desc()).all()
    result = []
    for c in campaigns:
        count = CampaignClinic.query.filter_by(campaign_id=c.id).count()
        result.append({
            'id':                c.id,
            'name':              c.name,
            'brand':             c.brand or '',
            'year':              c.year,
            'month':             c.month,
            'note':              c.note or '',
            'cooperation_items': c.cooperation_items or '',
            'cooperation_other': c.cooperation_other or '',
            'clinic_count':      count,
            'created_at':        c.created_at.strftime('%Y-%m-%d') if c.created_at else '',
        })
    return jsonify(result)

@app.route('/api/campaigns', methods=['POST'])
def create_campaign():
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    data              = request.get_json()
    brand             = (data.get('brand') or '').strip()
    year              = data.get('year')
    month             = data.get('month')
    note              = data.get('note') or ''
    cooperation_items = (data.get('cooperation_items') or '').strip()
    cooperation_other = (data.get('cooperation_other') or '').strip()
    name  = (data.get('name') or '').strip() or f"{brand}{year or ''}".strip()
    if not name:
        return jsonify({'error': '請輸入活動名稱或品牌'}), 400
    c = Campaign(name=name, brand=brand or None,
                 year=int(year) if year else None,
                 month=int(month) if month else None,
                 note=note or None,
                 cooperation_items=cooperation_items or None,
                 cooperation_other=cooperation_other or None)
    db.session.add(c)
    db.session.commit()
    return jsonify({'success': True, 'id': c.id, 'name': c.name})

@app.route('/api/campaigns/<int:campaign_id>', methods=['DELETE'])
def delete_campaign(campaign_id):
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    campaign = Campaign.query.get_or_404(campaign_id)
    CampaignClinic.query.filter_by(campaign_id=campaign_id).delete()
    db.session.delete(campaign)
    db.session.commit()
    return jsonify({'success': True})

# 編輯活動資訊（品牌、年份、月份、備註）
@app.route('/api/campaigns/<int:campaign_id>', methods=['PUT'])
def update_campaign(campaign_id):
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    campaign = Campaign.query.get_or_404(campaign_id)
    data              = request.get_json()
    brand             = (data.get('brand') or '').strip()
    year              = data.get('year')
    month             = data.get('month')
    note              = (data.get('note') or '').strip()
    cooperation_items = (data.get('cooperation_items') or '').strip()
    cooperation_other = (data.get('cooperation_other') or '').strip()
    # 年份和月份為必填
    if not year:
        return jsonify({'error': '年份為必填'}), 400
    if not month:
        return jsonify({'error': '月份為必填'}), 400
    campaign.brand             = brand or None
    campaign.year              = int(year)
    campaign.month             = int(month)
    campaign.note              = note or None
    campaign.cooperation_items = cooperation_items or None
    campaign.cooperation_other = cooperation_other or None
    db.session.commit()
    return jsonify({'success': True, 'id': campaign.id, 'name': campaign.name})

@app.route('/api/campaigns/<int:campaign_id>/clinics', methods=['GET'])
def get_campaign_clinics(campaign_id):
    Campaign.query.get_or_404(campaign_id)
    region    = request.args.get('region', '')
    specialty = request.args.get('specialty', '')
    links = CampaignClinic.query.filter_by(campaign_id=campaign_id).all()
    result = []
    for link in links:
        c = link.clinic
        if not c:
            continue
        if region and c.region != region:
            continue
        if specialty and (not c.specialties or specialty not in c.specialties):
            continue
        result.append({
            'id':             c.id,
            'region':         c.region or '',
            'district':       c.district or '',
            'name':           c.name or '',
            'specialties':    c.specialties or '',
            'address':        c.address or '',
            'phone':          c.phone or '',
            'contact_person': c.contact_person or '',
            'note':           c.note or '',
            'joined_at':      link.joined_at.strftime('%Y-%m-%d') if link.joined_at else '',
        })
    return jsonify(result)

@app.route('/api/campaigns/<int:campaign_id>/clinics/<int:clinic_id>', methods=['PUT'])
def update_campaign_clinic(campaign_id, clinic_id):
    """更新活動中某間診所的基本資料（直接修改 clinic table）"""
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    # 確認診所確實屬於此活動
    link = CampaignClinic.query.filter_by(campaign_id=campaign_id, clinic_id=clinic_id).first()
    if not link:
        return jsonify({'error': '此診所不在該活動中'}), 404
    clinic = Clinic.query.get_or_404(clinic_id)
    data = request.get_json() or {}
    # 只更新有傳入的欄位，避免意外清空
    if 'region'         in data: clinic.region         = data['region']
    if 'district'       in data: clinic.district       = data['district']
    if 'name'           in data: clinic.name           = data['name']
    if 'specialties'    in data: clinic.specialties    = data['specialties']
    if 'phone'          in data: clinic.phone          = data['phone']
    if 'contact_person' in data: clinic.contact_person = data['contact_person']
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/campaigns/<int:campaign_id>/import', methods=['POST'])
def import_campaign_clinics(campaign_id):
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    campaign = Campaign.query.get_or_404(campaign_id)
    if 'file' not in request.files:
        return jsonify({'error': '沒有上傳檔案'}), 400
    file = request.files['file']
    if not file.filename.endswith('.xlsx'):
        return jsonify({'error': '只接受 .xlsx 格式'}), 400

    filename  = secure_filename(file.filename)
    temp_path = os.path.join('/tmp', filename)
    file.save(temp_path)

    try:
        wb = load_workbook(temp_path)
        ws = wb.active
        os.remove(temp_path)

        # 前三行 debug 資訊
        preview_rows = []
        for r in ws.iter_rows(min_row=1, max_row=3, values_only=True):
            preview_rows.append([str(v) if v is not None else '' for v in r])

        # 自動偵測 header 行：掃描前 5 行，找到含「電話」的那行
        header_row_idx = None
        header = []
        for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=5, values_only=True), start=1):
            stripped = [str(v).strip() if v is not None else '' for v in row]
            if '電話' in stripped:
                header_row_idx = row_idx
                header = stripped
                break

        if header_row_idx is None:
            return jsonify({
                'error': '找不到含「電話」的標題行（掃描前 5 行）',
                'debug_preview': preview_rows,
            }), 400

        col = {name: idx for idx, name in enumerate(header)}

        # 支援雙名稱欄位
        def _resolve(row, *candidates):
            for field in candidates:
                idx = col.get(field)
                if idx is not None and idx < len(row) and row[idx] is not None:
                    return str(row[idx]).strip()
            return ''

        phone_to_clinic = {}
        for c in Clinic.query.all():
            np = _normalize_phone(c.phone)
            if np:
                phone_to_clinic[np] = c

        in_campaign = {cc.clinic_id for cc in
                       CampaignClinic.query.filter_by(campaign_id=campaign_id).all()}

        new_clinics_count = already_exists = recorded = already_in_campaign = 0
        errors = []
        processed_clinics = []  # 記錄本次處理過的診所，匯入後連動合作項目

        data_start_row = header_row_idx + 1
        for row_num, row in enumerate(ws.iter_rows(min_row=data_start_row, values_only=True), start=data_start_row):
            if not any(row):
                continue
            phone_raw  = _resolve(row, '電話')
            normalized = _normalize_phone(phone_raw)
            if not normalized:
                errors.append(f'第{row_num}列：缺少電話')
                continue

            if normalized in phone_to_clinic:
                clinic = phone_to_clinic[normalized]
                already_exists += 1
            else:
                raw_name = _resolve(row, '診所名稱', '院名')
                if not raw_name:
                    errors.append(f'第{row_num}列：總表無此電話且缺少診所名稱')
                    continue
                # 套用院名清理邏輯（括號/斜線內容移到備註）
                from import_custom import _parse_name
                name, extracted_note = _parse_name(raw_name)
                if not name:
                    errors.append(f'第{row_num}列：清理後診所名稱為空（原始值：{raw_name}）')
                    continue
                phone_fmt = format_phone(phone_raw, _resolve(row, '縣市') or None)
                clinic = Clinic(
                    region           = _resolve(row, '縣市') or None,
                    district         = _resolve(row, '區域') or None,
                    name             = name,
                    specialties      = _resolve(row, '科別') or None,
                    address          = _resolve(row, '地址', '院址') or None,
                    phone            = phone_fmt,
                    phone_normalized = normalized or None,  # 同步寫入正規化電話
                    contact_person   = _resolve(row, '負責人', '聯絡人') or None,
                    note             = extracted_note or None,
                )
                db.session.add(clinic)
                db.session.flush()
                phone_to_clinic[normalized] = clinic
                new_clinics_count += 1

            processed_clinics.append(clinic)
            if clinic.id in in_campaign:
                already_in_campaign += 1
                continue
            db.session.add(CampaignClinic(campaign_id=campaign_id, clinic_id=clinic.id))
            in_campaign.add(clinic.id)
            recorded += 1

        # 根據活動的合作項目，連動更新所有處理過的診所欄位（只設 True，不取消）
        coop_items = campaign.cooperation_items or ''
        if coop_items and processed_clinics:
            for c in processed_clinics:
                if '藥袋' in coop_items:
                    c.col_yaodai = True
                if '海報' in coop_items or '立牌' in coop_items:
                    c.col_haibao = True
                if '派樣' in coop_items:
                    c.col_paiyang = True
                if '百位' in coop_items:
                    c.col_baiwei = True

        db.session.commit()
        return jsonify({
            'success':             True,
            'new_clinics':         new_clinics_count,
            'already_exists':      already_exists,
            'recorded':            recorded,
            'already_in_campaign': already_in_campaign,
            'errors':              errors,
            'debug_header_row':    header_row_idx,
            'debug_columns':       header,
            'debug_preview':       preview_rows,
        })

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        db.session.rollback()
        return jsonify({'error': f'匯入失敗: {str(e)}'}), 500

@app.route('/api/campaigns/<int:campaign_id>/export', methods=['GET'])
def export_campaign_clinics(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    links    = CampaignClinic.query.filter_by(campaign_id=campaign_id).all()

    wb = Workbook()
    ws = wb.active
    ws.title = campaign.name[:28]
    headers  = ['縣市', '區域', '診所名稱', '科別', '地址', '電話', '聯絡人', '備註']
    ws.append(headers)
    fill = PatternFill(start_color='E96C2C', end_color='E96C2C', fill_type='solid')
    for i in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=i)
        cell.font      = Font(bold=True, color='FFFFFF')
        cell.fill      = fill
        cell.alignment = Alignment(horizontal='center')
    for link in links:
        c = link.clinic
        if not c:
            continue
        ws.append([c.region or '', c.district or '', c.name or '',
                   c.specialties or '', c.address or '',
                   c.phone or '', c.contact_person or '', c.note or ''])
    for i, w in enumerate([10, 10, 22, 18, 32, 15, 10, 24], 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'{campaign.name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)

@app.route('/api/clinics/<int:clinic_id>/campaigns', methods=['GET'])
def get_clinic_campaigns(clinic_id):
    links = CampaignClinic.query.filter_by(clinic_id=clinic_id).all()
    result = []
    for link in links:
        c = link.campaign
        result.append({
            'campaign_id':   c.id,
            'campaign_name': c.name,
            'brand':         c.brand or '',
            'year':          c.year,
            'joined_at':     link.joined_at.strftime('%Y-%m-%d') if link.joined_at else '',
        })
    return jsonify(result)


# ── 百位醫師 API ──────────────────────────────────────────────

@app.route('/api/baiwei', methods=['GET'])
def get_baiwei():
    specialty = request.args.get('specialty', '')
    query = BaiweiDoctor.query
    if specialty:
        # 用 LIKE 比對，支援「家醫科/外科」這類複合科別欄位
        query = query.filter(BaiweiDoctor.specialty.like(f'%{specialty}%'))
    items = query.order_by(BaiweiDoctor.region, BaiweiDoctor.district, BaiweiDoctor.clinic_name).all()
    return jsonify([{
        'id':          i.id,
        'clinic_id':   i.clinic_id,
        'clinic_name': i.clinic_name or '',
        'region':      i.region or '',
        'district':    i.district or '',
        'address':     i.address or '',
        'phone':       i.phone or '',
        'doctor_name': i.doctor_name or '',
        'specialty':   i.specialty or '',
    } for i in items])


@app.route('/api/baiwei/stats', methods=['GET'])
def get_baiwei_stats():
    total = BaiweiDoctor.query.count()
    return jsonify({'total': total})


@app.route('/api/baiwei/specialties', methods=['GET'])
def get_baiwei_specialties():
    """
    從 baiwei_doctor 的 specialty 欄位動態產生科別選單。
    以斜線拆分複合科別（如「家醫科/外科」→「家醫科」、「外科」），
    去重後排序，並排除指定科別。
    """
    EXCLUDE = {'泌尿科', '牙科', '產後護理之家', '醫美'}
    rows = db.session.query(BaiweiDoctor.specialty).filter(BaiweiDoctor.specialty.isnot(None)).all()
    seen = set()
    for (val,) in rows:
        # 同時支援斜線、頓號、逗號三種分隔符號
        for part in re.split(r'[/、,]', val):
            part = part.strip()
            if part and part not in EXCLUDE:
                seen.add(part)
    return jsonify(sorted(seen))


@app.route('/api/baiwei/import', methods=['POST'])
def import_baiwei():
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    if 'file' not in request.files:
        return jsonify({'error': '沒有上傳檔案'}), 400
    file = request.files['file']
    if not file.filename.endswith('.xlsx'):
        return jsonify({'error': '只接受 .xlsx 格式'}), 400

    filename  = secure_filename(file.filename)
    temp_path = os.path.join('/tmp', filename)
    file.save(temp_path)

    try:
        wb = load_workbook(temp_path)
        ws = wb.active
        os.remove(temp_path)

        # 偵測 header 行（找含「電話」的那行）
        header_row_idx = None
        header = []
        for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=5, values_only=True), start=1):
            stripped = [str(v).strip() if v is not None else '' for v in row]
            if '電話' in stripped:
                header_row_idx = row_idx
                header = stripped
                break
        if header_row_idx is None:
            return jsonify({'error': '找不到含「電話」的標題行（掃描前 5 行）'}), 400

        col = {name: idx for idx, name in enumerate(header)}

        def _get(row, *keys):
            for k in keys:
                idx = col.get(k)
                if idx is not None and idx < len(row) and row[idx] is not None:
                    return str(row[idx]).strip()
            return ''

        # 建立電話 → clinic 的快查表
        phone_to_clinic = {}
        for c in Clinic.query.all():
            np = _normalize_phone(c.phone)
            if np:
                phone_to_clinic[np] = c

        # 建立已存在的百位醫師組合（phone + doctor_name）防重複匯入
        existing_keys = {
            (_normalize_phone(d.phone), (d.doctor_name or '').strip())
            for d in BaiweiDoctor.query.all()
        }

        new_count = already_count = 0
        errors = []

        for row_num, row in enumerate(ws.iter_rows(min_row=header_row_idx + 1, values_only=True), start=header_row_idx + 1):
            if not any(row):
                continue

            phone_raw   = _get(row, '電話')
            doctor_name = _get(row, '醫師', '醫師名字')
            normalized  = _normalize_phone(phone_raw)

            if not normalized:
                errors.append(f'第{row_num}列：缺少電話')
                continue
            if not doctor_name:
                errors.append(f'第{row_num}列：缺少醫師名字')
                continue

            # 重複檢查
            if (normalized, doctor_name) in existing_keys:
                already_count += 1
                continue

            # 比對或新增診所
            clinic = phone_to_clinic.get(normalized)
            if clinic is None:
                raw_name = _get(row, '診所名稱', '院名')
                if not raw_name:
                    errors.append(f'第{row_num}列：總表無此電話且缺少診所名稱')
                    continue
                from import_custom import _parse_name
                name, extracted_note = _parse_name(raw_name)
                if not name:
                    errors.append(f'第{row_num}列：診所名稱清理後為空（原始：{raw_name}）')
                    continue
                clinic = Clinic(
                    region           = _get(row, '縣市') or None,
                    district         = _get(row, '區域') or None,
                    name             = name,
                    address          = _get(row, '地址') or None,
                    phone            = format_phone(phone_raw, _get(row, '縣市') or None),
                    phone_normalized = normalized or None,  # 同步寫入正規化電話
                    note             = extracted_note or None,
                )
                db.session.add(clinic)
                db.session.flush()
                phone_to_clinic[normalized] = clinic

            # 設定 col_baiwei
            clinic.col_baiwei = True

            doc = BaiweiDoctor(
                clinic_id   =clinic.id,
                clinic_name =_get(row, '診所名稱', '院名') or clinic.name,
                region      =_get(row, '縣市') or clinic.region,
                district    =_get(row, '區域') or clinic.district,
                address     =_get(row, '地址') or clinic.address,
                phone       =format_phone(phone_raw, _get(row, '縣市') or clinic.region or None),
                doctor_name =doctor_name,
                specialty   =_get(row, '科別') or None,
            )
            db.session.add(doc)
            existing_keys.add((normalized, doctor_name))
            new_count += 1

        db.session.commit()
        return jsonify({'success': True, 'new': new_count, 'already_exists': already_count, 'errors': errors})

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        db.session.rollback()
        return jsonify({'error': f'匯入失敗: {str(e)}'}), 500


@app.route('/api/baiwei/<int:doc_id>', methods=['DELETE'])
def delete_baiwei(doc_id):
    if session.get('role') != 'admin':
        return jsonify({'error': '權限不足'}), 403
    doc = BaiweiDoctor.query.get_or_404(doc_id)
    clinic_id = doc.clinic_id
    db.session.delete(doc)
    db.session.flush()
    # 若該診所已無其他百位醫師記錄，將 col_baiwei 設回 False
    if clinic_id:
        remaining = BaiweiDoctor.query.filter_by(clinic_id=clinic_id).count()
        if remaining == 0:
            clinic = Clinic.query.get(clinic_id)
            if clinic:
                clinic.col_baiwei = False
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/baiwei/export', methods=['GET'])
def export_baiwei():
    specialty = request.args.get('specialty', '')
    query = BaiweiDoctor.query
    if specialty:
        # 與列表 API 一致，用 LIKE 比對複合科別欄位（如「家醫科/外科」）
        query = query.filter(BaiweiDoctor.specialty.like(f'%{specialty}%'))
    items = query.order_by(BaiweiDoctor.region, BaiweiDoctor.district, BaiweiDoctor.clinic_name).all()

    wb = Workbook()
    ws = wb.active
    ws.title = '百位醫師'
    headers = ['縣市', '區域', '診所名稱', '醫師名字', '科別', '電話']
    ws.append(headers)

    fill = PatternFill(start_color='667EEA', end_color='667EEA', fill_type='solid')
    for i in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=i)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = fill
        cell.alignment = Alignment(horizontal='center')

    for d in items:
        ws.append([d.region or '', d.district or '', d.clinic_name or '',
                   d.doctor_name or '', d.specialty or '', d.phone or ''])

    for i, w in enumerate([10, 10, 24, 14, 16, 14], 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'百位醫師_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)


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


with app.app_context():
    db.create_all()
    # 逐一補上歷次新增的欄位，IF NOT EXISTS 確保重複執行也安全
    _migrations = [
        'ALTER TABLE campaign ADD COLUMN IF NOT EXISTS month INTEGER',
        'ALTER TABLE campaign ADD COLUMN IF NOT EXISTS cooperation_items VARCHAR(200)',
        'ALTER TABLE campaign ADD COLUMN IF NOT EXISTS cooperation_other VARCHAR(200)',
        # 新增正規化電話欄位（移除非數字後的電話），用於唯一性約束
        'ALTER TABLE clinic ADD COLUMN IF NOT EXISTS phone_normalized VARCHAR(50)',
        # 填入現有診所的正規化電話
        "UPDATE clinic SET phone_normalized = regexp_replace(phone, '[^0-9]', '', 'g') WHERE phone IS NOT NULL AND phone_normalized IS NULL",
        # 建立唯一索引（排除空值，避免無電話的診所互相衝突）
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_clinic_phone_normalized ON clinic(phone_normalized) WHERE phone_normalized IS NOT NULL AND phone_normalized <> ''",
        """CREATE TABLE IF NOT EXISTS baiwei_doctor (
            id SERIAL PRIMARY KEY,
            clinic_id INTEGER REFERENCES clinic(id) ON DELETE SET NULL,
            clinic_name VARCHAR(200),
            region VARCHAR(50),
            district VARCHAR(50),
            address VARCHAR(300),
            phone VARCHAR(50),
            doctor_name VARCHAR(100),
            specialty VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    ]
    for _sql in _migrations:
        try:
            with db.engine.connect() as _conn:
                _conn.execute(text(_sql))
                _conn.commit()
        except Exception:
            pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=True)
