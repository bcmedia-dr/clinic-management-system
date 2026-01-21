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
    health_mall = db.Column(db.String(10), default='否')  # 健康醫購
    hundred_position = db.Column(db.String(10), default='否')  # 百位
    media_items = db.Column(db.String(500))  # 媒體項目
    specialties = db.Column(db.String(500))  # 科別
    address = db.Column(db.String(300))  # 地址
    phone = db.Column(db.String(50))  # 電話
    contact_person = db.Column(db.String(100))  # 負責人
    business_hours = db.Column(db.String(200))  # 營業時間
    note = db.Column(db.Text)  # 備註
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 自動建立表格
@app.before_first_request
def create_tables():
    db.create_all()

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
        'health_mall': c.health_mall or '否',
        'hundred_position': c.hundred_position or '否',
        'media_items': c.media_items,
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
            health_mall=data.get('health_mall', '否'),
            hundred_position=data.get('hundred_position', '否'),
            media_items=data.get('media_items'),
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
        clinic.health_mall = data.get('health_mall', '否')
        clinic.hundred_position = data.get('hundred_position', '否')
        clinic.media_items = data.get('media_items')
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

@app.route('/init-database-secret-2026')
def init_database_web():
    """透過網址初始化資料庫（僅限首次使用）"""
    try:
        # 檢查是否已有資料
        existing_count = Clinic.query.count()
        
        if existing_count > 0:
            return f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>資料庫狀態</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; }}
                        .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        h2 {{ color: #ff9800; }}
                        .info {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                        .btn {{ display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2>⚠️ 資料庫已經有資料</h2>
                        <div class="info">
                            <p><strong>目前診所數量：{existing_count} 筆</strong></p>
                            <p>為了保護您的資料，系統不會重新初始化</p>
                            <p>所有資料都已安全保存 ✅</p>
                        </div>
                        <a href="/" class="btn">前往登入頁面</a>
                    </div>
                </body>
                </html>
            '''
        
        # 建立表格
        db.create_all()
        
        # 新增範例資料
        sample_clinics = [
            {{
                'region': '台北市',
                'district': '大安區',
                'name': '安心小兒科診所',
                'media_items': '藥袋,海報,櫃檯',
                'specialties': '小兒科',
                'address': '台北市大安區信義路三段123號',
                'phone': '02-2345-6789',
                'contact_person': '王醫師'
            }},
            {{
                'region': '新北市',
                'district': '板橋區',
                'name': '健康家醫科診所',
                'media_items': '全部',
                'specialties': '家醫科,內科',
                'address': '新北市板橋區中山路一段456號',
                'phone': '02-8951-2345',
                'contact_person': '李醫師'
            }},
            {{
                'region': '台中市',
                'district': '西屯區',
                'name': '康福小兒科診所',
                'media_items': '藥袋,派樣',
                'specialties': '小兒科,皮膚科',
                'address': '台中市西屯區台灣大道二段789號',
                'phone': '04-2358-7890',
                'contact_person': '張醫師'
            }},
            {{
                'region': '台北市',
                'district': '中正區',
                'name': '仁愛耳鼻喉科診所',
                'media_items': '海報,櫃檯',
                'specialties': '耳鼻喉科',
                'address': '台北市中正區羅斯福路二段321號',
                'phone': '02-2367-1234',
                'contact_person': '陳醫師'
            }},
            {{
                'region': '高雄市',
                'district': '前鎮區',
                'name': '博愛婦產科診所',
                'media_items': '全部',
                'specialties': '婦產科',
                'address': '高雄市前鎮區中華五路567號',
                'phone': '07-8123-4567',
                'contact_person': '林醫師'
            }},
            {{
                'region': '桃園市',
                'district': '中壢區',
                'name': '欣安皮膚科診所',
                'media_items': '藥袋,海報',
                'specialties': '皮膚科',
                'address': '桃園市中壢區中央路東段888號',
                'phone': '03-4567-890',
                'contact_person': '劉醫師'
            }},
            {{
                'region': '台南市',
                'district': '東區',
                'name': '成功泌尿科診所',
                'media_items': '櫃檯,派樣',
                'specialties': '泌尿科',
                'address': '台南市東區勝利路123號',
                'phone': '06-2345-678',
                'contact_person': '黃醫師'
            }},
            {{
                'region': '新竹市',
                'district': '北區',
                'name': '康寧中醫診所',
                'media_items': '藥袋,海報,櫃檯,派樣',
                'specialties': '中醫',
                'address': '新竹市北區光復路二段456號',
                'phone': '03-5234-567',
                'contact_person': '吳中醫師'
            }}
        ]
        
        for clinic_data in sample_clinics:
            clinic = Clinic(**clinic_data)
            db.session.add(clinic)
        
        db.session.commit()
        final_count = Clinic.query.count()
        
        return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>初始化成功</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    h2 {{ color: #4caf50; }}
                    .success {{ background: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #4caf50; }}
                    .warning {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ff9800; }}
                    .btn {{ display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
                    strong {{ color: #667eea; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>✅ 初始化成功！</h2>
                    <div class="success">
                        <p>成功新增 <strong>{len(sample_clinics)}</strong> 筆範例診所資料</p>
                        <p>目前資料庫共有 <strong>{final_count}</strong> 筆資料</p>
                    </div>
                    <div class="warning">
                        <p><strong>⚠️ 重要提醒：</strong></p>
                        <p>請立即刪除此初始化路由以確保系統安全！</p>
                        <p>詳細步驟請參考部署文件</p>
                    </div>
                    <a href="/" class="btn">前往登入頁面</a>
                </div>
            </body>
            </html>
        '''
        
    except Exception as e:
        db.session.rollback()
        return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>初始化失敗</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    h2 {{ color: #f44336; }}
                    .error {{ background: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #f44336; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>❌ 初始化失敗</h2>
                    <div class="error">
                        <p><strong>錯誤訊息：</strong></p>
                        <p>{str(e)}</p>
                    </div>
                    <p>請聯絡系統管理員或查看日誌</p>
                </div>
            </body>
            </html>
        '''

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8081, debug=True)
