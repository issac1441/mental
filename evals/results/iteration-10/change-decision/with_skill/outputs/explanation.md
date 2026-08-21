只有 A 會真的降低死信率；B 完全不動死信率,它想降的是「死信之後重派的成本」——但目前 120 秒的 reservation TTL(`config.py:4`)會讓 B 的「重派免搶庫存」在人工時間尺度上幾乎必然落空,而且反過來引入庫存洩漏。所以若目標照字面是「降死信率」,能達成的只有 A;B 解的是另一個(也合理的)問題「重派人因工程」,但它現在的形式解不了。兩者不互斥,可以 A + 修正版 B 併用。

下面把兩個選項各自實際改到什麼、代價在哪講清楚,都對到程式碼。

## 目前的行為(改動前)

派送在 `dispatch.py:61` 跑 `for attempt in range(1, MAX_DISPATCH_ATTEMPTS + 1)`,即嘗試 1、2、3 次;只有 `RetryableError`(carrier timeout / unavailable)會重試,`FatalError` 立刻放棄。每次重試前 sleep `backoff_ms`(`dispatch.py:44`),排程是 `200 * 2^(attempt-2) + 每單固定 jitter(0–99ms)`:

- 第 2 次前等 200ms、第 3 次前等 400ms → **3 次總退避等待約 0.6 秒**(不含每次真正呼叫 carrier 的耗時)。

正常單:某次 `send` 成功 → 回 `dispatched`。
失敗單(carrier 一直抖):三次都拋 `RetryableError` → `DispatchExhausted` → 進 `pipeline.py:59-67`,**先 `self.inventory.release(...)` 把庫存還回 catalog**,再進死信佇列,回 `dead_lettered`。這條「死信即釋放」被測試 `test_dead_letter_after_exhausted_retries_releases_stock`(`test_pipeline.py:51-63`,斷言 stock 回到 2)釘住,也寫在 `pipeline.py:12-14` 的失敗語意文件裡。

關鍵背景:`release()`(`inventory.py:77-91`)是**唯一**會把庫存還回 catalog 的路徑(grep 全庫只有 `pipeline.py:62` 這一個呼叫點,沒有任何過期回收 sweeper)。reservation 的壽命只由 `RESERVATION_TTL_SECONDS=120` 決定(`inventory.py:39-41`),過期後 `reserve()` 走「重建」分支(`inventory.py:64-71`):`_build` 會**再扣一次** catalog 庫存並標記 `reprice_required`。

## 選項 A:MAX_DISPATCH_ATTEMPTS 3 → 5(退避基準不變)

實際改動:一個常數(`config.py:7`)。退避基準 200ms 不動,所以多出來的第 4、5 次落在 **800ms、1600ms**:

- 總退避等待從約 0.6 秒 → **約 3 秒**(加 jitter 約 3.0–3.4 秒)。

**買到什麼:** 只救得回「在約 3 秒內自己恢復」的抖動。這是 A 唯一的槓桿,也是它的邊界——若你的 carrier 抖動是幾十秒級的斷線,多這兩次(仍在 ~3 秒內)救不回來,得動 `BASE_RETRY_DELAY_MS` 或改成非同步排隊重試,不是加 attempts 能解。(inferred:效果強弱取決於你的抖動時長分布,我沒有這份數據——這是判斷 A 值不值得的最大未知。)另一個限制:`backoff_ms` 的 jitter 是 `crc32(order_id)`,**每單固定、不隨 attempt 變**,所以加次數不會讓同一單的各次重試「錯開」;抖動若讓大量單同時失敗、同時重試,這個 jitter 最多把不同單錯開 99ms。

**代價:**
- 每個撞到抖動的單,最壞多花約 2.4 秒與最多 2 次額外 carrier 呼叫;真正注定失敗的單,現在要拖到約 3 秒才進死信。
- 若派送是同步佔用 worker,事故期間(正是大量單在重試時)每 worker 被佔更久,吞吐下降、佇列更容易堆積。
- reservation 在派送期間被多持有約 2.4 秒,但約 3 秒 ≪ 120 秒 TTL,所以**不會**在派送中途過期觸發重定價(inferred:前提是每次 carrier 呼叫本身不會慢到讓總時長逼近 120 秒;我追了退避排程,沒有量測真實 carrier 呼叫耗時)。

**契約 / 可逆性:** 不破任何測試(退避測試用固定 attempt 2、3,仍成立;死信測試仍會 exhaust 並釋放)。純可逆——改回常數即復原,無資料尾巴。這是低風險、低破壞面的一手。

## 選項 B:死信後「不釋放」保留

實際改動:拿掉 `pipeline.py:62` 的 `release(...)`。**對死信率零影響**——release 發生在 `DispatchExhausted` 之後,純屬事後。

