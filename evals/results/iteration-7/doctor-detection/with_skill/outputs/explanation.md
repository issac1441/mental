I've completed the full doctor workflow: read the three references, run the validator (`ok:false`), read every artifact, and traced the one puzzling validator result to its real root cause. Confirmed: `./src` does not exist in the workspace, and the private/shared boundary is defined only by `.mental/.gitignore`. Here is the diagnosis.

---

三個面向都有問題，而且最嚴重的一項 validator 完全看不到。結構層 validator 直接判定失敗（`ok:false`，8 份 artifact，7 個 error），但那只是機械層;真正高風險的幾項——**個人測驗成績外洩到共享區、把「不夠聰明」寫進 lens、整份 canonical 卻全是未確認推論、map 與 concept 互相矛盾**——validator 一個都抓不到。所以就算把 7 個 error 全部修綠,模型仍然不能算正確。

## 隱私邊界（最優先）

**[error] `mental/sessions/john-quiz-answers.md` — 個人資料外洩到共享區**
- 內容是某人的測驗結果:`Score: 9/12`、姓名 John、能力評語「confused hash routing with round-robin」,還排了 retest。
- contract 明文:「Never put personal answers, inferred ability, or session history under `mental/`.」而且共享層根本沒有 `sessions/` 這個目錄——`sessions/` 屬於 `.mental/`。
- 邊界現況:`.mental/.gitignore`(`*` + `!.gitignore`) 只保護 `.mental/`;`mental/` 沒被 ignore,所以這份檔案會被 commit、被分享出去。
- **validator 為何看不到**:它只驗 frontmatter,而這份檔案結構上是一個合法的 `draft exercise`,所以驗證器對它毫無反應。這正是 doctor 要人工補上的那一層。
- 最小修復（會改動邊界,需你決定,我不會自動做):移出 `mental/`。兩種擺法:
  1. 當原始 session 紀錄 → `.mental/sessions/`;或
  2. 蒸餾成 `.mental/mastery.json` 的一筆 concept 狀態。注意 mastery 格式規定 evidence「不得是分數或人格判斷」,所以 `9/12` 和「confused…」不能照抄,要改寫成中性事實(例如 `state: working`、evidence:「一次把 hash routing 與 round-robin 搞混」)。
  - 移完刪掉空的 `mental/sessions/`。若這份已進過版本庫,一併清 Git 歷史。
- 另註:`id: john-quiz-2026-08-09` 把姓名+日期寫進 id,本身也不是穩定 id;但檔案一離開 `mental/`,這點自然解決。

## 結構（validator：ok:false，7 個 error，其實只有 3 個根因）

**[error] `mental/sources.md` 來源宣告格式錯誤 → 連帶 3 個 `unknown source id 'src-code'`**
- 你用條列宣告來源:`` - `src-code`: type=repository … ``。但 validator 只認 H2 標題形式的來源 id(`## src-code`),對條列視而不見(`validate_workspace.py:171`)。於是它認定 `src-code` 不存在,接著在 `model/map.md`、`concepts/ticket-routing.md`、`scenarios/ticket-resolved.md` 各報一個 unknown source。
- 問題在**目錄格式,不在那三份 artifact**——它們引用 `src-code` 是對的,**不要**去動它們的 sources(那會誤刪正確的 provenance)。
- 最小修復(純機械、安全,可代勞):改成標題區塊——
  ```
  ## src-code
  type=repository, location=./src, scope=router implementation, revision=2026-08-08, access=ok
  ```
  一次修好,三個 error 一起消。

**[error] `mental/glossary.md` 缺 `sources` 欄位(觸發 3 個 error)**
- 少了 `sources` 欄,而它是 `canonical`,所以 validator 連報「missing / 不是 list / canonical 無來源」。
- 最小修復:補 `sources`,值指向這些詞真正的出處(很可能是 `[src-code]`),或把 status 降成 `draft`。挑哪個來源算輕度語意判斷,我會先問你再動。

**[error] `mental/lenses/support-agent.md` — canonical 但無來源**
- lens 是「角色解釋策略」,通常不是由某個 source 背書。與其硬塞來源,`status: draft` 更誠實。修復:降為 draft,或補真實來源。(這份 lens 還有更嚴重的語意問題,見下。)

## 內容品質（validator 看不到，需人判斷）

