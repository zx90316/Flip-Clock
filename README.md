# ESP32-CAM 翻頁時鐘

一顆 AI-Thinker ESP32-CAM 直接驅動 ULN2003 與一顆 5V 28BYJ-48。時間來自 Wi-Fi 的網路時間，操作全部在 ESP 提供的網頁上，韌體可用網頁 OTA 更新。

**目前狀態：0.4.7 單主控版具備響應式裝置控制台，尚未在實機上跑過。** 網頁可顯示步數與餘數規劃；手動進步只調整馬達角度，不修改位置或餘步。歸零後可直接儲存並開始走時。舊 Wi-Fi 連不上時，裝置會維持穩定熱點供重新設定。高速度仍需在實際機構上驗證。

機構與步數參考：[TunyFPV 的 Flip Clock 設定](https://gitlab.com/-/snippets/4791675)。專案公開 Repo：[zx90316/Flip-Clock](https://github.com/zx90316/Flip-Clock)。先前的 ESP＋Uno 雙主控版本保留在 Git 歷史（提交 `8d25573`）。

## 文件

- [接線與電源](docs/wiring.md)
- [從零開始的步驟](docs/bringup.md)
- [網頁操作與行為](docs/web.md)
- [序列與 BLE 維修操作](docs/operation.md)
- [BLE 協定與保存格式](docs/protocol.md)
- [驗證紀錄與實機待測](docs/validation.md)
- [VS Code 操作](docs/vscode.md)
- [早期工程規格（雙主控，僅供歷史參考）](docs/engineering-spec.zh-TW.md)

## 全新機構 CAD（FC-R1）

單馬達雙棘輪、24 片時輪與 60 片分輪的全新參數化設計位於 [cad/README.md](cad/README.md)。
模型未匯入原作者幾何；目前為工程原型，實測校準、負載及實機驗證尚待完成。
已提供 [重力與碰撞影片、物理回放及已知限制](cad/PHYSICS_VIEW.md)，包含 84 片獨立翻片與有限力矩的正反向輸入。
CAD 的雙輸出回授控制需求尚未整合至下方既有韌體。

## 韌體建置

需要 Python 3.12 與網路。工具安裝於本專案 `.tools/`，不修改全域 Arduino 安裝。VS Code 開啟專案後，F5 選「Flip：主控操作台」，或 Ctrl+Shift+B 建置。

```powershell
python tools/build.py setup
python tools/build.py test
python tools/build.py build
```

鎖定 Arduino CLI 1.5.1、Arduino-ESP32 3.3.12、NimBLE-Arduino 2.5.1。FQBN 為 `esp32:esp32:esp32cam:PartitionScheme=min_spiffs,FlashFreq=40`（4 MB Flash、雙 OTA 分區各 1.9 MB）。

```text
firmware/esp32_clock/   韌體
shared/protocol/src/    韌體與測試共用的核心（馬達、規劃、保存、BLE 分行）
tools/                  建置、燒錄與 BLE 工具
tests/                  真正的控制程式搭配模擬外設
dist/esp32_clock/       可燒錄映像與 SHA-256
```

## 更新韌體

平常在網頁的「韌體更新（OTA）」上傳 `dist/esp32_clock/esp32_clock.ino.bin`。OTA 失敗才需要序列救援，見 [接線文件](docs/wiring.md)。

每次推送到 GitHub 的 `main` 後，[Actions → Build OTA firmware](https://github.com/zx90316/Flip-Clock/actions/workflows/ota.yml) 會自動執行測試與 ESP32-CAM 建置。點開最新成功的執行紀錄，在 **Artifacts** 下載 `flip-clock-ota-v…`，解壓縮後只將 `esp32_clock.ino.bin` 上傳到裝置網頁；`SHA256SUMS.txt` 可用於核對下載檔案。也可在 Actions 頁面手動執行。GitHub 的執行產物保留 90 天；建置失敗時不會提供 OTA 產物。

## 重要行為

- 馬達由獨立計時器驅動，網頁、Wi-Fi、BLE 不會卡住動作；步進晚到只會稍微停頓，不會補衝。
- 每次移動有步數與時間上限，結束或逾時都會關閉線圈。
- 開機保持暫停；取得網路時間後，從儲存的位置自動補跑到現在的時間。
- 沒有原點感測器：步數送完不代表機構確實翻頁，移動中斷電會失去位置，需要重新歸零。
- 顯示只比時間領先 60 分鐘以內時，原地等時間追上，不會繞一整圈。

授權：[GPL-3.0](LICENSE)；依賴授權與來源見 [manifest](manifest.json)。
