# log_comparer 設計規格

版本: 2026-06-30

目的
- 提供在終端中即時互動的 side-by-side 日誌比對工具，使用標準 Python 內建套件 (curses、difflib、re 等)。

功能摘要
- 自動偵測並回應終端大小變更（寬/高）。
- 以 side-by-side 方式顯示左右兩份日誌（left / right）。
- 支援分頁（PageDown / PageUp / 空白鍵翻頁）。
- 兩種檢視模式：
  - view_all_mode (`a`)：顯示所有行。
  - view_diff_mode (`d`, 預設)：僅顯示差異行與上下文行。
- 以數字鍵 `1`~`9` 設定 diff 顯示周圍的上下文行數 (diff_display_lines)。
- 使用 `0` 可將 diff 顯示上下文設定為 0（只顯示差異行）。
- 搜尋並高亮（`s`）：可輸入正則或文字並在左右行中以顏色高亮匹配，與任何檢視模式合併。
- 熱鍵 `q` 退出。

其他快捷鍵
- `↑` / `↓`: 向上/向下捲動一行。
- `l`: 切換顯示行號（左/右各行的原始行號）。
- `h`: 切換將差異列以反白顯示（差異列會用反色或指定顏色顯示）。

資料處理
- 載入檔案時會做標準化：
  - 取代固定格式（時間、pid、tid、thread、16 進位等）為保護性標記，減少非實質差異。
  - 可選忽略大小寫處理（CLI 參數 `--ignore-case`）。
  - 濾掉可配置的 drop patterns（例如 heartbeat、health check、polling）。
- 使用 `difflib.SequenceMatcher` 計算左/右檔案的 opcode，展開為行級的三元組 (marker, left_text, right_text)，marker 表示相等/替換/刪除/插入。

UI 與互動
- 介面區塊
  - 頂部：左右檔名標頭與模式行 (mode、context、快捷鍵提示)。
  - 本體：兩欄顯示（left / right），中間顯示 marker 字元 (" ", "|", "<", ">")。
  - 底部：分頁/行數統計語句與搜尋輸入列（搜尋時在倒數第二行輸入）。

- 配色/高亮
  - 使用 curses color pair (若終端支援)：
    - 高亮匹配使用醒目的前/背景組合（預設為黑字黃底）。
    - 標頭或模式行使用次要色彩（例：青色）。

- 捲動/分頁
  - 每次 PageDown/空白鍵向下翻一頁（頁大小 = 畫面高度 - header/footer）
  - PageUp 向上翻頁
  - top_row 保留當前顯示的可見索引起點；在模式或 context 變更時重置為 0

搜尋行為
- `s` 進入搜尋模式：在畫面倒數第二行顯示 "Search: " 並啟用輸入（回車後套用）。
- 優先以正則搜尋 (使用 re.IGNORECASE)，若輸入為非法正則，退回成文字比對（literal）。
- 搜尋可同時在左/右行上高亮顯示，且不改變過濾/檢視邏輯。

效能與限制
- 使用 difflib 做整體比對；對極大型日誌（數十萬行）可能佔用較多記憶體與 CPU。若需要，可在未來加入 streaming 或基於行索引的增量演算法。
- 目前在載入階段會把整個檔案讀入記憶體，設計上假定日誌檔大小在可接受範圍內。

錯誤處理
- curses 啟動失敗或例外會回退到簡易文字輸出，將 rows 以 marker left | right 列印到 stdout，並顯示例外訊息。

CLI
- 語法: `python3 log_comparer/log_compare.py left.log right.log [--ignore-case]`

擴充建議
- 支援多行 context 自定義預設值與儲存在設定檔中。
- 加入顏色/樣式設定檔 (例如 $HOME/.log_comparerrc)。
- 支援顯示行號與同步滾動（選項）。

測試計畫
- 單元測試：封裝 normalize、keep_line、load_lines 與 build_rows 的函式以進行純函式測試。
- 互動測試：人工在終端中驗證模式切換、分頁、搜尋與大小調整行為。

檔案位置
- 主程式: `log_comparer/log_compare.py`
- 設計文件: `log_comparer/log_comparer_design.md`

作者/維護者
- 寫於 2026-06-30，自動由開發代理生成，請人工確認細節並補充需求。

