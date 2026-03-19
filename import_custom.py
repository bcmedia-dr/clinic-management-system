from openpyxl import load_workbook
import re
from phone_utils import format_phone
from sqlalchemy.exc import IntegrityError


def _normalize_phone(phone):
    """移除所有非數字字元，用於重複比對"""
    return re.sub(r'\D', '', str(phone)) if phone else ''


def _parse_name(raw_name):
    """
    清理院名，提取備註內容。
    - 全形/半形括號內文字 → note
    - 斜線後文字 → note（與括號備註以「 / 」合併）
    返回 (name, note)
    """
    if not raw_name:
        return '', ''

    raw_name = str(raw_name).strip()
    notes = []

    # 提取括號內容（支援全形 （）和半形 ()）
    bracket_pattern = re.compile(r'[（(]([^）)]*)[）)]')
    for m in bracket_pattern.findall(raw_name):
        if m.strip():
            notes.append(m.strip())
    name = bracket_pattern.sub('', raw_name).strip()

    # 提取斜線後文字
    if '/' in name:
        parts = name.split('/', 1)
        name = parts[0].strip()
        slash_part = parts[1].strip()
        if slash_part:
            notes.append(slash_part)

    note = ' / '.join(notes)
    return name.strip(), note


def import_custom_clinics(file_path, db, Clinic):
    """
    匯入自訂格式 Excel（欄位名稱：縣市、區域、院名、科別、院址、電話、聯絡人、院長）。
    院名自動清理括號/斜線內容為備註。
    以電話號碼檢查重複，重複者跳過。
    """
    try:
        wb = load_workbook(file_path)
        ws = wb.active

        header_row = [str(cell.value).strip() if cell.value else '' for cell in ws[1]]
        col = {name: idx for idx, name in enumerate(header_row)}

        if '院名' not in col:
            return {'success': False, 'error': 'Excel 缺少必要欄位：院名'}

        def _get(row, field):
            idx = col.get(field)
            if idx is None or idx >= len(row):
                return ''
            v = row[idx]
            return str(v).strip() if v is not None else ''

        # 建立現有電話集合（正規化）
        existing_phones = set()
        for (phone,) in Clinic.query.with_entities(Clinic.phone).all():
            np = _normalize_phone(phone)
            if np:
                existing_phones.add(np)

        imported_count = 0
        skipped_count  = 0
        error_count    = 0
        skipped_names  = []
        error_details  = []

        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                if not any(row):
                    continue

                raw_name = _get(row, '院名')
                if not raw_name:
                    error_count += 1
                    error_details.append(f'第{row_num}列：院名為必填')
                    continue

                name, extracted_note = _parse_name(raw_name)
                if not name:
                    error_count += 1
                    error_details.append(f'第{row_num}列：清理後院名為空（原始值：{raw_name}）')
                    continue

                phone_raw  = _get(row, '電話')
                normalized = _normalize_phone(phone_raw)
                phone_fmt  = format_phone(phone_raw, _get(row, '縣市') or None)

                if normalized and normalized in existing_phones:
                    skipped_count += 1
                    skipped_names.append(name)
                    continue

                clinic = Clinic(
                    region           = _get(row, '縣市') or None,
                    district         = _get(row, '區域') or None,
                    name             = name,
                    specialties      = _get(row, '科別') or None,
                    address          = _get(row, '院址') or None,
                    phone            = phone_fmt or None,
                    phone_normalized = normalized or None,  # 同步寫入正規化電話
                    contact_person   = _get(row, '聯絡人') or None,
                    note             = extracted_note or None,
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
                    skipped_names.append(name)

            except Exception as e:
                error_count += 1
                error_details.append(f'第{row_num}列：{str(e)}')

        db.session.commit()

        return {
            'success':       True,
            'imported':      imported_count,
            'skipped':       skipped_count,
            'errors':        error_count,
            'skipped_names': skipped_names,
            'error_details': error_details,
        }

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}
