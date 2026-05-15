# NCUE-CSIE-UNIX-FINAL-PROJECT
---
## 1. 編譯 Sandbox
在專案根目錄下執行以下指令
```bash
make
```
## 2. 啟動 Worker 去資料庫 polling 資料
```bash
make worker
```
(欲關閉 Worker 請在 Terminal 直接按下 Ctrl + C)

## 3. 單純獨立測試沙盒環境
直接將單一 C 語言檔案送進沙盒測試，可執行：（之後會支援更多語言）
```bash
make run
```
(需把對應檔案取名 main.c 放進 ./sandbox/tmp/test 裡）

---
