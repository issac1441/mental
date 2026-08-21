I've read the skill, its three references, and the full OrderFlow source. Here's the model, grounded in the code.

---

OrderFlow 是一條四階段的訂單管線：`ingest → reserve → price → dispatch`(`orderflow/pipeline.py:3`)。**庫存保留(reserve)** 會為一筆訂單同時凍結兩樣東西——要扣的庫存、以及要計價的單價快照——而且對同一個 `order_id` 是冪等的:TTL 內重複處理拿回同一筆保留,TTL 過期後才用當前目錄重建並標記 `reprice_required`。**重試** 發生在兩個彼此獨立的層:儲存層對寫入衝突(`VersionConflict`)重試,dispatch 層對可重試的投遞錯誤(`RetryableError`)以指數退避重試。在「乾淨」的意義下,一筆訂單整個失敗有兩種:任一 **`FatalError`**(payload 不合法、SKU 不存在、庫存不足)讓它立刻拿到 `status="failed"` 收據、完全不進 dispatch;或 dispatch 把重試用盡,訂單被 **dead-letter**(釋放庫存、回 `status="dead_lettered"`)。但程式實際上還有兩條「丟例外而不是回收據」的邊界路徑,是最容易誤會的地方——最後一節專門講。

## 三種收據:管線的乾淨模型

`process()` 只會用三種 `status` 回收據(`pipeline.py:29-74`):

- **`dispatched`** — 一路成功,帶 `carrier` 與 `total_cents`。
- **`failed`** — 在 ingest 或 reserve 階段撞到 `FatalError`,立即失敗,dispatch 從沒跑過。
- **`dead_lettered`** — dispatch 重試用盡,庫存已釋放,訂單進 `dead_letters` 佇列。

階段順序是刻意的:pricing 排在 reserve 之後,因為單價快照由保留擁有——過期重建會重新抓當前價,所以報價總額在 dispatch 前是可以合法變動的(`pipeline.py:3-7`)。

## 庫存保留怎麼運作(`inventory.py`)

**冪等**:`reserve` 以 `reservation/{order_id}` 為 key(`inventory.py:62-75`)。若已有保留且未過期,直接回傳原保留、**不再扣庫存**——這就是冪等保證,重送同一筆訂單不會二次扣庫存。

**TTL 與重建**:`RESERVATION_TTL_SECONDS = 120`(`config.py:4`)。`expired()` 以 `time.monotonic()` 判斷 `now - created_at > 120`(`inventory.py:39-41`)。過期後 `reserve` 用當前目錄重建一筆、設 `reprice_required=True`,讓 pricing 知道要重算(test `test_expired_reservation_is_rebuilt_and_flags_reprice`)。

**原子建立**:`_build` 採「先全部驗證、再全部提交」(`inventory.py:93-125`)。第一個迴圈只讀取、檢查每一行(SKU 在不在目錄?庫存夠不夠?),任何一行不過就當場 raise,**這時還沒扣過任何庫存**;第二個迴圈才真正逐行扣庫存並寫回。註解點明用意:*"a failed reservation leaves no partial stock to unwind"*——所以在單筆建立內部,驗證失敗不會留下扣了一半的庫存。

*槓桿*:`RESERVATION_TTL_SECONDS` 調長 → 保留活更久、reprice 更少,但庫存被凍更久。

## 重試:兩個獨立的層

**第一層 — 儲存寫入重試**(`_put_with_retry`, `inventory.py:127-137`)。所有寫入目錄/保留都經過它。撞到 `VersionConflict`(樂觀鎖版本不符,`store.py:29-47`)就重讀最新版本、重試,最多 **`_PUT_ATTEMPTS = 3`** 次;第 3 次還衝突就把 `VersionConflict` 重新丟出。注意這個 `3` 是寫死在 `inventory.py:21` 的模組常數,**不在 `config.py` 裡**,調整時容易漏掉。

**第二層 — dispatch 投遞重試**(`dispatch.py:52-71`)。只重試 `RetryableError`(主要是 `CarrierTimeout`、`CarrierUnavailable`)。最多 **`MAX_DISPATCH_ATTEMPTS = 3`** 次 `send`。第 2 次起先睡 `backoff_ms/1000` 秒:

```
backoff_ms = BASE_RETRY_DELAY_MS * 2^(attempt-2) + jitter
jitter = crc32(order_id) % 100      # 0–99 ms,對同一訂單固定
```

所以序列是:**試 → 等 ~200ms → 試 → 等 ~400ms → 試 → 放棄**(`BASE_RETRY_DELAY_MS = 200`)。3 次都 `RetryableError` → 丟 `DispatchExhausted(last_error)`。

*槓桿*:`MAX_DISPATCH_ATTEMPTS` 調多 → 更多次投遞嘗試;`BASE_RETRY_DELAY_MS` 調大 → 每段等待等比放大;jitter 固定 0–99ms 且對同一 `order_id` 穩定(test `test_backoff_doubles_with_stable_jitter`),作用是讓不同訂單的重試錯開、同一訂單卻可預測。

## 什麼情況下一筆訂單「整個失敗」

乾淨失敗有兩類,兩類都會回收據:

