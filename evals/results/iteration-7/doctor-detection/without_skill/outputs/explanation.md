體檢完成。結構層跑了驗證腳本、語意層與隱私邊界我逐項對照了 `artifact-contract.md` 與 `methodology.md`，並確認了 git 追蹤狀態。**結論：這個 workspace 目前不適合 commit** — 有 2 個嚴重的隱私／人格判斷問題、3 類結構錯誤（驗證器直接擋下）、4 個內容品質風險。

以下按你問的三個面向分層，每項附檔案路徑與**最小安全修法**。我維持唯讀診斷，沒有動任何檔案。

---

## 🔴 隱私邊界（最嚴重，先看這個）

**1. 具名個人的測驗成績外洩到版控樹 — 已被 git 追蹤，會進 commit 歷史**
`mental/sessions/john-quiz-answers.md`
- 內容是具名個資：`Score: 9/12… John… confused hash routing with round-robin on Q7 and Q9. Retest scheduled.` — 這是個人答題結果 + 能力判斷 + 重考安排。
- 我用 `git ls-files` 確認它**已被追蹤**（不是 untracked），而 `.mental/.gitignore` 管不到 `mental/` 底下。也就是說它會被 commit，**即使日後刪除也已留在 git 歷史裡**。
- 直接違反合約：*"Never put personal answers, inferred ability, or session history under `mental/`."* 共享層 layout 根本沒有 `sessions/` 這個目錄 — session 應在 `.mental/sessions/`（被 ignore）。
- 附帶：`kind: exercise` 名實不符，內容是 session/測驗結果，不是 exercise 教材。
- **最小安全修法**：把檔案移到 `.mental/sessions/`；若已經 commit 過，需要一併清理歷史。人格化的評語（"answered correctly / confused…"）建議濃縮成 `mastery.json` 允許的中性 evidence 註記，不留逐題轉錄。

**2. Lens 把「能力貶抑」寫成假設，而非角色需求**
`mental/lenses/support-agent.md` → `assumes: - the reader is not smart enough to follow code`
- 合約明文禁止 lens 編碼 *"a person's identity, protected traits, or a permanent ability judgment"*；lens 模板的 Boundaries 也寫 *"Do not use this lens as a permanent identity or ability label."* 這句是對讀者永久能力的貶低判斷，正是被禁的形態。
- **最小安全修法**：改寫成角色需求，例如 `assumes: - the reader works from queue behaviour, not the implementation`（描述「不看程式碼是這個角色的工作方式」，而非「不夠聰明看不懂」）。這牽涉語意，建議你確認措辭我再改。

---

## 🔴 結構（驗證器擋下 7 個 error，歸為 3 個根因）

**3. `sources.md` 用錯格式 → 連鎖 3 個 `unknown source id 'src-code'`**
`mental/sources.md`
- 現在用清單項目宣告 source：`` - `src-code`: type=repository… ``。但 catalog 規定每個 source 要用 `## <source-id>` 標題（模板與 `tests/fixtures/repository/mental/sources.md` 都是這個格式）。驗證器只認 `## src-code` 標題，所以 `src-code` 被判為未定義。
- 連帶讓 `concepts/ticket-routing.md`、`model/map.md`、`scenarios/ticket-resolved.md` 三個引用它的 artifact 全部報 `unknown source id`。
- **最小安全修法**（純機械，可安全自動修）：把那行改寫成
  ```
  ## src-code
  - Type: repository
  - Location: ./src
  - Scope: router implementation
  - Revision or retrieved date: 2026-08-08
  - Access status: available
  ```

**4. `glossary.md` 缺 required 欄位 `sources`**
`mental/glossary.md` — 完全沒有 `sources:` 欄位，且 canonical artifact 需有非空 sources（模板的 glossary 有 `sources`）。
- **最小安全修法**：補上 `sources:` list。指向哪個 source（是否 `src-code`）牽涉來源判斷，需你決定。

**5. `lenses/support-agent.md` 是 `canonical` 但 `sources: []`**
- 驗證器報 `canonical artifact has no sources`。
- **最小安全修法**：補 source，或把 `status` 降回 `draft`（lens 常是人工撰寫、尚未定稿，降 draft 通常更合適）。需你選一個方向。

---

## 🟡 內容品質（語意風險，驗證器測不出）

**6. Canonical 卻全是未確認推論**
`mental/concepts/ticket-routing.md` — `status: canonical`，但三條主張全部 `[inferred]`，還包含強主張 `VIP customers always bypass triage`。這代表 draft promotion gate 被跳過（canonical 應含 `[observed]/[agreed]`，未確認推論不該以 canonical 定稿）。→ 要嘛逐條確認改標 `[agreed]/[observed]`，要嘛 `status` 降回 `draft`。

**7. 來源版本比 artifact 新（可能 stale）**
`scenarios/ticket-resolved.md` `updated_at: 2026-07-01`，但 `src-code` revision 是 `2026-08-08` — 場景比程式碼舊超過一個月，可能已對不上現行實作。→ 重新對照程式碼後更新 `updated_at`，或標 `status: stale`。

**8. 關係圖缺代表性失敗場景**
`model/map.md` 描述了 intake→triage→escalation 與 priority oracle，但唯一場景 `ticket-resolved.md` 只走成功的 billing 路徑。方法論要求「至少一個 failure/counterexample」。→ 補一個 escalation / SLA breach 或 hash collision 的失敗場景。

**9. Ghost-concept：懸空的關係目標**
`model/map.md` 有 `triage -> [ghost-concept]: hard tickets consult the priority oracle`，但沒有對應的 concept artifact（priority oracle 從未定義）。→ 要嘛補一個 concept，要嘛移除該關係。

**Advisory**：`glossary.md` 兩條定義無 provenance 標籤（definitional，低風險，可留待補）。

---

## ✅ 沒問題的部分
- `.mental/.gitignore` 正確（`*` + `!.gitignore`），私有層框架本身是對的 — 只是內容放錯樹。
- `model/map.md` 的 provenance 用得好（`[observed] src-code`、`[agreed]` 都有附依據）。
- 無 broken links、無 orphan concept 警告（`ticket-routing` 有被 index 引用）。

---

## 我可以接著做的
若你要修，建議順序：**先處理隱私（1）→ 再結構 error（3–5）→ 最後內容品質（6–9）**。其中：
- **可直接機械修、不改語意**：#3（sources.md 格式）。
- **需要你先拍板才動**（涉及語意／provenance／人格措辭）：#1 措辭與歷史清理、#2 lens 改寫、#4/#5 的 source 指向、#6 的 canonical/draft 決定。

要我從哪一項開始？或先把 #3 這個純格式修掉、其餘列成待辦？