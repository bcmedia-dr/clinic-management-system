"""
資料庫遷移腳本：添加 business_hours 和 note 欄位
如果資料庫已存在，需要手動添加這些欄位
"""
from app import app, db
import sqlite3
import os

def migrate_database():
    """遷移資料庫，添加新欄位"""
    with app.app_context():
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        
        # 如果是 SQLite 資料庫
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            
            # 檢查多個可能的路徑
            possible_paths = [
                db_path,
                os.path.join('instance', 'clinics.db'),
                'clinics.db'
            ]
            
            db_file = None
            for path in possible_paths:
                if os.path.exists(path):
                    db_file = path
                    break
            
            if db_file:
                try:
                    print(f"找到資料庫檔案: {db_file}")
                    conn = sqlite3.connect(db_file)
                    cursor = conn.cursor()
                    
                    # 檢查欄位是否存在
                    cursor.execute("PRAGMA table_info(clinic)")
                    columns = [column[1] for column in cursor.fetchall()]
                    print(f"現有欄位: {columns}")
                    
                    # 需要添加的欄位
                    fields_to_add = [
                        ('health_mall', 'VARCHAR(10) DEFAULT "否"'),
                        ('hundred_position', 'VARCHAR(10) DEFAULT "否"'),
                        ('business_hours', 'VARCHAR(200)'),
                        ('note', 'TEXT')
                    ]
                    
                    for field_name, field_type in fields_to_add:
                        if field_name not in columns:
                            try:
                                cursor.execute(f"ALTER TABLE clinic ADD COLUMN {field_name} {field_type}")
                                print(f"✓ 已添加 {field_name} 欄位")
                            except sqlite3.OperationalError as e:
                                print(f"✗ 添加 {field_name} 欄位時發生錯誤: {e}")
                        else:
                            print(f"- {field_name} 欄位已存在")
                    
                    conn.commit()
                    conn.close()
                    print("\n資料庫遷移完成！")
                except Exception as e:
                    print(f"遷移資料庫時發生錯誤: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                # 如果資料庫不存在，直接建立新表
                print("資料庫檔案不存在，建立新表...")
                db.create_all()
                print("已建立新的資料庫表")
        else:
            # PostgreSQL 資料庫需要手動執行 SQL
            print("檢測到 PostgreSQL 資料庫")
            print("請手動執行以下 SQL 語句：")
            print("ALTER TABLE clinic ADD COLUMN IF NOT EXISTS health_mall VARCHAR(10) DEFAULT '否';")
            print("ALTER TABLE clinic ADD COLUMN IF NOT EXISTS hundred_position VARCHAR(10) DEFAULT '否';")
            print("ALTER TABLE clinic ADD COLUMN IF NOT EXISTS business_hours VARCHAR(200);")
            print("ALTER TABLE clinic ADD COLUMN IF NOT EXISTS note TEXT;")

if __name__ == '__main__':
    migrate_database()
