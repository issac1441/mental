`force_redispatch(order_id)` 會把 `dead_lettered` 從「終點」變成「可再出貨」的狀態——但目前 dead-letter 當下只留下 `{order_id, reason}`,而且已經把 reservation **釋放掉**了(`pipeline.py:62-66`、`inventory.py:77-91`),所以單憑 `order_id`,系統手上沒有任何東西可以「重寄」。真正的風險不在 dispatch 本身,而在它被迫多出來的「重建 Order 與 reservation」這一步:重新 reserve 會重新定價、也可能因庫存被別人吃掉而 **fatal 失敗**,而 `send` 沒有冪等鍵,可能把一張其實已經寄出的單再寄一次。「不改失敗語意」在 **dispatch 這一階段**做得到(原封不動重用 `dispatch()`),但在整個 pipeline 的 lifecycle 層面必然被打破——因為 `dead_lettered` 會多出通往 `dispatched` / `failed` 的新轉移。

## 先確立現況(這個 change 的參照點)

今天一張單只有三個終態,而且都是 `process(raw)` 一次跑完後回傳的(`pipeline.py:44-74`):

- **正常**:parse → reserve(凍結庫存+單價)→ price → `dispatch()` 首次成功 → `Receipt(status="dispatched")`。
- **fatal 失敗**:parse / reserve 丟 `FatalError`(`ValidationError`、`UnknownSku`、`InsufficientStock`)→ 立即 `Receipt(status="failed")`,dispatch 完全沒跑。
- **dead-letter**:dispatch 對 `RetryableError`(`CarrierTimeout`/`CarrierUnavailable`)重試到 `MAX_DISPATCH_ATTEMPTS=3` 用盡(`config.py:6`、`dispatch.py:61-71`)→ 丟 `DispatchExhausted` → pipeline **釋放 reservation**(庫存還回 catalog、reservation record 被 `store.delete` 刪掉)→ 把 `{order_id, reason}` append 進 `dead_letters` → `Receipt(status="dead_lettered", total_cents=None)`。

關鍵事實:[observed] 目前**沒有任何程式碼會去讀 `dead_letters`**(只有測試讀),所以 `dead_lettered` 事實上是終態;而那個 list entry 只有 `order_id` 和 `str(err.last_error)`(`pipeline.py:63-65`)——連原始例外**型別**都丟了,Order 的 region/lines、reservation 的凍結單價全都不在。

## 這個 change 實際改變的模型

一句話:**`dead_lettered` 不再是終態,而 `dead_letters` 從一個「只進不出的記錄」變成一個「可被重放的輸入」。** 而且因為現況把重建所需的狀態都丟掉了,`force_redispatch` 沒辦法是「拿凍結好的單重寄」,只能是「從頭再 reserve→price→dispatch 一次」。這一點會連鎖決定下面每一個 tradeoff。

注意一個你可能會想走、但走不通的捷徑:**不能靠「dead-letter 時不要釋放 reservation」來保住凍結狀態**——那會直接改掉現有失敗語意(違反你的前提),而且會讓 dead-lettered 的單無限期佔住庫存。所以「保留失敗語意」這個前提,反而把你**鎖死**在「redispatch 必須重建」這條路上,價格漂移與新的 fatal 失敗因此不可避免。

## 需要你拍板的決策(這才是「要考慮什麼」)

1. **`dead_lettered` 變非終態,接受嗎?** 這是「不改失敗語意」在 lifecycle 層面唯一躲不掉的破口。dispatch 階段的分類/重試/backoff 可以一字不改;但 pipeline 可觀察的結果會多出 `dead_lettered → dispatched` 和 `dead_lettered → failed` 兩條新轉移。你要的「不改失敗語意」是**窄義**(只指 dispatch 階段的重試規則)還是**廣義**(整條 pipeline 的失敗結果集合)?兩者答案不同。

2. **重建來源怎麼取?**(這決定 `force_redispatch` 到底是什麼)
   - (a) 在 dead-letter 當下**多存** Order / reservation 快照 / 或 raw payload 進 entry。改到 dead-letter 的**資料模型**,但不改失敗語意;`force_redispatch(order_id)` 名副其實。
   - (b) 讓呼叫者**重新提供 raw order**,再走一次 reserve→price→dispatch。那其實是 *reprocess*,不是「用 order_id 重寄」,簽章會誤導。
   
   若不選 (a),`force_redispatch(order_id)` 這個簽章就是空頭支票。

