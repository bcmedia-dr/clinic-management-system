"""
遷移腳本：將 clinic 表中的舊健康醫購欄位資料，遷移到新的 health_mall table。

執行時機：完成 app.py 重構後，在 Render 或本地執行一次即可。
執行方式：python migrate_health_mall.py
"""

from app import app, db, HealthMall
from sqlalchemy import text


def migrate():
    with app.app_context():
        # 建立新 table（若不存在）
        db.create_all()

        # 從舊欄位讀取健康醫購診所（直接用 raw SQL，避免 Clinic model 已移除這些欄位）
        try:
            result = db.session.execute(text(
                "SELECT id, region, district, name, phone, contact_person, "
                "specialties, address, health_mall_status, health_mall_start_date, health_mall_note "
                "FROM clinic WHERE health_mall_status IN ('合作中', '暫停', '結束')"
            ))
            rows = result.fetchall()
        except Exception as e:
            print(f'[錯誤] 查詢舊資料失敗（可能舊欄位已不存在）: {e}')
            print('若已完整遷移過，此為正常狀況，無需再次執行。')
            return

        if not rows:
            print('沒有舊的健康醫購資料需要遷移。')
            return

        count = 0
        skip  = 0
        for row in rows:
            # 避免重複遷移（以診所名稱 + 電話判斷）
            existing = HealthMall.query.filter_by(
                name=row.name,
                phone=row.phone
            ).first()
            if existing:
                print(f'  略過（已存在）：{row.name} / {row.phone}')
                skip += 1
                continue

            hm = HealthMall(
                clinic_id      = row.id,
                region         = row.region,
                district       = row.district,
                name           = row.name,
                phone          = row.phone,
                contact_person = row.contact_person,
                specialties    = row.specialties,
                address        = row.address,
                status         = row.health_mall_status,
                start_date     = row.health_mall_start_date,
                note           = row.health_mall_note,
            )
            db.session.add(hm)
            count += 1

        db.session.commit()
        print(f'遷移完成：新增 {count} 筆，略過 {skip} 筆。')


if __name__ == '__main__':
    migrate()
