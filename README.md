# Ditto Agent Lab｜MySQL 與共同修訂測試版

聊天、來源預覽、選取修訂、貼圖、完整版本歷史及查詢回饋。仍為獨立測試系統：未串接正式 Ditto、真實登入或自動更新知識庫。

## 在現有 Ubuntu 24.04 虛擬機更新

先停止舊程式（Ctrl+C），再於原專案目錄執行：

```bash
git pull --ff-only
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

若尚未 clone：先執行 `git clone https://github.com/Dancingbear0305/AI-Agent.git` 再 `cd AI-Agent`。若缺少 venv，經該機管理規範允許後執行 `sudo apt install python3-venv`。不要使用 sudo pip。

### 設定本機 MySQL cindydb

假設已建立專用資料庫 `cindydb`、帳號 `cindy_app` 並授權；不需要更改 root 或其他人的帳號，不需要重啟 MySQL。

第一次才複製設定（已有 .env 時不要覆蓋）：

```bash
cp -n .env.example .env
chmod 600 .env
nano .env
```

填入 `DB_PASSWORD` 的真實密碼，只留在虛擬機，不要貼到 GitHub 或聊天。預設設定如下：

```dotenv
DB_BACKEND=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=cindydb
DB_USER=cindy_app
DB_PASSWORD=請在虛擬機填入你的密碼
HOST=127.0.0.1
AI_MODE=demo
```

值可以用單引號或雙引號包住；不支援變數展開、跳脫字元或行尾註解。既有環境變數優先於 .env；環境變數如有舊值，請先移除或同步更新。如果 TCP 驗證失敗，可在直接 Python 模式設定 `DB_SOCKET=/var/run/mysqld/mysqld.sock`，沿用本機 Unix socket。

確認密碼不會被 Git 追蹤：

```bash
git check-ignore -v .env
git ls-files -- .env
```

第二行應無輸出。程式會自動讀 .env；資料庫帳密不會送到前端。不要執行或分享會列出環境密碼的指令，例如未遮蔽的 `docker compose config`。

啟動：

```bash
python app.py
```

首次會在 cindydb 建立本專案資料表及虛構知識。**請使用獨立的 cindydb，不要填其他應用的資料庫；本程式使用 knowledge、queries 等通用表名。** MySQL 連線失敗會停止，不會改寫 root 或退回 SQLite。

### 打開網頁

虛擬機本身的瀏覽器開 `http://127.0.0.1:8080`。如要允許已核准的內網測試，在 .env 設定 `HOST=0.0.0.0` 並重啟，再從 Windows 瀏覽器輸入 `http://虛擬機IP:8080`；需網路及防火牆允許，不能填 0.0.0.0 作目的網址。

本版沒有真實登入，能連到服務的人都能查詢及修改。僅供限定範圍的測試；SSH 通道可保留 HOST=127.0.0.1。

## 新操作

- 回答內的來源標籤：滑鼠移上或鍵盤聚焦即在回答下方展開，推開下方內容，不覆蓋 AI 回答；點擊可固定。顯示的是回答當時的知識快照，包含附件。
- 在知識正文或來源預覽選取文字：出現「修改選取內容」；聊天內的按鈕位於該則回答下方，游標移上／鍵盤聚焦／點擊即可展開內嵌編輯區，不跳出遮罩或覆蓋回答。輸入替換文字，確認完整知識後保存；游標移開不會丟失輸入。知識庫頁仍使用原編輯視窗。
- 在 AI 回答選取：確認要更新的來源；若無法唯一對應原文，直接編輯全文預覽，不能任意把生成文字當原文替換。
- 浮框內 Ctrl+V 貼圖或選擇檔案：PNG/JPEG/WebP，每張原始檔不超過 2 MB、1600 萬像素；每次最多 4 張新圖，每篇最多 12 張。伺服器重新編碼後存進 MySQL（或 SQLite），隨知識版本關聯保存。圖片是附件，不會自動 OCR，也不會送模型解讀。
- 修改後顯示當前正文，下方列出日期、修改差異與修改人標籤，展開可看修改前後全文、原因及該版本圖片。
- 舊版內容修訂若已過期，會拒絕保存；重新開啟知識庫最新版本後再修改，不自動覆寫他人的修改。
- 「總查詢／回饋／知識修訂」三個數字卡片可點擊，切換相應紀錄；已移除提問人數。知識修訂不含系統初始資料，新建知識計為一筆。
- 回饋「太冗長」只記錄，不會偷偷改 prompt。模型模式提供「重新精簡回答」，以原問題及原來源重新產生一則精簡版，原回答仍保留，紀錄顯示關聯。

## 模型設定

demo 不需 key，顯示檢索原文，不會摘要。MySQL 與 AI 是兩個獨立設定。

如要真正生成回答，在 .env 設定 `AI_MODE=openai`、`AI_BASE_URL`（以 /v1 結尾）、`AI_MODEL` 及 `AI_API_KEY`，重啟。適用相容 Chat Completions 的公司核准服務或本機模型。key 不會提交或送到前端。

簡單關鍵字檢索不是語意搜尋；對話為逐題查詢，沒有前文推理。模型來源需人工核實，修改 prompt 為手動版本管理，回饋不是模型訓練。

## 舊資料與備份

既有 SQLite `data/ditto.sqlite3` 不會被刪除；換 MySQL **不會自動搬移舊資料**，MySQL 初次使用獨立測試資料。若要沿用 SQLite，在 .env 設 `DB_BACKEND=sqlite`。正式資料搬移應另行核對與備份。

MySQL 的文字、圖片、查詢與版本都在資料庫，請交由該機既有備份流程備份 cindydb；備份不要放 Git。`.gitignore` 已排除 .env、venv、資料目錄、SQL 備份、常見金鑰及日誌，但仍需檢查實際提交內容。

## Docker（Linux 選用）

也可以用 `docker compose up -d --build`。本版改為 **host network**，讓容器連到虛擬機本機 MySQL，因此僅適用 Linux，不需對外開放 3306。Compose 讀 .env 並傳入設定。HOST 決定網頁監聽範圍；Docker 使用 TCP DB_HOST/DB_PORT，不使用 DB_SOCKET。

原本 Docker SQLite named volume 仍保留；`docker compose down` 不刪資料，勿用 `down -v`。SQLite 直接 Python 與 Docker 的資料目錄不同。

## 驗證

```bash
source .venv/bin/activate
python -m unittest -v
```

測試預設使用暫存 SQLite，不讀寫 MySQL 資料（測試檔會強制隔離）；詳細手動案例見 TESTING.md。JavaScript 語法可用 `node --check static/app.js` 檢查。