3. **允許改價、允許因庫存不足而 fatal 失敗嗎?** 因為 reservation 已釋放,重 reserve 會:(i) 若庫存已被別的單吃掉 → `InsufficientStock`(fatal)→ 這張單從 `dead_lettered` 變 `failed`,而且是用一個**原本不存在的、非 retryable 的原因**失敗;(ii) 重建時設 `reprice_required=True`、總價可能變。而且 [observed] `pipeline.process` 從不讀 `reprice_required`(`pipeline.py:56` 無條件 `price()`),所以**改價會靜默發生、沒有任何訊號**。redispatch 要不要沿用這個「靜默重新報價」?

4. **重複出貨——最需要防的一項。** [inferred] `send` 是 `Callable[[str, Order], None]`,**沒有冪等鍵**(`dispatch.py:55`);而 dead-letter 最常見的原因 `CarrierTimeout` 本質上模稜兩可(可能其實已寄出)。`force_redispatch` 會在人為判定「永久失敗」之後再送一次(失敗又會再送最多 3 次)。更糟的情境:若同一 `order_id` 後來被 `process()` 重跑並成功,`dead_letters` 的舊 entry 還在,`force_redispatch` 會**再寄一次**。要考慮:redispatch 前是否去重、是否只重寄 `CarrierUnavailable` 而拒絕 timeout 類(但目前 entry 只存字串、型別已丟,分不出來——見決策 2a)、出貨端能否加冪等鍵。**我無法保證這個功能不會重複出貨——以現況它會。**

5. **queue 的語意與所有權。** `dead_letters` 是 append-only 的 `list[dict]`,沒有 `order_id` 索引,可能同一 id 有多筆。`force_redispatch` 要處理:線性掃描、找不到、找到多筆;成功後**要不要移除 entry**(不移除 → 可被無限重放;移除 → 對 queue 的新 mutation、新的 invariant 與 owner)。

6. **新的 public 邊界。** `Pipeline` 現在只有 `process()` 一個入口。`force_redispatch` 是第二個,會在正常 ingest 流程外 mutate `inventory` 與 `dead_letters`。它是 operator-only 工具嗎(目前無 auth/role 概念)?回傳 `Receipt` 嗎、status 如何對應成功/再失敗/再 dead-letter?

(次要:重 reserve 走 optimistic concurrency,同單並發會撞 `VersionConflict`,但 `_put_with_retry` 已處理,`inventory.py:127-137`。)

## 失敗行為的幾條新路徑(驗證時要蓋到)

- redispatch 成功 → `dispatched`,但總價可能與原單不同 → 需測「改價是預期的」。
- redispatch 時 `InsufficientStock` → `failed`(新轉移 `dead_lettered→failed`)。
- carrier 仍掛 → 再次 `DispatchExhausted` → 再 release + 再 append → 回到 `dead_lettered`(可能產生第二筆 entry)。
- 未曾 dead-letter 的 `order_id` / 已成功卻仍在 queue 的 `order_id` → 需明確拒絕或去重,否則就是重複出貨。
- **回歸**:現有 6 個測試(尤其 `test_dead_letter_after_exhausted_retries_releases_stock`)必須原封不動通過,作為「dispatch 階段失敗語意未變」的證據。

---

以 **engineer** lens、**map/mechanism/scenario/evidence** views、**standard** 深度分析。因為 workspace 沒有 `mental/` canonical model,以上皆為**讀碼推得的 `[inferred]` 現況**,未實際執行程式或測試;涉及重複出貨與改價可接受性的判斷已標為 `[inferred]`。若要我把這份分析存成 `mental/changes/force-redispatch.md`(維持 `status: draft`)以便接進 Plan Mode,回我 `record=true`。

**Human Decision: pending** — 需要你先定的選擇:
1. 「不改失敗語意」取窄義(僅 dispatch 階段)還是廣義(整條 lifecycle)?→ 決策 1
2. 重建來源選 (a) dead-letter 多存狀態,還是 (b) 由呼叫者重供 payload(=reprocess)?→ 決策 2
3. redispatch 是否允許改價、是否允許因庫存不足轉 `failed`?→ 決策 3
4. 重複出貨如何防(去重／只重寄 unavailable／出貨端加冪等鍵)?→ 決策 4
5. 成功後是否從 `dead_letters` 移除、以及 `force_redispatch` 的回傳型別與呼叫者權限?→ 決策 5、6

在這些拍板前,我不會動任何程式碼。