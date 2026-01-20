# Bcmedia 診所管理系統（含統計分析）

完整的診所資料管理系統，支援本地開發和雲端部署，**新增專業統計分析儀表板**。

## ✨ 新功能：統計分析儀表板

### 🗺️ 台灣地圖視覺化
- 真實的台灣地圖顯示各縣市診所分布
- 顏色深淺代表診所數量
- 可縮放、拖曳互動

### 📊 多維度圖表分析
1. **各縣市診所數量排行**（長條圖）
2. **診所科別分布**（圓餅圖）
3. **健康醫購比例**（圓餅圖）
4. **各縣市健康醫購分布**（堆疊長條圖）

### 📈 即時統計摘要
- 總診所數
- 涵蓋縣市數
- 科別種類數
- 健康醫購比例

## 功能特色

### ✅ 診所資料管理
- 新增、編輯、刪除診所資料
- 支援多科別選擇（可複選）
- 完整的診所資訊記錄

### ✅ 篩選與搜尋
- 依地區篩選
- 依科別篩選
- 依健康醫購狀態篩選
- 全文搜尋（診所名稱、地址、負責人）

### ✅ 統計分析
- 台灣地圖視覺化
- 多種圖表類型
- 即時資料更新
- 互動式圖表

## 快速開始

### 本地測試

```bash
# 1. 解壓縮
# 2. 進入資料夾
cd clinic_management_system

# 3. 安裝套件
pip install -r requirements.txt

# 4. 初始化資料庫
python3 init_db.py

# 5. 啟動系統
python3 app.py

# 6. 訪問 http://localhost:8081
```

### 雲端部署（Render）

```bash
# 1. 建立 GitHub Repository
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/你的帳號/clinic-management-system.git
git push -u origin main

# 2. 在 Render 部署
# - 登入 Render Dashboard
# - New → Blueprint
# - 連接 GitHub Repository
# - 自動部署

# 3. 初始化雲端資料庫
# 在 Render Shell 執行：
python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
python3 init_db.py
```

## 登入帳號

**管理員：**
- 帳號：`admin`
- 密碼：`Bcm13011579!@`

**一般用戶：**
- 帳號：`user`
- 密碼：`Bcm13011579`

## 系統頁面

### 1. 診所管理頁面（/）
- 診所列表
- 新增/編輯/刪除
- 篩選搜尋

### 2. 統計分析頁面（/analytics）⭐ **新增**
- 台灣地圖
- 多種圖表
- 統計摘要

## 技術架構

### 後端
- **Flask 3.0** - Web 框架
- **SQLAlchemy** - ORM
- **PostgreSQL** - 雲端資料庫
- **SQLite** - 本地資料庫

### 前端
- **HTML5 + CSS3**
- **ECharts 5.4** - 圖表庫 ⭐ **新增**
- **原生 JavaScript**

### 視覺化
- **ECharts** - 專業圖表庫
- **台灣地圖** - GeoJSON 格式
- **互動式圖表** - 縮放、拖曳、提示

## API 端點

### 診所管理
- `GET /api/clinics` - 取得診所列表
- `POST /api/clinics` - 新增診所
- `PUT /api/clinics/<id>` - 更新診所
- `DELETE /api/clinics/<id>` - 刪除診所

### 統計分析 ⭐ **新增**
- `GET /api/analytics/regions` - 各縣市統計
- `GET /api/analytics/specialties` - 科別統計
- `GET /api/analytics/health_mall_by_region` - 健康醫購分布
- `GET /api/analytics/taiwan_map` - 台灣地圖資料

## 專案結構

```
clinic_management_system/
├── app.py                      # Flask 主程式（含統計 API）
├── init_db.py                 # 資料庫初始化
├── requirements.txt           # Python 套件
├── render.yaml               # Render 部署配置
├── .gitignore               # Git 忽略檔案
├── README.md                # 說明文件
└── templates/
    ├── login.html          # 登入頁面
    ├── index.html          # 診所管理頁面
    └── analytics.html      # 統計分析頁面 ⭐ 新增
```

## 範例資料

系統包含 8 筆範例診所資料，涵蓋：
- **地區**：台北、新北、桃園、台中、台南、高雄、新竹
- **科別**：小兒科、家醫科、耳鼻喉科、婦產科、皮膚科、泌尿科、中醫
- **健康醫購**：5 筆是、3 筆否

## 圖表說明

### 🗺️ 台灣地圖
- **用途**：一眼看出各縣市診所密度
- **互動**：縮放、拖曳、懸停查看數量
- **顏色**：深藍色=多，淺藍色=少

### 📊 縣市排行
- **用途**：比較各縣市診所數量
- **排序**：由多到少
- **顯示**：長條圖 + 數字標籤

### 🏷️ 科別分布
- **用途**：了解科別占比
- **類型**：環形圓餅圖
- **標籤**：科別名稱 + 百分比

### ✅ 健康醫購
- **用途**：快速了解健康醫購比例
- **類型**：圓餅圖
- **顏色**：綠色=是，紅色=否

### 📈 各縣市健康醫購
- **用途**：比較各縣市健康醫購分布
- **類型**：堆疊長條圖
- **顏色**：綠色=是，紅色=否

## 常見問題

### Q: 如何進入統計分析頁面？
A: 登入後，點選頂部導航的「📊 統計分析」按鈕

### Q: 圖表資料如何更新？
A: 新增/編輯/刪除診所後，重新整理統計頁面即可

### Q: 可以匯出圖表嗎？
A: ECharts 支援右鍵儲存為圖片

### Q: 本地版和雲端版圖表一樣嗎？
A: 完全一樣，使用相同的技術

## 更新日誌

### v2.0 (2026-01-20) ⭐ **最新版本**
- ✨ 新增統計分析儀表板
- ✨ 新增台灣地圖視覺化
- ✨ 新增 5 種互動式圖表
- ✨ 新增統計 API 端點
- 🎨 優化整體設計

### v1.0 (2026-01-19)
- 🎉 初始版本
- ✅ 診所管理功能
- ✅ 篩選搜尋功能

## 授權

© 2026 Bcmedia. All rights reserved.
