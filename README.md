# Ditto Agent Lab｜Linux 測試版

打開首頁就是 Agent。這是獨立原型，尚未串接正式 Ditto、既有自動更新知識庫或真實帳號。

## 最快開始：Linux 已有 Python 3.10 以上

不需 pip、不需模型金鑰、不需 GPU。測試機已安裝 Git 時，直接執行：

```bash
git clone https://github.com/Dancingbear0305/AI-Agent.git
cd AI-Agent
python3 --version
python3 app.py
```

看到 `Ditto Lab: http://127.0.0.1:8080 | mode=demo` 後：

- 在測試機本身操作瀏覽器：開啟 `http://127.0.0.1:8080`。
- 從自己的電腦使用：保留服務執行，在自己電腦另一個終端機建立 SSH 通道：

```bash
ssh -N -L 18080:127.0.0.1:8080 你的Linux帳號@測試機IP
```

然後在**自己電腦**的瀏覽器開啟 `http://127.0.0.1:18080`。SSH 通道與伺服器都需保持開啟；Ctrl+C 可停止。若 18080 被佔用，換另一個本機連接埠。

這個做法不需要開放額外網站連接埠。測試身分只是模擬，沒有真正登入或編輯權限限制，先用 SSH 通道測試；本版不應直接對外公開。

## 選用：用 Docker Compose 管理常駐服務

Linux 已安裝 Docker Engine 與 Compose plugin 時，在專案目錄執行：

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f
```

同樣使用上述 SSH 通道與網址。停止：

```bash
docker compose down
```

SQLite 存在 named volume `ditto-data`，重新建立容器或 `down` 不會刪除資料；不要使用 `down -v`，那會刪除資料。直接 Python 模式存到 `data/ditto.sqlite3`；這兩種方式的資料存放位置不同，不會自動共用。

## 功能與怎麼操作

- **AI Agent**：輸入問題、查看引用來源、在回答下方分開回報正確性及滿意度。
- **測試身分**：右上角切換小陳／小林／小王。回饋與修改均以操作當下的身分記錄。
- **共同知識庫**：新增、修改知識。聊天回答下的來源按鈕可直接開啟該篇最新版本的編輯視窗；從聊天修改會關聯原查詢。
- **版本紀錄**：修改須填原因；並行編輯過期版本會被拒絕，避免覆蓋他人的更新。若要還原，可把歷史內容複製到編輯框，另存新版本。
- **查詢與回饋**：查誰問、什麼時間、原問題、回答、來源快照、prompt 版本、回饋，以及誰修改知識。
- **問題次數**：相同問題忽略標點、空白與大小寫；近似主題依第一筆檢索來源分組，包含相同問題本身，並非語意相似度。未知問題分別記錄，不全部合併。
- **Prompt 版本**：手動修改並保留歷史。下一次模型回答使用最新版；不會因收到回饋自動改寫 prompt。
- **測試指南**：有 8 題可一鍵帶入的問題，更多驗收案例見 `TESTING.md`。

服務重啟後資料仍保留。聊天頁的目前訊息在重新整理後清空，歷史回答可在紀錄頁查看。「新對話」不刪除歷史。對話編號用於記錄分組，當前回答為逐題檢索，不使用前文作推理。

## 兩種模式

### 1. demo（預設，沒有外部模型）

使用關鍵字及中文字元重疊檢索，顯示完整來源原文。知識更新後直接讀取 SQLite 新內容，不需要等待向量索引。

可以測試共同編輯、來源、回饋、身分、版本、紀錄；**不會依 prompt 生成或摘要**。不能以此模式評估真正模型的語意理解、回答長度或推理品質。

### 2. openai（相容 Chat Completions API）

適用公司允許的模型服務，或支援相同 API 的本機服務。先確認所用模型支援 `/chat/completions`。金鑰只放在伺服器端，請勿貼到聊天或前端。

直接 Python 啟動時，設定環境變數；以下模型名稱與網址要換成實際服務設定：

```bash
export AI_MODE=openai
export AI_BASE_URL=https://api.openai.com/v1
export AI_MODEL=你的模型名稱
read -rs -p '輸入 API key: ' AI_API_KEY
export AI_API_KEY
python3 app.py
```

本機無金鑰服務可以不設 `AI_API_KEY`。模型服務超時或回應無效時會顯示失敗，不會悄悄改成 demo；失敗請求不記為成功查詢。

Docker 模式：複製 `.env.example` 為 `.env`，填好後執行 `docker compose up -d` 重新建立服務。`.env` 中金鑰不應提交到版本控制。本機模型在容器外時，不要使用 `localhost` 指向宿主機；需設定容器可連到的模型位址。

真實模式仍使用同一套簡單檢索；回答的來源清單代表提供給模型的參考資料，不保證模型每一句話都受來源支持，需人工驗證。自訂 prompt 的效果只在模型模式可評估。

## 測試與維護

```bash
python3 -m unittest -v
node --check static/app.js
```

第一個指令只需 Python；第二個為選用的 JavaScript 語法檢查，需要 Node.js。備份直接 Python 模式的資料時，先停止服務，再複製整個 `data/` 目錄。可用 `DATA_DIR` 指定資料目錄，`PORT` 更改預設 8080。

## 後續接正式 Ditto

目前以手動新增／修改模擬知識更新。正式串接還需確認 Ditto 程式框架、帳號權限、知識庫格式與自動更新事件；再接入登入、資料同步／刪除與衝突規則，以及適合的語意檢索。Linux 部署只是執行方式，沒有自動完成這些串接。

## 專案結構

```text
app.py             HTTP API、SQLite、檢索、模型介接
static/            聊天與管理介面，無第三方 CDN
Dockerfile         Python 容器，非 root 執行
compose.yaml       本機綁定、持久化資料、健康檢查
.env.example       選用模型設定
TESTING.md         測試問題與驗收流程
test_app.py        13 項自動測試
```