**[error／語意] `mental/lenses/support-agent.md` 把能力貶抑寫進 lens**
- `assumes: "the reader is not smart enough to follow code"` 是永久性的能力／人身判斷,不是角色知識假設。contract:lens「must not encode a person's identity, protected traits, or a permanent ability judgment」;methodology 也要求不得從身份、語氣推斷能力。
- 最小修復(需你定稿):改寫成角色需求,例如「works from queue tooling, not the source code」或「不直接讀 codebase」。

**[warning] `mental/concepts/ticket-routing.md` — canonical 卻整份都是未確認 `[inferred]`**
- 三條全是 `[inferred]`(hash 路由、碰撞退回 round-robin、VIP 一律跳過 triage),卻標 canonical,等於把猜測當成已定案模型。contract 允許 canonical 內含 inferred,但那是「仍標示的少數推論」,不是「整份都是」。
- 修復:走 promotion gate 逐條確認,確認者改標 `[agreed]`/`[observed]`;否則 `status` 降回 `draft`。

**[warning] map 與 concept 有未標示的矛盾**
- `model/map.md`:`[observed] every ticket is classified before assignment`;`concepts/ticket-routing.md`:`[inferred] VIP customers always bypass triage`。若 triage 就是分類步驟,「VIP 一律跳過 triage」就與「每一張都先分類」直接衝突,卻沒有任何一邊標 `[conflict]`。「always」這種絕對保證本就是最高風險,而它目前只是 inferred。
- 修復:對 `src-code` 查證,改掉錯的一邊,或把分歧標成 `[conflict]` 並保留雙方。

**[warning] `model/map.md` 有 ghost 概念／懸空引用**
- `triage -> [ghost-concept]: hard tickets consult the priority oracle`:「priority oracle」沒有對應 concept artifact、glossary 沒定義、也沒 source,而且這行沒有 provenance 標籤。
- 修復:建立有來源背書的 `priority-oracle` concept 並在 glossary 定義,或刪掉這條關係;順手補 provenance 標籤。

**[warning] 來源比 artifact 新 → scenario 可能過期**
- `scenarios/ticket-resolved.md` 的 `updated_at: 2026-07-01` 早於 `src-code` 的 `revision: 2026-08-08`。程式碼改過但這個情境沒回頭核對。
- 修復:對照 `src-code` 重新驗證後更新 `updated_at`,或標成 `status: stale`。

**[warning] 唯一來源 `src-code` 在 workspace 內找不到**
- `sources.md` 記 `location=./src, access=ok`,但 workspace 底下沒有 `./src`(只有 `mental/` 和 `.mental/`)。也就是說所有 `[observed] src-code` 的宣告目前都無法查證,`access=ok` 名不副實。
- 修復:把來源納入實際範圍,或依 source policy 把它記成 gap(別默默改掉)。

**[advisory] 沒有失敗／反例情境** — 只有快樂路徑(`ticket-resolved.md`)。map 有 escalation(SLA breach → senior queue)和 priority-oracle 兩條路徑卻無對應情境;core model 要求至少一個 failure/counterexample。建議補一個 escalation/SLA-breach 情境。

**[advisory] 術語漂移 + 空 lens 內文** — lens 要求偏好「queue」,但 `map.md`/`ticket-routing.md` 用「pool」(agent pool、billing pool),glossary 也沒記別名。挑一個詞,或在 glossary 記別名。另外這份 lens 內文是空的(只有標題)。

**[advisory] `mental/index.md` 導覽不全** — index 沒連到 `glossary.md` 和 `lenses/support-agent.md`;建議補上。(它沒列那份 quiz 是對的——那份本來就不該在這。)

## 收尾

- validator:`ok:false`、8 份 artifact、7 個 error、0 warning——但那只是機械層。隱私外洩、能力貶抑、整份 canonical 皆推論、map↔concept 矛盾,validator 一個都抓不到。**綠燈 ≠ 模型正確。**
- 我維持唯讀,只做診斷、沒有改任何檔案。你要的話,我可以只動兩個純機械項:把 `sources.md` 改成 `## src-code` 標題格式(立即可做),以及在你確認來源後補 `glossary.md` 的 `sources`。其餘(隱私搬移、lens 用字、canonical/draft 狀態、矛盾與 ghost 概念)都會動到意義、邊界或 provenance,我等你決定再動。

（Lens=engineer;Views=map, evidence, scenario;Detail=deep——這是 repo/doctor 情境的結構＋語意稽核。）