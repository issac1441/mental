I traced both options through the actual code (execution was sandbox-blocked, so the Option B numbers below are derived from the code paths with line references you can check, not run empirically). Here's the grounded comparison.

## 先講一個關鍵點:兩個選項不是在解同一個問題

- **A(3→5 次)降的是「死信率」** — 讓更多訂單在 dispatch 階段被救回,不進 dead-letter queue。
- **B(死信後不釋放保留)完全不動死信率** — 它改的是「訂單已經死信之後,人工重派的成本」。

你把它們並列成「兩個降死信率的選項」,但 B 一張訂單都不會少進 dead-letter queue。所以嚴格講,只有 A 在做你標題說的事;B 是在做「死信後的回收」。兩者甚至可以並用。這點先釐清,後面的取捨才成立。

---

## Option A:MAX_DISPATCH_ATTEMPTS 3 → 5

**機制**(`dispatch.py:44-71`, `config.py:7`):backoff 是 `200 * 2^(attempt-2)` + 每單固定 jitter 0–99ms,`sleep` 是同步阻塞。

| | 今天 (3 次) | 改成 5 次 |
|---|---|---|
| 每次重試前等待 | 200、400ms | 200、400、**800、1600**ms |
| 死信前總阻塞 | ≈0.6s | ≈**3.0s** |
| 打給 carrier 的請求數(全失敗單) | 3 | **5 (+67%)** |

**實際效果(誠實版):** 第 4 次落在起點後 ≈1.4s、第 5 次 ≈3.0s。所以 A 只多救回「恢復時間落在 ≈0.8s–3.4s 這個帶狀區間」的抖動事件。

- 若 carrier「抖動」是幾十毫秒的瞬斷 → 3 次(200/400ms backoff)其實已經接住大部分,A 幾乎沒增益。
- 若是幾秒級的 brownout → A 明顯有效。
- 超過 ~3.4s 的斷線 → 5 次照樣死信,只是晚 3 秒才死。

→ **A 的收益完全取決於你 `CarrierTimeout`/`CarrierUnavailable` 事件的「恢復時間分布」。動手前先量這個分布,否則不知道那多兩次落在不落在有效帶。**

**代價:**
1. **每張終將死信的訂單,阻塞從 ~0.6s 變 ~3s(約 5×)**;晚成功的訂單尾延遲最高到 ~3.4s。這是無條件成本。
2. **重試風暴風險。** dispatch 是同步阻塞,而 carrier 抖動是跨訂單相關的(同一家 carrier)。jitter 只有 0–99ms、疊在 800/1600ms 上,幾乎去相關不了 → 同一波訂單會在 ~800ms、~1600ms 兩個新的、幾乎同步的浪頭一起砸向「已經在生病的 carrier」。若 dispatch 在請求路徑上或 worker 數有限,worker 被占住的時間也 ~5×,可能在抖動期堆積 backlog(典型 metastable failure)。這條依你的併發度而定,fixture 是單執行緒看不出來,但這是它模擬的生產形狀。

**安全性:** reservation TTL 是 120s(`config.py:4`),遠大於 3.4s 的重試視窗,所以 A **不會**讓保留在 dispatch 中途過期,無正確性風險。改一個常數、可逆、**不破壞任何測試**。爆炸半徑小。

---

## Option B:死信後不呼叫 `release()`

`release()` 全專案只在死信路徑被呼叫一次(`pipeline.py:62`,定義在 `inventory.py:77`)。B 把它拿掉 → **從此沒有任何東西會回收 reservation。**

它的預期好處(重派不用重搶庫存)只在一個前提下成立:**重派發生在 reservation 的 120s TTL 內**。但人工重派是人,幾分鐘到幾小時後才處理 —— 幾乎必然已過 TTL。而過了 TTL,`reserve()` 走的是「expired → 重建」路徑(`inventory.py:64-71`),它會再呼叫一次 `_build()`,**在沒有先歸還舊保留的情況下,對庫存再扣一次**(`inventory.py:111`)。兩個後果:

**情況一(庫存充足,如 WIDGET×3,起始 10):** 原始扣到 7 → B 不釋放 → 過 TTL 重派再扣到 **4**。**單一訂單(數量 3)吃掉 6 個庫存** + 悄悄設 `reprice_required` 重新抓現價。→ 幽靈庫存流失 + 可能改價。

**情況二(庫存吃緊,如死信測試用的 ANVIL×2 = 全部庫存):** 原始 2→0 → B 不釋放,庫存停在 0 → 過 TTL 重派時 `_build` 檢查 `0 < 2` → 直接丟 **`InsufficientStock`(fatal)**。**人工重派根本無法 reserve,而那 2 個 ANVIL 卡在一個再也不會被釋放的死保留裡,永久 stranded。** 「不用重搶庫存」的初衷,反而變成「重派直接失敗、庫存永久鎖死」。

**額外代價:**
- **直接打破現有測試** `test_dead_letter_after_exhausted_retries_releases_stock`(`tests/test_pipeline.py:51-63`,斷言死信後 stock 回到 2)。
- Orphaned reservations 在 store 裡無限累積,**無回收路徑**(release 是唯一呼叫點)。

→ **B as-written 是淨負:它不降死信率,又在「人工重派」這個它專門要優化的情境下腐蝕庫存正確性。**

---

## 結論

- **要降死信率:只有 A 做得到。** 值得試,但先量抖動的恢復時間分布來確認那多兩次落在有效帶;上線同時盯 carrier 端負載與 pipeline backlog。若擔心重試風暴,更穩的是先只加到 **4 次**(只多 800ms、多 1 次請求),或把 jitter 換成真正的隨機化/加上限,而不是直接跳到 5。
- **B 不要照這樣上。** 它沒解你要解的問題,還在人工時間尺度上雙扣/鎖死庫存。若你要的是 B 的**意圖**(重派免重搶),正確做法是換設計:給死信訂單一個**不受 120s TTL 影響的獨立「待重派保留」狀態**,並讓重派路徑**直接複用那份凍結的 reservation,而不是再走一次 `reserve()`/`_build()`**。這樣才不會踩到 expired-rebuild 的雙扣。

一句話:**A 和 B 並非二選一 —— A 降率、B(重寫後)降回收成本,可以疊。但目前寫法的 B 是個坑。**