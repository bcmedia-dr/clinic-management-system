from app import app, db, Clinic
import os

def init_database():
    """初始化資料庫並新增範例診所資料"""
    with app.app_context():
        try:
            # 檢查是否已經有資料
            existing_count = Clinic.query.count()
            
            if existing_count > 0:
                print(f"⚠️  資料庫已有 {existing_count} 筆資料")
                print(f"⚠️  為了安全，不會重新初始化")
                return
            
            # 建立表格（如果不存在）
            db.create_all()
            print("✅ 資料表已建立")
            
            # 新增範例資料
            sample_clinics = [
                {
                    'region': '台北市',
                    'district': '大安區',
                    'name': '安心小兒科診所',
                    'specialties': '小兒科',
                    'address': '台北市大安區信義路三段123號',
                    'phone': '02-2345-6789',
                    'contact_person': '王醫師'
                },
                {
                    'region': '新北市',
                    'district': '板橋區',
                    'name': '健康家醫科診所',
                    'specialties': '家醫科,內科',
                    'address': '新北市板橋區中山路一段456號',
                    'phone': '02-8951-2345',
                    'contact_person': '李醫師'
                },
                {
                    'region': '台中市',
                    'district': '西屯區',
                    'name': '康福小兒科診所',
                    'specialties': '小兒科,皮膚科',
                    'address': '台中市西屯區台灣大道二段789號',
                    'phone': '04-2358-7890',
                    'contact_person': '張醫師'
                },
                {
                    'region': '台北市',
                    'district': '中正區',
                    'name': '仁愛耳鼻喉科診所',
                    'specialties': '耳鼻喉科',
                    'address': '台北市中正區羅斯福路二段321號',
                    'phone': '02-2367-1234',
                    'contact_person': '陳醫師'
                },
                {
                    'region': '高雄市',
                    'district': '前鎮區',
                    'name': '博愛婦產科診所',
                    'specialties': '婦產科',
                    'address': '高雄市前鎮區中華五路567號',
                    'phone': '07-8123-4567',
                    'contact_person': '林醫師'
                },
                {
                    'region': '桃園市',
                    'district': '中壢區',
                    'name': '欣安皮膚科診所',
                    'specialties': '皮膚科',
                    'address': '桃園市中壢區中央路東段888號',
                    'phone': '03-4567-890',
                    'contact_person': '劉醫師'
                },
                {
                    'region': '台南市',
                    'district': '東區',
                    'name': '成功泌尿科診所',
                    'specialties': '泌尿科',
                    'address': '台南市東區勝利路123號',
                    'phone': '06-2345-678',
                    'contact_person': '黃醫師'
                },
                {
                    'region': '新竹市',
                    'district': '北區',
                    'name': '康寧中醫診所',
                    'specialties': '中醫',
                    'address': '新竹市北區光復路二段456號',
                    'phone': '03-5234-567',
                    'contact_person': '吳中醫師'
                }
            ]
            
            for clinic_data in sample_clinics:
                clinic = Clinic(**clinic_data)
                db.session.add(clinic)
            
            db.session.commit()
            print(f"✅ 成功新增 {len(sample_clinics)} 筆範例診所資料")
            print(f"📊 目前資料庫共有 {Clinic.query.count()} 筆資料")
            
        except Exception as e:
            print(f"❌ 資料庫初始化錯誤: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    init_database()
    print("🎉 資料庫初始化程序完成！")
