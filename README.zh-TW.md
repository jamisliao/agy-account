# agy-account

[English](README.md) | [繁體中文](README.zh-TW.md)

Google Antigravity CLI (`agy`) 多帳號管理與 macOS Keychain 毫秒級輪替工具。

---

## 為什麼需要本工具？

Google 官方 Antigravity CLI (`agy`) 在 macOS 上透過系統鑰匙圈（macOS Keychain，`Service='gemini'`, `Account='antigravity'`）存取使用者的 OAuth 憑證。

當您需要切換多個 Google 帳號（例如公務、個人或不同配額專用帳號），或是透過程式執行大量批次任務時，官方 CLI 每次切換帳號皆需重新開啟瀏覽器登入。

`agy-account` 直接讀取與寫入 macOS Keychain，將各帳號憑證快取於本地設定檔目錄，達成**免開瀏覽器、毫秒級即時切換**。

---

## 核心功能

1. **Keychain 快速切換**：直接置換系統鑰匙圈憑證，切換瞬間生效，終端機與 Paseo IDE 皆可立即使用新帳號。
2. **跨帳號防污染機制**：回寫與同步前嚴格檢查 Token 內的 Email，確保不會意外覆蓋不同帳號的憑證。
3. **自動帳號輪替 (Rotation)**：支援一鍵切換至下一個可用帳號，方便於批次任務遇 429 配額限制時自動重試。
4. **完整生命週期管理**：支援 `save`、`switch`、`rotate`、`list`、`current`、`rename`、`delete`、`test`。
5. **Python 模組支援**：除了 CLI 指令外，亦提供 `AccountManager` 與 `temporary_context` 上下文管理器供自動化腳本調用。

---

## 安裝方式

### 方法 1：執行安裝腳本（建立全域軟連結）

```bash
cd ~/opensource/agy-account
./install.sh
```

這會將執行檔軟連結建立至 `~/.local/bin/agy-account`。請確認 `~/.local/bin` 已加入您的 `$PATH` 環境變數。

### 方法 2：使用 pip 安裝

```bash
cd ~/opensource/agy-account
pip install -e .
```

---

## 指令使用說明

### 1. 檢視目前狀態與清單

```bash
# 顯示目前作用中的帳號
agy-account current

# 列出所有已保存帳號與對應 Email
agy-account list
```

### 2. 切換帳號

```bash
# 切換至指定別名帳號
agy-account switch <帳號別名>

# 自動輪替到下一個可用帳號
agy-account rotate
```

### 3. 新增全新 Google 帳號

當您需要加入一個全新的 Google 帳號時：

```bash
# 步驟 1：暫時移除 Keychain 憑證以觸發官方登入流程
security delete-generic-password -s gemini -a antigravity 2>/dev/null
agy -p "ping"

# 步驟 2：在瀏覽器中完成 Google 授權

# 步驟 3：將新登入的憑證儲存為別名
agy-account save <新帳號別名>
```

### 4. 帳號憑證重新授權（過期時）

若某帳號過期需要重新登入：

```bash
# 切換到該帳號
agy-account switch <帳號別名>

# 重新登入並覆蓋存檔
security delete-generic-password -s gemini -a antigravity 2>/dev/null
agy -p "ping"
agy-account save <帳號別名>
```

### 5. 管理與維護

```bash
# 修改帳號別名
agy-account rename <舊別名> <新別名>

# 刪除已儲存帳號
agy-account delete <帳號別名>

# 測試當前帳號的 API 連線狀況
agy-account test
```

---

## Python API 使用範例

您可以在自動化腳本中直接匯入：

```python
from agy_account import AccountManager

mgr = AccountManager()

# 取得目前帳號
print("目前帳號:", mgr.get_current_profile())

# 暫時切換工作帳號，離開 context 時自動復原
with mgr.temporary_context(target_alias="tool", restore_alias="work"):
    # 在此區塊內，Keychain 會切換為 tool
    pass
# 離開區塊後，自動切回 work
```

---

## 運作原理與目錄結構

* **系統憑證**：存放在 macOS Keychain (`Service='gemini'`, `Account='antigravity'`)。
* **保存設定檔**：各別名的憑證檔案存放在 `~/.gemini/antigravity-cli/profiles/`（檔案權限限設 `0600` / 目錄 `0700`）。
* **自訂目錄**：可透過環境變數 `ANTIGRAVITY_CLI_HOME` 覆寫基礎設定路徑。

---

## 授權

MIT License
