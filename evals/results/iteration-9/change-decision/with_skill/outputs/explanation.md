This is a **decision-mode** comparison. I've traced the actual retry/dead-letter/inventory coupling in the code; every claim below points at a file and line. Here is the analysis.

---

**這兩個選項不是通往同一個目標的兩條路——只有 A 會真的降低死信率，B 不會。** A 把 `MAX_DISPATCH_ATTEMPTS` 由 3 加到 5，等於多給兩次出貨嘗試;只要抖動是「獨立、短暫」的，死信率在指數上會從 p³ 掉到 p⁵。但因為你保留退避基準不變，整個重試視窗仍只有約 3 秒，所以 **A 只對「短於約 3 秒的抖動」有效**,代價是每筆失敗訂單的出貨時間與執行緒占用最壞拉長到約 5 倍。B 完全不改變「有多少訂單被死信」——它換的是每一筆死信的「善後成本」;而且照字面「死信後只是不釋放庫存」，在現有程式碼上不但拿不到你要的好處，還會在 TTL(120 秒) 過後對同一張單重複扣庫存，甚至把一次投遞抖動升級成新訂單缺貨。

## 現況：重試、死信、庫存三者怎麼綁在一起

- 出貨重試在 `dispatch.py:61` 的 `for attempt in range(1, MAX_DISPATCH_ATTEMPTS + 1)`：嘗試 1、2、3。只有 `RetryableError` 會重試（`dispatch.py:67`），`attempt>1` 前先 sleep 退避（`dispatch.py:62-63`）。
- 退避是 `BASE_RETRY_DELAY_MS * 2^(attempt-2) + jitter`（`dispatch.py:44-49`，base=200 見 `config.py:10`）：嘗試 2 等 200ms、嘗試 3 等 400ms（jitter 0–99ms，同一 order_id 每次相同）。所以現在一筆最終失敗的訂單，**死信前總共等 ≈600ms、呼叫 carrier 3 次**。
- 三次用盡 → `DispatchExhausted`（`dispatch.py:70-71`）→ pipeline 接住後補償：`release()` 把庫存還回、寫入 `dead_letters`、回 `dead_lettered` 收據（`pipeline.py:59-67`）。
- 今天成立的關鍵不變量：一張單的庫存最終**不是已出貨、就是已歸還**。`release()` 只有這一個呼叫點（`pipeline.py:62`）;`dead_letters` 只存 `order_id`+`reason`，而且**沒有任何程式碼會讀它**（無重派路徑）;過期庫存沒有背景回收——`expired()` 只在下一次對同一 order_id 呼叫 `reserve()` 時才被評估（`inventory.py:66`）。

## 選項 A：加嘗試次數——真的降率，但只對短抖動

**改動面**：只動 `config.py:7` 一個常數。`dispatch.py` 的迴圈與 `backoff_ms` 已是通式，嘗試 4、5 會自動等 800ms、1600ms;`DispatchExhausted` 訊息讀的是 `config.MAX_DISPATCH_ATTEMPTS`（`dispatch.py:26`），會自己變成「gave up after 5」。完全可逆。

**實際效果**：死信前多兩次取樣。若各次失敗機率獨立為 p，死信率 p³→p⁵（[inferred] 示意：p=0.5 → 12.5%→3.1%;p=0.3 → 2.7%→0.24%）。

**真正的限制（要點）**：A 加的是「取樣數」，不是「時間視窗」。五次仍在約 3 秒內跑完（200+400+800+1600 ≈ 3.0s ＋抖動）。如果 carrier 的抖動持續時間 > 3 秒（例如 10 秒的 brownout），五次全落在同一段壞狀態裡，仍會一起失敗——A 幾乎無效。**抖動的實際時間尺度在這個 repo 看不出來，這是 A 是否有效的關鍵未知數**;若抖動是多秒級，真正該調的槓桿是 `BASE_RETRY_DELAY_MS`（拉長視窗），不是次數。

**代價**：
- 失敗單死信前的等待 ≈600ms → ≈3.0s（＋抖動），最壞約 5 倍;`dispatch` 用同步 `sleep`，呼叫端執行緒被綁住同樣久。抖動風暴時失敗比例最高，正是吞吐掉最多的時候。
- 對「正在不健康」的 carrier，每筆失敗單的 `send()` 由 3 次增為 5 次（≈1.67 倍負載），可能拖慢它復原。
- 庫存面乾淨：多等的約 2.4 秒相對 TTL 120 秒微不足道，且 dispatch 期間不會重新評估 reservation，所以 A **不會**觸發重估價或 TTL 過期。

## 選項 B：死信後保留庫存——不降率，且照字面實作會反效果

