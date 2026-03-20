"""
phone_utils.py — 台灣電話號碼格式化工具 + 科別標準化工具
供 app.py、import_data.py、import_custom.py 共用，避免循環 import
"""
import re


# ── 科別標準化 ────────────────────────────────────────────────

# 標準科別白名單（所有科別最終都必須是其中之一）
STANDARD_SPECIALTIES = [
    '小兒科', '家醫科', '耳鼻喉科', '內科', '外科', '皮膚科',
    '婦產科', '復健/骨科', '中醫', '內兒科', '神經科', '精神科',
    '身心科', '泌尿科', '牙科', '眼科', '產後護理之家', '其他',
]

# 非標準科別 → 標準科別的對應表
SPECIALTY_MAPPING = {
    '腸胃科':    '內科',
    '肝膽腸胃科': '內科',
    '腸胃肝膽科': '內科',
    '消化內科':  '內科',
    '家庭醫學科': '家醫科',
    '家庭醫學':  '家醫科',
    '家醫':     '家醫科',
    '腸胃專科':  '內科',
    '一般外科':  '外科',
    '整形外科':  '外科',
    '小兒外科':  '小兒科/外科',   # 對應後為複合科別，會再次拆開處理
    '骨科':     '復健/骨科',
    '復健':     '復健/骨科',   # '復健/骨科' 被切開後 '復健' 也能對應回來
    '復健科':   '復健/骨科',
    '骨科復健':  '復健/骨科',
}


def normalize_specialty(raw: str) -> str:
    """
    將原始科別字串標準化：
    1. 用 /、、，, 拆開（支援全形/半形逗號、頓號、斜線）
    2. 每個科別套用 SPECIALTY_MAPPING 對應規則
    3. 不在白名單也不在對應規則 → 歸類為「其他」
    4. 去重複後用 / 合併回傳
    """
    if not raw:
        return ''

    parts = re.split(r'[/、，,]', str(raw))
    seen = []
    seen_set = set()

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 套用對應規則
        mapped = SPECIALTY_MAPPING.get(part, part)

        if mapped in STANDARD_SPECIALTIES:
            # 對應結果整個在白名單（含 '復健/骨科' 這類含斜線的標準科別）
            if mapped not in seen_set:
                seen.append(mapped)
                seen_set.add(mapped)
        else:
            # 對應結果不在白名單，嘗試拆分（處理 '小兒科/外科' 這類複合對應）
            for sub in mapped.split('/'):
                sub = sub.strip()
                if sub not in STANDARD_SPECIALTIES:
                    sub = '其他'
                if sub not in seen_set:
                    seen.append(sub)
                    seen_set.add(sub)

    return '/'.join(seen)


# 區碼 → 本地號碼長度對應表
# 04 同時支援 7 碼（彰化縣）和 8 碼（台中市），依實際長度自動判斷
AREA_FORMATS = {
    "02":  {"local_digits": 8},
    "03":  {"local_digits": 7},
    "037": {"local_digits": 6},
    "04":  {"local_digits": [7, 8]},
    "049": {"local_digits": 7},
    "05":  {"local_digits": 7},
    "06":  {"local_digits": 7},
    "07":  {"local_digits": 7},
    "08":  {"local_digits": 7},
    "089": {"local_digits": 6},
}

# 縣市 → 預設區碼對應表（用於補區碼）
# 注意：苗栗縣卓蘭鎮例外使用 04，但無法從縣市名稱自動區分，預設 037
REGION_TO_AREA = {
    "台北市": "02", "臺北市": "02",
    "新北市": "02",
    "基隆市": "02",
    "桃園市": "03",
    "新竹市": "03", "新竹縣": "03",
    "宜蘭縣": "03",
    "花蓮縣": "03",
    "苗栗縣": "037",
    "台中市": "04", "臺中市": "04",
    "彰化縣": "04",
    "南投縣": "049",
    "雲林縣": "05",
    "嘉義市": "05", "嘉義縣": "05",
    "台南市": "06", "臺南市": "06",
    "高雄市": "07",
    "屏東縣": "08",
    "台東縣": "089", "臺東縣": "089",
}