**為什麼「重派免搶庫存」會落空:** `reserve()` 只有在 `not reservation.expired(now)` 時才回舊的那筆(`inventory.py:64-66`)。`expired` 從**原始下訂時的 `created_at`** 起算 120 秒(`inventory.py:39-41, 124`),死信不會重置它。人工發現死信、再手動重派,通常是幾分鐘到幾小時後——早就 > 120 秒。於是重派的 `reserve()` 必走**過期重建**分支:重新扣庫存(正是你想避免的「搶庫存」)、`reprice_required=True`(報價總額可能變動)。B 想省的事,在人工時間尺度上不但沒省到,還多了重定價。

**而且引入庫存洩漏(具體到測試目錄的 catalog):**
- ANVIL stock=2、下訂 qty 2:原 reservation 把 2→0。死信、B 不釋放 → 庫存停在 0、reservation 留著。10 分鐘後重派 → 過期 → `_build` 檢查發現 stock 0 < 2 → 拋 `InsufficientStock`(FatalError),重派直接以 `failed` 收場,那 2 件永遠卡在被丟棄的 reservation 裡。**今天(有 release)重派會看到 stock=2、成功。**
- 若庫存充裕(WIDGET stock=10、qty 1):不報錯,但過期重建會把 catalog 從 9 再扣到 8,那 1 件**永久洩漏**(第一次的扣減沒人還回,沒有 sweeper 回收)。

所以 B 在 <120 秒的自動重派下才如預期;超過 TTL(即真正的「人工重派」)就從「省搶庫存」變成「洩漏庫存 / 重派反而 InsufficientStock 失敗 / 順帶重定價」。

**契約 / 可逆性:** 破壞 `test_dead_letter_after_exhausted_retries_releases_stock`,並改掉 `pipeline.py:12-14`、`dispatch.py:4-6` 文件裡「死信即釋放」的語意——這是契約變更,不是微調。可逆性也較差:上線期間被保留的庫存,事後改回程式碼**不會**追溯釋放,得另外清理。

**B 要真的成立,你其實還得連帶決定(用戶沒提到的隱含選擇):** 把 TTL 拉到覆蓋人工重派 SLA(但這會讓**所有**reservation 都持有數小時,壓縮可用庫存、增加別單的 InsufficientStock);或死信時重置 `created_at`;或加一條「過期也重用、不重建不重定價」的路徑;或加過期回收 sweeper。少了這些,B 淨效果是負的。

## 需要拍板的取捨(Decision Manifest)

- **動的變數:** A 降死信率;B 降「死信後重派成本」但目前形式做不到。目標若是字面的死信率 → A。
- **庫存不變量:** A 維持「釋放的庫存必回 catalog」;B 打破它(不還、可能雙扣、無回收路徑)。
- **契約 / 測試:** A 不破;B 破一支測試 + 改死信語意文件。
- **失敗語意:** A 不變(仍會死信、仍釋放);B 讓重派可能因自身未釋放的保留而 `InsufficientStock`。
- **可逆性:** A 一行常數、無尾巴;B 有資料清理尾巴。
- **TTL 耦合:** B 的成敗完全綁在 `RESERVATION_TTL_SECONDS` 與重派延遲的相對大小上;A 只要總時長 ≪ 120 秒就與 TTL 無交互。
- **可併用:** A 與(修正後的)B 不互斥。

---

以上以 engineer lens、偏 mechanism/scenario/evidence、detail 介於 standard 與 deep(依你要「實際效果與代價」的決策比較選定)。**這份分析是 inferred 綜合**:workspace 沒有 canonical mental/ 模型,結論靠直接讀碼推得;我追了程式路徑,但沒有實跑派送、沒有你的抖動時長分布(A 效益的最大未知),也假設人工重派 >120 秒(B 落空的前提)。若要把這份比較存成 change brief(draft)可加 `record=true`;鑑於 reservation 生命週期與死信契約(TTL vs release vs 過期重建洩漏)相當微妙且無 canonical 模型,建議之後用 `$build` 把「庫存保留生命週期 + 死信契約」固化成模型再改。

**Human Decision: pending** — 待定的具體選擇:
1. 目標到底是「降死信率」還是「降死信後重派成本」?據此選 A / B / 兩者(見「動的變數」)。
2. 若選 A:你能接受的重試視窗是多久(抖動多久內要救回)?這決定只動 attempts 夠不夠,或要不要一起動 `BASE_RETRY_DELAY_MS`(見選項 A 邊界)。
3. 若選 B:必須連帶決定 reservation 生命週期(拉高 TTL?死信重置 `created_at`?加不重建的重用路徑?加過期 sweeper?),否則 B 淨為庫存洩漏(見 B 的隱含選擇)。
4. 是否接受改/刪 `test_dead_letter_after_exhausted_retries_releases_stock` 並更新死信語意文件(僅 B)。

在你拍板前我不會動任何程式碼。