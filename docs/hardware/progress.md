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