# 3 碼區碼必須在 2 碼之前偵測，避免 037 被誤判為 03、089 被誤判為 08
_AREA_DETECT_ORDER = ["037", "049", "089", "02", "03", "04", "05", "06", "07", "08"]


def _apply_area_format(area: str, local: str, original: str) -> str:
    """
    根據區碼格式化本地號碼，長度不符則回傳原始輸入。

    格式規則：
        02 + 8碼  → 02-XXXX-XXXX
        03 + 7碼  → 03-XXX-XXXX
        037 + 6碼 → 037-XXX-XXX
        04 + 8碼  → 04-XXXX-XXXX（台中市）
        04 + 7碼  → 04-XXX-XXXX（彰化縣）
        049 + 7碼 → 049-XXX-XXXX
        05~08 + 7碼 → XX-XXX-XXXX
        089 + 6碼 → 089-XXX-XXX
    """
    expected = AREA_FORMATS[area]["local_digits"]

    # 判斷長度是否符合（04 可接受 7 或 8）
    if isinstance(expected, list):
        if len(local) not in expected:
            return original
    else:
        if len(local) != expected:
            return original

    # 依區碼套用格式
    if area == "02":  return f"02-{local[0:4]}-{local[4:8]}"
    if area == "03":  return f"03-{local[0:3]}-{local[3:7]}"
    if area == "037": return f"037-{local[0:3]}-{local[3:6]}"
    if area == "04":
        # 8碼：台中市；7碼：彰化縣
        if len(local) == 8: return f"04-{local[0:4]}-{local[4:8]}"
        if len(local) == 7: return f"04-{local[0:3]}-{local[3:7]}"
    if area == "049": return f"049-{local[0:3]}-{local[3:7]}"
    if area in ("05", "06", "07", "08"): return f"{area}-{local[0:3]}-{local[3:7]}"
    if area == "089": return f"089-{local[0:3]}-{local[3:6]}"
    return original


def format_phone(phone: str, region: str = None) -> str:
    """
    格式化電話號碼為標準台灣市話／手機格式。

    參數：
        phone  — 原始電話字串（可含空格、破折號等任意格式）
        region — 縣市名稱（用於無區碼時補區碼，e.g. "台北市"）；可為 None

    回傳：
        格式化後的電話字串；
        空值回傳 ""；
        無法判斷格式時回傳原始輸入（不改動）

    範例：
        format_phone("02 2876 6955")          → "02-2876-6955"
        format_phone("2876 6955", "台北市")   → "02-2876-6955"
        format_phone("037-322-150")           → "037-322-150"
        format_phone("322150", "苗栗縣")      → "037-322-150"
        format_phone("0933 090 809")          → "0933-090-809"
        format_phone("abc-1234", "台北市")    → "abc-1234"  # 無法判斷，保留原始
        format_phone("")                       → ""
    """
    # Step 1：空值守衛
    if not phone:
        return ""

    original = str(phone).strip()
    digits = re.sub(r'\D', '', original)  # 移除所有非數字字元

    # Step 2：去除非數字後仍為空（e.g. 純符號）
    if not digits:
        return original

    # Step 3：手機（09 開頭，10 碼）→ XXXX-XXX-XXX
    if digits.startswith("09"):
        if len(digits) == 10:
            return f"{digits[0:4]}-{digits[4:7]}-{digits[7:10]}"
        return original  # 長度異常，保留原始

    # Step 4：偵測市話區碼（3碼優先於2碼）
    for area in _AREA_DETECT_ORDER:
        if digits.startswith(area):
            local = digits[len(area):]
            return _apply_area_format(area, local, original)

    # Step 5：無區碼 → 根據 region 補區碼後格式化
    if region and region in REGION_TO_AREA:
        area = REGION_TO_AREA[region]
        expected = AREA_FORMATS[area]["local_digits"]
        # 判斷 digits 長度是否符合該區碼的本地號碼長度
        if isinstance(expected, list):
            ok = len(digits) in expected
        else:
            ok = len(digits) == expected
        if ok:
            return _apply_area_format(area, digits, original)

    # Step 6：無法判斷，保留原始輸入
    return original
