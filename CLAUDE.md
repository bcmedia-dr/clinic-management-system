# 診所管理系統 CLAUDE.md

## 專案說明
BCM/Bcmedia 診所管理系統，追蹤診所資料、合作項目、活動記錄。

## 技術架構
- 後端：Flask (Python)，所有邏輯在 app.py 單一檔案
- 資料庫：本地 SQLite（開發）/ PostgreSQL on Render（正式）
- 部署：git push → GitHub → Render 自動部署
- 前端：HTML + JS（內嵌在 Flask templates）

## ⚠️ 最重要規則（每次都要遵守）

### 1. doctor table 絕對不能動
- doctor-db 資料庫共用兩個系統：診所管理系統 + 醫師資料庫
- doctor table 絕對不能修改、不能新增欄位、不能刪除資料
- 只能操作 clinic、health_mall、campaign、campaign_clinic、baiwei_doctor、audit_log table

### 2. 每次修改完必須 git push
- 修改完程式碼後，一定要執行：
  ```
  git add . && git commit -m "說明" && git push
  ```
- 沒有 push 就沒有部署，雲端不會更新

## 系統六個分頁
1. 診所管理 - 總表，CRUD，匯入/匯出
2. 健康醫購 - 獨立 health_mall table
3. 活動比對 - 上傳 Excel 比對電話
4. 活動記錄 - campaign + campaign_clinic table
5. 百位 - 獨立 baiwei_doctor table
6. 統計分析 - 圖表統計

## 合作項目欄位
- col_yaodai（藥袋）
- col_haibao（海報/立牌）
- col_paiyang（派樣）
- col_baiwei（百位）

## 電話比對規則
- 所有比對一律使用 phone_normalized 欄位
- 編輯電話時必須同步更新 phone_normalized
- 不可用 _normalize_phone(c.phone) 即時重算來比對

## 常見錯誤提醒
- Flask 3.0 已移除 @app.before_first_request，不要使用
- PostgreSQL 和 SQLite 語法不同，兩者都要相容
- 匯入 Excel 用 read_only=True 減少記憶體用量
- 所有 API 錯誤必須回傳 JSON，不能讓 Flask 回傳 HTML 500
- db.session.rollback() 要用 try 包住，避免連線斷開時拋出例外