**A. 立即失敗 → `status="failed"`**(`pipeline.py:46-54`)。觸發點是任一 `FatalError`:
- *ingest*(`ingest.py:25-49`):`order_id` 缺或非字串、region 不在 `{domestic, offshore}`、完全沒有 line、line 缺 sku、quantity 不是正整數 → `ValidationError`。
- *reserve*(`inventory.py:98-105`):SKU 不在目錄 → `UnknownSku`;庫存不足 → `InsufficientStock`。

這些都是 `FatalError` 子類(`errors.py:20-29`),被 `process()` 攔下、回 `failed`,且 **dispatch 完全沒跑**(test `test_insufficient_stock_fails_without_retry` 斷言 `calls == []`)。

**B. 投遞用盡 → `status="dead_lettered"`**(`pipeline.py:59-67`)。dispatch 連 3 次都 `RetryableError` → `DispatchExhausted` → `process` 釋放保留(庫存還回目錄)、把訂單記進 `dead_letters`、回 `dead_lettered`,reason 是最後一個錯誤。caller 拿到的是收據、不是例外。

具體走一遍 B:一筆 `ANVIL × 2`、`send` 每次都 `CarrierTimeout`。attempt 1 立刻失敗 → 睡 ~200ms → attempt 2 失敗 → 睡 ~400ms → attempt 3 失敗 → `DispatchExhausted` → 保留釋放,ANVIL 庫存回到 2,收據 `dead_lettered`(test `test_dead_letter_after_exhausted_retries_releases_stock`)。

## 失敗行為的邊界:不是每個失敗都回收據

管線 docstring 把失敗講成乾淨的兩模式,但程式碼還有幾條路徑偏離它。**你可能以為每筆訂單都會落在三種 `status` 之一;實際上不是**——這是理解失敗行為時最關鍵的一點:

**1. reserve 期間的 `VersionConflict` 會逃逸成例外。** `_put_with_retry` 用盡 3 次後重丟 `VersionConflict`(它是 `RetryableError`)。但 `process` 在 reserve 外層只 `except FatalError`(`pipeline.py:51-54`),接不住 `RetryableError` → 這個例外直接往上拋給 caller,不是收據。*前提*:要有並發寫入、或紀錄消失,才會真的連撞 3 次版本衝突(`store.py` 正是為樂觀並發而設計);純單執行緒、無並發時不會發生——現有測試都在這個安全區內,所以測不到這條路徑。

**2. dispatch 期間的「非重試」錯誤會逃逸成例外。** dispatch 只 `except RetryableError`(`dispatch.py:64-68`)。若 `send` 丟出的是 `FatalError` 或任何非 `RetryableError` 例外,它立刻穿過 dispatch;而 `process` 在 dispatch 外層只 `except DispatchExhausted`(`pipeline.py:59-61`),同樣接不住 → 例外拋給 caller。**而且這條路徑不會走到 `release`,保留仍扣著庫存沒還。**

**3. 過期重建會重複扣庫存(會反過來製造 A 類失敗)。** 過期後 `reserve` 走重建分支時直接呼叫 `_build`(又扣一次庫存),卻沒有先把舊保留的量還回目錄——`release` 只在 dead-letter 那條路徑被呼叫(對比 `inventory.py:66-71` 與 `77-91`)。所以同一筆訂單每跨過一次 TTL 被重新處理,該 SKU 的庫存就被再扣一份且永不歸還,累積下去會讓**後續訂單**誤判 `InsufficientStock`。`[inferred]` 我判斷這比較像 bug 而非設計:`_build` 的原子性註解只保證「單次建立內」不留半吊子庫存,並未承諾跨重建守恆;且 expiry 測試只斷言 `reprice` 旗標,沒驗證庫存守恆。

---

這個 workspace 目前沒有 `mental/` canonical model,以上都是我直接讀原始碼推得的。若想把這套失敗語意固化成可維護、可被團隊共用的模型(含這三條邊界),可以用 `$build` 建立;我不會自行寫檔。

**Sources and gaps**
- 管線與收據語意:`orderflow/pipeline.py:1-74`(尤其 `44-74`)。
- 保留機制:`orderflow/inventory.py`(`reserve` 62-75、`_build` 93-125、`_put_with_retry` 127-137、`release` 77-91、`expired` 39-41)。
- 重試與退避:`orderflow/dispatch.py:44-71`;儲存樂觀鎖 `orderflow/store.py:29-47`。
- 失敗分類:`orderflow/errors.py:1-41`;驗證觸發點 `orderflow/ingest.py:25-49`。
- 槓桿常數:`orderflow/config.py`(TTL、`MAX_DISPATCH_ATTEMPTS`、`BASE_RETRY_DELAY_MS`);另有 `_PUT_ATTEMPTS` 在 `inventory.py:21`。
- 行為佐證:`tests/test_pipeline.py`(insufficient-stock、dead-letter、backoff、expiry 四個測試)。
- *Gaps*:邊界 1、2 的例外逃逸在現有測試中無覆蓋(測試都在單執行緒安全區);邊界 3 是否為預期行為未有文件或測試佐證,判斷為 `[inferred]`。

本次以 engineer 視角、著重結構圖 · 機制 · 情境 · 證據,深度 standard(失敗段落加深至 deep)——依你「搞懂失敗行為」的除錯目標推得。想更深、換視角或聚焦某條路徑,直接說,或用 `lens= views= detail=` 調整。