**對死信率的影響：零。** 一樣的訂單、一樣的三次用盡、一樣進 DLQ。B 動的是死信「之後的狀態」，不是「有多少死信」。所以若你的目標白紙黑字是「降低死信率」，B 根本不在候選內。

它想換到的是「重派時庫存已保留、不用重搶」。但對照現有程式碼有三個問題：

1. **沒有重派路徑可用**：`dead_letters` 只被寫入、沒人讀（`pipeline.py:63`）;唯一入口 `Pipeline.process()` 一定先走 `reserve()`。所以「重派不用重搶」這個好處，需要一條**目前不存在**、能重用 reservation 的重派路徑才拿得到。

2. **TTL 過後會重複扣庫存（把承諾整個反轉）**：`reserve()` 只有在 reservation **未過期**時才回傳既有的（`inventory.py:66`）;一旦超過 120 秒，它會 `_build()` 重建，而 `_build()` 會**再扣一次**庫存（`inventory.py:112`），同時把 `reprice_required` 設起來（`inventory.py:69`）。人工重派幾乎一定 > 120 秒——於是同一張單**扣兩次**庫存（第一次的保留 B 又不還），而且**悄悄重新計價**：`reprice_required` 沒有任何生產程式碼會讀（grep 只在 docstring 與測試出現），`price()` 永遠照 reservation 當下的快照算（`pipeline.py:56-57`、`pricing.py:48`）。B 的實際效果不是「不用重搶」，而是「重複搶、且金額可能變」。

3. **庫存洩漏 → 新訂單缺貨**：沒有背景回收，保留會一直掛著直到有人手動處理。抖動風暴時死信成批出現，被凍結的庫存持續累積。用測試目錄具體化：`ANVIL` 只有 2 件（`test_pipeline.py:11`），一張 qty=2 的 ANVIL 單死信就把兩件全凍住，**下一張 ANVIL 單**在 `reserve()` 直接 `InsufficientStock`——這是 `FatalError`、不重試（`pipeline.py:51-54`、`inventory.py:102-105`）。一次「可重試的投遞抖動」就此升級成「另一張單的硬失敗」。

**要安全拿到 B 的好處，實際要做的遠不只刪一行**：一條繞過 `reserve()`（或更新 `created_at` 以免觸發重建）的重派入口;DLQ 至少要帶 reservation 參照（現在只有 order_id/reason）;以及把「保留給人工」的庫存獨立記帳、可觀察、可設上限與背景回收，否則洩漏無界。

**契約與測試**：B 會**照設計**弄壞 `test_dead_letter_after_exhausted_retries_releases_stock`（`test_pipeline.py:51-63`，它斷言死信後庫存歸還）。這條測試編碼的是現有不變量;改它是一個「模型決策」，不是修測試。

## 決策清單（Decision Manifest）

- **你在最佳化哪個量**：死信「率」（只有 A）還是每筆死信的「善後成本」（B）?兩者正交、可並存;當成二選一會選錯。
- **A 的前提**：carrier 抖動持續時間是否 < ~3 秒?若否，加次數幾乎無效，該調的是 `BASE_RETRY_DELAY_MS`（或次數與基準一起加，並接受更長延遲）。
- **A 的預算**：能否接受失敗單出貨延遲最壞約 5 倍、抖動風暴時吞吐下降、對不健康 carrier 增加約 1.67 倍呼叫?
- **B 的不變量抉擇**：是否願意把「庫存最終非出即還」改成第三種「保留給人工」狀態?誰擁有、監控、設上限、背景回收這池庫存?
- **B 的前置工程**：是否先建好重派入口 ＋ DLQ 結構 ＋ TTL/`created_at` 處理，再移除 `release()`?否則此改動淨負面。
- **範圍與可逆性**：A 一個常數、可逆;B 觸及 `pipeline.py`、`inventory.py`、DLQ 結構、既有測試與庫存不變量。

以 architect 視角，聚焦關係／因果／情境／證據、deep 密度（此決策的關鍵代價都藏在非顯而易見的耦合上，故未省略）;此 workspace 沒有 mental/ 正規模型，以上是我讀碼推得的 [inferred] 結論、未實際執行，機率模型為示意而非量測。若要我把這份比較存成 `mental/changes/…` 草稿，或針對選定方向起 `$build`，說一聲即可。

**Human Decision: pending**
- 選 A / 選 B / A＋B / 都不選（先量測抖動時間尺度）——見「你在最佳化哪個量」。
- 若傾向 A：只加次數，還是改退避基準?——見「A 的前提／預算」。
- 若傾向 B：是否接受新的庫存不變量，並先補齊重派路徑、DLQ 結構與背景回收，再刪 `release()`?——見「B 的不變量抉擇／前置工程」。