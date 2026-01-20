from openpyxl import load_workbook
import os

def import_clinics(file_path, db, Clinic):
    """從 Excel 匯入診所資料"""
    try:
        wb = load_workbook(file_path)
        ws = wb.active
        
        # 驗證標題列
        expected_headers = ['縣市', '區域', '診所名稱', '科別', '地址', '電話', '負責人']
        actual_headers = [cell.value for cell in ws[1]]
        
        if actual_headers[:7] != expected_headers:
            return {'success': False, 'error': '檔案格式錯誤：標題列不符合要求'}
        
        # 讀取資料
        imported_count = 0
        errors = []
        
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                # 跳過空白列
                if not any(row[:7]):
                    continue
                
                region = row[0]
                district = row[1]
                name = row[2]
                specialties = row[3]
                address = row[4]
                phone = row[5]
                contact_person = row[6]
                
                # 驗證必填欄位
                if not name:
                    errors.append(f'第{row_num}列：診所名稱為必填')
                    continue
                
                # 建立診所資料
                clinic = Clinic(
                    region=region,
                    district=district,
                    name=name,
                    specialties=specialties,
                    address=address,
                    phone=phone,
                    contact_person=contact_person,
                    media_items=''  # 匯入時預設為空，可後續編輯
                )
                
                db.session.add(clinic)
                imported_count += 1
                
            except Exception as e:
                errors.append(f'第{row_num}列：{str(e)}')
        
        # 提交到資料庫
        db.session.commit()
        
        result = {
            'success': True,
            'imported': imported_count,
            'errors': errors
        }
        
        return result
        
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}
