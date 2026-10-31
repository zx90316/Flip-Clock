# 實物進度

- 正式專案：D:\Project\Flip-Clock。
- 2026-11-01：使用者回覆只有單板接 USB，其他接線為零。
- 已辨識 USB-SERIAL CH340 (COM3)，已燒錄並校驗 Uno 韌體 0.2.0。
- 已透過 UART STATUS 核對 BOOT_UNARMED、armed=false、coil_mask=0；未發送運動命令。
- 實機診斷發現 .init3 初始化被 LTO 淘汰，已加入 used、重新燒錄，並由符號表及 reset_cause=0 確認初始化生效。Optiboot 可能清除 MCUSR，所以 0 代表未取得硬體重置原因，不宣稱已識別 reset 類型。
- 使用者確認馬達為 5V，希望先由 Uno 5V 做單顆試轉。
- 已準備有限步數 UART bench；2026-11-01 01:09 已接 ULN2003＋單顆 5V 馬達，以 Uno USB 5V 空載試轉 256 半步／50 steps/s；使用者回報馬達有轉動（Uno 未重開機、USB 未掉線）。僅證明單顆空載基本相序與供電可用，不代表整機負載或外部電源驗證。
- ESP 燒錄、外部供電、電平轉換、RTC 電池、雙板 I2C 及 BLE 真機驗收尚待進行。

下一步：依 bringup.md 第 2 段，USB 拔除時接好 Uno／ULN2003／單顆 5V 馬達，再回報接線狀態。

- 2026-11-01：ESP32-CAM（ESP32-D0WD-V3）經 Uno CH340 UART＋BSS138 燒錄成功，四個映像均校驗通過。排錯重點：ESP32-CAM 排針上有一個標 GND 的腳實測不是 GND，導致 IO0 無法進下載模式；換接正確的 GND 後才進入 boot:0x3。UART 診斷指令為小寫 `status`。新韌體讀回 LINK_WAIT，i2c_error_count 偏高屬預期（I2C／RTC／Uno 尚未連接）。
- 下一步：拆除燒錄接線、恢復雙主控 I2C 接線（見 bringup.md 第 4 段）。
- 2026-11-01：OTA 實測成功（雙 OTA 分區）。RTC 模組實為 PCF8563（HW-689），韌體已支援。Uno 與 ESP 經 HW-209 完成 I²C 運轉接線，網頁顯示 Uno 已連線，RTC 校時成功。
- 2026-11-01（夜）：Uno 已更新為 0.3.0（速度上限 1000、加速度上限 4000）並由 USB 校驗。**ESP 0.3.0 新版（Wi-Fi 設定、高速歸零）已編譯，尚未燒入**，待網頁 OTA。馬達驅動板、RTC 電池（先量電池座正極電壓確認沒有充電支路）尚未接。
