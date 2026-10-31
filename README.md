# ESP32-CAM＋Uno 雙主控翻頁時鐘

這是依使用者提供的 **v2.0 繁體中文工程規格**建立的獨立版本。ESP32-CAM 管理時間、BLE、Wi-Fi、RTC 與設定；Uno R3 控制一顆 28BYJ-48。參考分支的 Mega2560／ESP32-S 多字元功能未移入這個獨立 Repo；其腳位、12 V 馬達、45 字元及 4096 步設定不適用本版本。

**目前狀態：兩板已編譯，Uno 0.2.0 已在 COM3 燒錄／校驗並讀回安全待機；ESP 與馬達接線／實測尚未完成。** 出廠設定 `mechanics_confirmed=false`、位置 unknown、暫停、反轉停用。200 half-steps/s 是軟體起測上限，尚非實機合格速率。沒有原點感測器，每次重啟仍須目視確認實際頁面。

本地基底：[zx90316/split-flap 的 esp32-purchased-bom](https://github.com/zx90316/split-flap/tree/esp32-purchased-bom)，提交 `f4216b735131ca2adf7772f3dbfca01d22112111`。本專案公開 Repo：[zx90316/Flip-Clock](https://github.com/zx90316/Flip-Clock)，分支 `main`。

## VS Code 快速開始

正式專案在 **D:\Project\Flip-Clock**。開啟此資料夾後，按 F5 選「Flip：主控操作台」；「終端機 → 執行工作」有 39 個建置／燒錄／維修／BLE Tasks。Ctrl+Shift+B 建置兩板。

先讀 [逐段接線](docs/bringup.md) 與 [VS Code 操作](docs/vscode.md)。目前只完成 Uno 單板 USB；下一段是單顆 5V 馬達空載試轉，先不接 ESP。

## 先看這些文件

- [接線、電源與三種模式切換](docs/wiring.md)
- [初次啟用、校準與日常操作](docs/operation.md)
- [協定、保存格式與 BLE 規則](docs/protocol.md)
- [已完成的驗證與實機待測清單](docs/validation.md)
- [原始工程規格](docs/engineering-spec.zh-TW.md)
- [版本與授權 manifest](manifest.json)

## 建置

需要 Python 3.12 與網路。以下從 **專案根目錄 D:\Project\Flip-Clock**執行，工具與套件安裝於本專案 `.tools/`，不修改全域 Arduino 安裝。首次 ESP32 套件下載量大，包含官方提供的多平台工具與函式庫。

```powershell
python tools/build.py setup
python tools/build.py test
python tools/build.py build
```

鎖定 Arduino CLI 1.5.1、Arduino AVR 1.8.8、Arduino-ESP32 3.3.12、NimBLE-Arduino 2.5.1。BLE 依賴有一個可檢查的配對政策補丁：拒絕自動覆蓋既有 bond；重新配對須本地清除 bond。建置腳本驗證原檔及補丁內容，並設定 Secure Connections only。不要直接在未套用設定的 Arduino IDE 中編譯後宣稱與交付映像一致。

只有 Windows 專案路徑較長時，腳本才暫時對應一個未使用的磁碟代號來縮短路徑，結束後解除；這是避免官方 GCC 的路徑長度限制。主機測試使用鎖定的 Zig 0.13.0 與測試用 cJSON 1.7.19。

```text
firmware/esp32_clock/       ESP32-CAM 韌體
firmware/uno_motor/         Uno 馬達韌體
shared/protocol/src/       兩板與測試共用的 C++ 核心
shared/protocol/vectors.*  獨立 Python 協定向量
tools/                     建置、燒錄與 BLE 驗收工具
tests/                     真正控制程式搭配模擬外設的測試
dist/esp32_clock/          ESP32 .bin、.elf、分區與 SHA-256
dist/uno_motor/            Uno .hex、.elf 與 SHA-256
docs/                      接線、操作、原規格與驗證紀錄
```

## 燒錄

先關閉馬達電源，依 [模式表](docs/wiring.md)改接線，再查實際 COM。開啟 Uno 序列埠可能觸發 DTR reset，維修前先停止裝置。

```powershell
python tools/build.py ports
python tools/build.py upload --board uno_motor --port <實際COM>
python tools/build.py upload --board esp32_clock --port <實際COM>
```

兩條 upload 命令是**不同接線模式下分別操作**，不能接著執行而不切換接線。ESP32 FQBN 為 `esp32:esp32:esp32cam:PartitionScheme=huge_app,FlashFreq=40`；目前映像以 4 MB Flash、40 MHz、無 OTA 分區為目標，施工前確認實際 Flash 容量。ESP 首次／救援燒錄由 Uno 板載 USB UART 傳送，不是 Uno 執行 ArduinoISP。腳本會重新編譯、上傳並要求驗證，不開啟馬達。

## BLE 桌面工具

可在獨立虛擬環境安裝；Windows 的完整版本鎖定另附 `tools/requirements-windows.lock.txt`。

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r tools/requirements-windows.lock.txt
.venv/Scripts/python tools/ble_client.py --scan
.venv/Scripts/python tools/ble_client.py --address <掃描到的位址>
```

第一次須先在 ESP 的 UART 維修介面輸入 `pair`，120 秒內依作業系統提示輸入該次印出的六位數 passkey。之後由系統 bond 保管金鑰；工具不保存 passkey。BLE 工具是桌面驗收用，尚未交付原生 Android／iOS App，也沒有聲稱手機配對已實測。

互動模式可下 `status`、`time`、`display 10:30`、`jog 4`、`pages 1`、`preview`、`resume`、`pause`、`stop`、`save`。移動命令不阻塞輸入，可繼續送 stop。`time` 會取電腦當下 UTC 秒數；手機仍可用一般 GATT 工具依協定操作。

## 重要行為

- RTC 存 UTC，本地預設 +480 分鐘；OSF 或日曆無效時禁止自動走時。網路時間不掩蓋 RTC 失聯。
- 一頁一筆 Uno 工作；核對 session、工作序號、DONE、完整步數及輸出關閉後才提交顯示索引與小數餘額。
- BLE 與 I²C 重送使用原 id／seq 及原內容，不重新執行已受理移動；斷電後 RAM 去重表不保留，故不承諾跨任意掉電 exactly-once。
- `pause` 等當頁完成再 DISARM；`stop` 可停在半頁，位置隨即失效。Uno 心跳期限 1.5 秒，實際 1.6 秒關閉目標仍須實測。
- 設定 A/B blob、CRC32、讀回後才回 `persisted:true`。保存的頁面只是歷史參考，不是重啟後自動採用的位置。
- 手動校時關閉 `auto_time`；SNTP 新時間先暫停，差超過五分鐘要額外確認；小修正套用後也須重新預覽及 resume。
- 無相機、SD、MCP23017 馬達路徑、網頁控制或 OTA。這些不列入本版必要範圍。

授權：[GPL-3.0](LICENSE)；依賴授權與來源見 manifest。
