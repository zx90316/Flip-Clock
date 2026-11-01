# VS Code 操作

開啟 `D:\Project\Flip-Clock`。F5 選 **Flip：主控操作台**，或在「終端機 → 執行工作」選 Task。Ctrl+Shift+B 建置韌體，另有預設的測試 Task。

F5 除錯的是電腦端工具，不能對 ESP 下硬體斷點。平常更新韌體用網頁 OTA，序列燒錄只在救援時使用，接線見 [wiring.md](wiring.md)。

序列維修台：輸入一行後 Enter；`/quit` 或 Ctrl+C 關閉。燒錄前先關閉其他占用同一 COM 的視窗，不要中斷正在寫 Flash 的工作。

連接埠只有一個時自動使用，多個時會詢問。個人連接埠與 BLE 位址存在 `.local/settings.json`，不進 Git。

其他電腦需要 Python 3.12，先執行 `Flip：安裝編譯環境`，再 `Flip：準備桌面操作工具`。`.vscode` 由 `python tools/configure_vscode.py` 產生。
