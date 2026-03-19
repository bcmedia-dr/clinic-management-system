from openpyxl import load_workbook
from datetime import datetime
import re
from phone_utils import format_phone
from sqlalchemy.exc import IntegrityError


def _normalize_phone(phone):
    return re.sub(r'\D', '', str(phone)) if phone else ''


def import_clinics(file_path, db, Clinic):
    """從 Excel 匯入診所資料，以電話號碼檢查重複"""
    try:
        wb = load_workbook(file_path)
        ws = wb.active

        expected_headers = ['縣市', '區域', '診所名稱', '科別', '地址', '電話', '負責人']
        actual_headers = [cell.value for cell in ws[1]]

        if actual_headers[:7] != expected_headers:
            return {'success': False, 'error': '檔案格式錯誤：標題列不符合要求'}

        # 建立現有電話號碼集合
        existing_phones = set()
        for (phone,) in Clinic.query.with_entities(Clinic.phone).all():
            np = _normalize_phone(phone)
            if np:
                existing_phones.add(np)

        imported_count = 0
        skipped_count = 0
        skipped_names = []
        errors = []

        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                if not any(row[:7]):
                    continue

                region         = row[0]
                district       = row[1]
                name           = row[2]
                specialties    = row[3]
                address        = row[4]
                phone          = row[5]
                contact_person = row[6]

                if not name:
                    errors.append(f'第{row_num}列：診所名稱為必填')
                    continue

                phone_str  = str(phone) if phone else ''
                normalized = _normalize_phone(phone_str)
                region_str = str(region).strip() if region else None
                phone_fmt  = format_phone(phone_str, region_str)

                if normalized and normalized in existing_phones:
                    skipped_count += 1
                    skipped_names.append(str(name))
                    continue

                clinic = Clinic(
                    region           = region,
                    district         = district,
                    name             = name,
                    specialties      = specialties,
                    address          = address,
                    phone            = phone_fmt,
                    phone_normalized = normalized or None,  # 同步寫入正規化電話
                    contact_person   = contact_person,
                )
                try:
                    # 用 savepoint 隔離每筆 INSERT，UniqueViolation 只回滾該筆
                    sp = db.session.begin_nested()
                    db.session.add(clinic)
                    db.session.flush()
                    if normalized:
                        existing_phones.add(normalized)
                    imported_count += 1
                except IntegrityError:
                    sp.rollback()  # 回滾到 savepoint，其餘已成功筆數不受影響
                    skipped_count += 1
                    skipped_names.append(str(name))

            except Exception as e:
                errors.append(f'第{row_num}列：{str(e)}')

        db.session.commit()

        return {
            'success':       True,
            'imported':      imported_count,
            'skipped':       skipped_count,
            'skipped_names': skipped_names,
            'errors':        errors,
        }

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def import_health_mall(file_path, db, HealthMall):
    """從 Excel 匯入健康醫購資料，以電話號碼檢查重複"""
    try:
        wb = load_workbook(file_path)
        ws = wb.active

        expected_headers = ['縣市', '區域', '診所名稱', '科別', '地址', '電話', '負責人']
        actual_headers = [cell.value for cell in ws[1]]

        if actual_headers[:7] != expected_headers:
            return {'success': False, 'error': '檔案格式錯誤：標題列不符合要求'}

        header = [str(c.value).strip() if c.value else '' for c in ws[1]]
        col = {name: idx for idx, name in enumerate(header)}

        # 建立現有電話號碼集合
        existing_phones = set()
        for (phone,) in HealthMall.query.with_entities(HealthMall.phone).all():
            np = _normalize_phone(phone)
            if np:
                existing_phones.add(np)

        imported_count = 0
        skipped_count  = 0
        skipped_names  = []
        errors         = []

        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                if not any(row[:7]):
                    continue

                def _get(field):
                    idx = col.get(field)
                    if idx is None or idx >= len(row):
                        return ''
                    return str(row[idx]).strip() if row[idx] is not None else ''

                name = _get('診所名稱')
                if not name:
                    errors.append(f'第{row_num}列：診所名稱為必填')
                    continue

                phone_str  = _get('電話')
                normalized = _normalize_phone(phone_str)
                phone_fmt  = format_phone(phone_str, _get('縣市') or None)

                if normalized and normalized in existing_phones:
                    skipped_count += 1
                    skipped_names.append(name)
                    continue

                start_date = None
                start_date_str = _get('開始日期')
                if start_date_str:
                    try:
                        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        pass

                status = _get('合作狀態') or '合作中'

                hm = HealthMall(
                    region         = _get('縣市'),
                    district       = _get('區域'),
                    name           = name,
                    specialties    = _get('科別'),
                    address        = _get('地址'),
                    phone          = phone_fmt,
                    contact_person = _get('負責人'),
                    status         = status,
                    start_date     = start_date,
                    note           = _get('備註'),
                )
                db.session.add(hm)
                if normalized:
                    existing_phones.add(normalized)
                imported_count += 1

            except Exception as e:
                errors.append(f'第{row_num}列：{str(e)}')

        db.session.commit()

        return {
            'success':       True,
            'imported':      imported_count,
            'skipped':       skipped_count,
            'skipped_names': skipped_names,
            'errors':        errors,
        }

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}
