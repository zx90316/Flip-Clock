# VS Code 操作

正式專案：`D:\Project\Flip-Clock`。請開啟這個資料夾；所有工具依自己的專案位置定位，不依賴舊的 C 槽工作區。

F5 選 **Flip：主控操作台**，可從選單執行建置、測試、兩板燒錄、Uno 診斷、ESP UART 維修／配對／Wi-Fi、BLE 校時與校準。也可在「終端機 → 執行工作」選專用 Task。Ctrl+Shift+B 建置兩板；軟體測試有預設 test task。

目前提供 39 個 Tasks、12 個 Launch；Python、Python Debugger、C/C++ 擴充已安裝於這台 VS Code。F5 除錯的是電腦端工具，沒有宣稱可對 MCU 直接下硬體斷點。

## 常用順序

1. `Flip：檢查環境`／`Flip：列出連接埠`。
2. `Uno：燒錄並驗證（單板 USB）` → `Uno：讀取安全待機狀態`。
3. 完成 bringup 接線後，`Uno：單顆空載試轉 16 半步（需先接線）`。
4. 切換接線後，`ESP：燒錄並驗證（Uno UART 模式）`。
5. ESP 正常開機後，`ESP：開啟 BLE 配對窗口`、`ESP：設定 Wi-Fi（密碼不顯示）`。
6. 恢復雙主控接線，再用 `BLE：互動主控台` 校時、配置機構、確認實際顯示、preview、resume、save。

獨立 Tasks 另涵蓋 get_status、get_config、set_time、set_display、jog_steps、advance_pages、set_config、save_config、preview_sync、resume、pause、stop、clear_fault、confirm_time。完整操作見 [operation.md](operation.md)。

序列維修台：輸入一行後 Enter；`/quit` 或 Ctrl+C 關閉。燒錄前先關閉其他占用同一 COM 的序列視窗。按 VS Code 停止會終止本工具啟動的子程序；不要中斷正在寫 Flash 的工作。工作不會因開啟資料夾或讀狀態就 ARM／轉動馬達。

連接埠會從目前 USB 裝置辨識；只有一個時使用該埠，多個時要求選擇。個人連接埠／BLE 位址在 `.local/settings.json`，不加入 Git。Wi-Fi 密碼以不顯示的輸入送到 ESP UART，不寫入原始碼／檔案。

## 重新安裝環境

本機已備齊依賴；其他電腦需要 Python 3.12，先執行 `Flip：安裝編譯環境`，再 `Flip：準備桌面操作工具`。工具安裝在本專案 `.tools`，不是全域 Arduino。

`.vscode` 檔案由 `python tools/configure_vscode.py` 產生。C/C++ 索引使用 ESP 建置後的 `.build/esp32_clock/compile_commands.json`；正式建置板型由各 task 的參數決定，不由編輯器當前索引設定決定。
