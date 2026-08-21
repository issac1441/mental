I have enough from the code to give a grounded analysis (I'll note the tests were read but not executed, since running them needs approval). Here is the change analysis.

---

`force_redispatch(order_id)` 以目前這個 signature **無法實作**——因為一張單被 dead-letter 的當下，`pipeline.py` 只往佇列塞了 `{"order_id", "reason"}` 兩個欄位 `[observed: pipeline.py:63-65]`,而訂單本體(region、lines)和 reservation 在同一步已經被 `release()` 丟回目錄並刪除 `[observed: inventory.py:77-91]`。也就是說,重新出貨時你手上**沒有任何可以拿去出貨的資料**。所以第一個、也是最關鍵的決策是:重新出貨的輸入從哪裡來。第二個對「不改變失敗語意」威脅最大的點是**重複出貨**:`CarrierTimeout` 是可重試錯誤,但 timeout 不代表 carrier 沒收到貨,而 `send` 沒有 idempotency key,所以「重新出貨」在最常見的 dead-letter 成因上,可能讓同一張單出第二次。

## 你要保住的「現有失敗語意」

先把約束講清楚,才能拿 force_redispatch 去對照。目前 `[observed]`:

- **S1** `FatalError`(`ValidationError` / `UnknownSku` / `InsufficientStock`)→ 立刻 `"failed"`,不重試、不進 dead-letter `[pipeline.py:47-54, errors.py:12-28]`。
- **S2** dispatch 中的 `RetryableError` → 指數退避重試,上限 `MAX_DISPATCH_ATTEMPTS=3`,耗盡才 dead-letter,而 dead-letter = 釋放庫存 + 入佇列 + 回 `"dead_lettered"` `[dispatch.py:61-71, pipeline.py:59-67, config.py:6]`。
- **S3** dispatch 永不靜默丟單:`DispatchExhausted` 一定被 surface `[dispatch.py:22-27, 70-71]`。
- **S4** 只有 `RetryableError` 被重試,錯誤分類的 Fatal/Retryable 切分是操作語意的核心 `[errors.py]`。

force_redispatch 是額外的進入點,對 process() 這條主線是「加法」,所以 S1–S4 對正常流不受影響。真正要盯的是 **force_redispatch 自己會不會違反 S1–S4**。

## 預測:dead-letter 之後,系統剩下什麼

拿測試裡的 `o-4`(ANVIL×2,carrier 一直 timeout)當失敗情境 `[test_pipeline.py:51-63]`:三次 timeout → `DispatchExhausted` → `release("o-4")` 把 2 件庫存還回目錄、**刪掉** `reservation/o-4` → `dead_letters = [{"order_id":"o-4","reason":"carrier down"}]` → 回 `"dead_lettered"`。

事後狀態 `[inferred,基於上述 observed]`:

1. **沒有 reservation**——已被 delete,所以 force_redispatch 一定得**重新 reserve**。
2. **庫存已還原**——重新 reserve 會**再扣一次**庫存;若這期間庫存被別的單吃掉,`_build` 會丟 `InsufficientStock`(Fatal)`[inventory.py:97-105]`。
3. **佇列記錄是有損的**——只有 id 和 reason,湊不回 Order。

## Model delta:force_redispatch 實際上要做什麼

概念上它是「把 S2 的 dispatch 路徑,用一個手動進入點,對某張已 dead-letter 的單重跑一次」。最乾淨的形狀是 `Pipeline.force_redispatch`,**復用** `dispatch()` / `inventory.reserve()` / `release()`,不要複製退避與 dead-letter 邏輯(一旦 fork,S2–S3 就有兩份會漂移)。它必須:找回 Order → 重新 reserve → 走 dispatch → 依結果更新佇列。每一步都藏著一個要你拍板的決策。

## 需要你拍板的決策(Decision Manifest)

1. **出貨輸入來源(擋路的關鍵)。** 佇列記錄有損。選項:(a) 把 dead-letter 記錄加欄位,存下整個 Order(必要時連原始 Quote)——會動到現有 dead-letter 寫入點,但只改**記錄形狀**、不改**行為**,我建議這條;(b) 改成 `force_redispatch(order_id, raw)` 由呼叫端重新帶入——但這就不是你要的 signature;(c) 另建 order archive。**沒有 (a)/(c),`force_redispatch(order_id)` 這個 signature 就是做不出來的。**

2. **重新 reserve 的副作用(重點,直接碰失敗語意)。** 重新 reserve 會:① 用**當前**目錄價重抓 → 總價可能變;② 重扣庫存,不足就 `InsufficientStock`;③ 依當前重量重選 carrier `[dispatch.py:36-41]`。有個陷阱:dead-letter 後 reservation 是被**刪除**、不是過期,所以 force_redispatch 的 reserve() 走「全新建立」分支,**不會**設 `reprice_required` `[observed: inventory.py:63-75]`——等於價格悄悄變了、卻沒有那面平常會亮的旗子。**要決定**:redispatch 允許重新計價(和 TTL 過期重算一致),還是必須沿用原始 Quote(那就得先存下來)?

3. **佇列的變動。** 成功後要不要把該 id 從 `dead_letters` 移除?不移 → 可被重複 redispatch、且重複出貨;移 → 但它是 append-only 的 list,今天沒有移除邏輯,還要處理同一 id 多筆與 O(n) 掃描。再失敗時是留著、換 reason、還是重新入列?**要決定**移除/去重策略。

4. **重複出貨 / idempotency(最硬的一條)。** `send: Callable[[str, Order], None]` 沒有冪等鍵、沒有回執 `[observed: pipeline.py:41]`。timeout 語意上=「沒在時限內回應」,carrier 可能已收貨——其實**現有**的三次重試本身就有 at-least-once 風險,force_redispatch 只是把它放大成一個「人為、刻意」的動作。**要決定**:接受這是 operator 的判斷並在文件/回傳上標明風險(內部服務、手動操作的最小解),還是替 `send` 加冪等契約(較大改動,但才是真正的解)。我不會宣稱 force_redispatch「可以做到不重複出貨」——沒有冪等鍵就是做不到。

5. **force_redispatch 自己的失敗結果與回傳型別。** 建議**復用** `Receipt` 詞彙,不要發明新狀態:成功→`"dispatched"`;再次耗盡→`"dead_lettered"`(**必須再 release 一次並重新入列**,否則庫存洩漏、違反 S2/S3);重新 reserve 撞 Fatal(現在庫存不足)→ `"failed"`?——注意這是把一張單從 `dead_lettered` 推到 `failed` 的**新轉移**,現有模型裡沒有,要明確定義並讓 operator 知道「因為庫存沒了,退不了貨」。

6. **前置守衛(防雙出)。** 對不在佇列、或**已經是 live/dispatched** 的 order_id 呼叫會怎樣?危險點:reserve() 對「還活著的」reservation 是冪等回傳既有的那張 `[observed: inventory.py:64-67]`——若該單此刻正在主線飛,force_redispatch 復用 reserve() 會抓到那張 live reservation 再 dispatch 一次 → 雙出。**要決定**:守衛條件不能只看「是否在 dead-letter 佇列」,還要確認該單不在飛;以及找不到時是 raise 還是 no-op。

7. **併發。** `dead_letters` 是普通 list、send 端無鎖。兩個 force_redispatch、或 force_redispatch 撞上 process(),都可能雙出。建議「**先認領再出貨**」(先把佇列項摘掉再 dispatch),把認領當成互斥點。

## 會被破壞的契約與不變式(逐條對照)

- **不變式「dead-letter 釋放庫存」**:force_redispatch 重新 reserve 後,若再耗盡**必須再 release**,否則庫存洩漏。
- **S3「永不靜默丟單」**:force_redispatch 的每條路徑(含重新 reserve 撞 Fatal)都要有明確 receipt / 佇列去向。
- **S4「只有 Retryable 被重試」**:重新 reserve 的 `InsufficientStock` / `UnknownSku` 是 Fatal,force_redispatch **不可**把它們拉進重試。
- **`Receipt.status` 契約**:沿用 `"dispatched"|"failed"|"dead_lettered"`,不要新增狀態 `[observed: pipeline.py:30-35]`。
- **`send` 契約**:除非你選 4-加冪等,否則維持不動。

## 證據與未驗證項

- 全部結論來自靜態閱讀 `pipeline.py` / `dispatch.py` / `inventory.py` / `errors.py` / `config.py` 與 `tests/test_pipeline.py`。測試我**讀了但未執行**(本 session 執行需核准而被擋),所以「目前為綠燈」是依測試碼推斷、非我實跑觀察。
- 有損 dead-letter 記錄(#1)與「重刪除後 reserve 不設 `reprice_required`」(#2)是這次最容易被忽略的兩個 [observed] 事實,建議在動手前先確認你對它們的取捨。

**Human Decision: pending** — 動手前請就以下拍板(其餘可沿用我標的建議預設):

1. 出貨輸入來源:(a) 擴充 dead-letter 記錄存 Order / (b) 改 signature 帶 raw / (c) 另建 archive。
2. redispatch 是否允許依當前目錄重新計價與重選 carrier(還是必須沿用原始 Quote)。
3. `send` 的重複出貨:接受 operator 風險並標注,還是替 `send` 加冪等契約。
4. force_redispatch 各結局的 `Receipt` 狀態,特別是「重新 reserve 撞 InsufficientStock」該回什麼。
5. 佇列移除/去重策略與併發「先認領再出貨」是否納入本次範圍。

在你拍板前我不會寫任何實作;決定後再交給 Plan Mode,實作完走 `$review`。

（分析視角:engineer;著重關係、機制、情境與證據;深度 standard。此 workspace 沒有 `mental/` 正式模型,以上皆為 inferred 分析——若你想把「失敗語意 S1–S4 + dead-letter 契約」固化成可回歸校驗的模型,再動這個 change 會更安全,建議接著跑 `$build`。）