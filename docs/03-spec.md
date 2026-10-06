# 03-spec — 每章的規格

**狀態：凍結 2026-09-15（Phase 1 結束）。** 每章的預期結論都指向一份 probe VERDICT；`pending-decisions.md` 已清空。之後改動 = `docs/decisions.md` 一條決策。Phase 2 起 step 6 對的是這份，不是大綱；大綱只在這裡沒講到的地方補看（D19）。

每章五段：**問題**（這章回答什麼）、**預期結論**（probe 證據下會量到什麼，附證據路徑）、**量什麼**（指向 measurement.md）、**散文的論點**（要寫進 README 的說法，含誠實的天花板）、**與大綱的已知差異**。開頭一張全書的大綱對照表。
## 全書寫作前提（D42；每章作者半必揭露相關者）

程式碼替全書定下、大綱沒有或說反的事。作者寫任何一章前先讀這五條；每章 README 的 *What the chapter must disclose* 把跟該章有關的揭露一次。

1. **資料是 Amazon ESCI（US 子集），不是 Wikipedia。** 全書一個 schema、ESCI 欄位名；大綱 ch2 的 `wiki.sd`、`sample_wiki_dpr.py`、DPR 都不存在。
2. **語料上限 100,000 筆商品**（Q2：4 CPU / 10 GB 帶向量五分鐘內餵完），不是大綱 ch2 說的「可擴到一百萬筆不改設計」。沒測過一百萬，書裡不寫。
3. **ch2、ch3 零 embedder**（每份報告 `deployed_embedders: none declared`），向量 ch4 才進來，且**檢索用的 embedder 只有一個** `BAAI/bge-small-en-v1.5`；ch6 起的重排器（ColBERT、cross-encoder，`docs/pins.md`）是 add-on component，不做檢索（D71）。大綱 ch2 資料列的 "DPR embeddings as needed" 不成立。
4. **ch2 的敘事是「管線通了、搜尋還不行」**：2,000 筆、結果刻意差、沒有相關度數字；ch3 才餵全量、才有 ndcg。大綱 ch2 「已經有一個能用的搜尋」的語氣程式碼撐不住。
5. **cost 數字（秒、docs/s、記憶體）一台機器一次**：Apple M4 Pro、Docker Desktop 4 CPU / 10 GB，讀者重跑不會一樣；quality 數字（ndcg、計數、布林）會一樣。

## 大綱對照表（每章的隱含結論 vs 我們量到的）

一列一個大綱的主張。「量到」欄只寫檔案裡有的數字；「出入」欄三種：**成立** / **成立但形式不同** / **不成立**；沒量到的寫 **待**。這張表就是給作者的「哪裡跟大綱不一樣」，也是 step 6 的對照基準。

| 章 | 大綱的主張（出處） | 我們量到 | 出入 | 證據 |
|---|---|---|---|---|
| 3 | tune a BM25 rank profile with field weights and exact-match boosts（heading 3、skill 1） | 欄位加權全輸（手調 −0.015 real）；k1 0.6 +0.012 real；exact boost +0.012 real；合計 test +0.019 [+0.013, +0.024] | **成立但形式不同**：贏在 BM25 參數與 exact boost，不在 field weights | `probes/q13-lexical-baseline/VERDICT.md` |
| 3 | vocabulary mismatch is the measurable reason semantic retrieval is introduced（principle 3） | test 17,659 相關商品中 1,452（8.2%）與查詢無共同字，647 個 Exact | **成立** | `probes/q14-semantic-effect/reports/test-reach.json` |
| 3 | 100-query evaluation set（What will you build） | 需 ≥700 題才判 0.03；validation 735、test 1,050 | **成立但形式不同**：100 題判不出任何差 | `probes/q01-validation-size/VERDICT.md` |
| 3 | vs Elasticsearch / OpenSearch / Solr / Mongo（heading 5） | — | **待**（不是我們的，作者敘事） | — |
| 4 | semantic retrieval improves over the lexical baseline（隱含，Part 2 milestone） | **執行後（ch04 step 6，2026-09-16）**：ndcg@10 對 tuned test +0.010 [−0.005, +0.025] noise、validation +0.014 noise；recall@100 0.644→0.686（+0.041 real）；只向量找到 2,153 vs 只關鍵字 1,313，淨 +840；盲區 1,452 撈回 14.5% / 19.6% / 26.4% | **成立但形式不同**：贏在 recall 不在 ndcg（D32、D55） | `chapters/ch04/README.md` *For the chapter text*；`chapters/ch04/expected/` |
| 4 | embedding compatibility / choosing encoders（heading 1、skill 2、principle 1） | **執行後**：bge-base 對 small +0.016 [+0.004, +0.027] real、p50 33.1 vs 12.9 ms（2.6×）、feed 3.3×、記憶體 1,739 vs 1,605 MB；prefix 用錯 −0.035 real、**不用 −0.017 real**（Phase 1 說 noise，735 題判出來了） | **成立**（D55：兩種錯都付代價） | `chapters/ch04/README.md` *For the chapter text*；`expected/model-tradeoff.block.md`、`compare-validation-prefixes.block.md` |
| 4 | HNSW recall–latency–memory curves（heading 4、skill 3） | **執行後**：query-time 探索 sweep——agreement@100 0.911（預設）→ 0.990（+500）；p50 12.6 → 14.0 ms，exact 14.9 ms；memory 1,605 MB settled（單一靜態讀數）；build 參數不掃（D5） | **成立但形式不同**：101k 筆上延遲曲線是平的，曲線是 agreement-vs-exploration（D55）；build-parameter × memory 沒量 | `chapters/ch04/README.md` *For the chapter text*；`expected/validation-ann-sweep*.block.md`、`memory.block.md` |
| 4 | precomputed vs in-application embeddings（heading 5） | **執行後**：同 app 兩欄（D5 / D51）；離線 encode 4m 36s（367 docs/s）、向量與 in-app 完全相等（diff 0、cosine 1）；partial-update feed 4m 01s（420 docs/s）vs in-app feed 7m 41s（220 docs/s）；第二欄位 +174 MB settled | **成立** | `chapters/ch04/README.md` *For the chapter text*；`expected/encode*.block.md`、`feed-precomputed.block.md`、`memory-precomputed.block.md` |
| 4 | multi-vector / late interaction（heading 6、7） | **執行後**：只有敘事，`chapters/ch04/models/colbert.md`（無數字）；重排效果留給後章 | **成立但形式不同**：量測移到 ch6 | `chapters/ch04/models/colbert.md` |
| 5 | hybrid improves over either baseline（隱含） | **執行後（ch05 step 6，2026-09-20）**：對 tuned ndcg@10 linear +0.044 / +0.043、rrf +0.030 / +0.027（validation / test，全 real）；對 semantic ndcg@10 +0.030 / +0.032、+0.016 / +0.016 real，recall@100 noise；linear 對 rrf −0.014 / −0.016 real（validation 選 α=0.3）；alpha 0.3–0.6 鏈狀分不出；starved 第一階段 recall@100 掉回關鍵字（−0.037 real）而前十幾乎不動；只有向量找到的 1,617 / 2,158 個只有 36–105 / 24–112 進前十 | **成立但形式不同**：前十贏是 real，但主要是重排兩邊都找到的商品，向量端的網大多仍在前十外（D68：明講、後章接手）；RRF vs 加權以一般概念說（無 held-out set 用 RRF，有的話這份資料上加權贏） | `chapters/ch05/README.md` *For the chapter text*；`chapters/ch05/expected/compare-*`、`*-wider-net.block.md`、`validation-alpha-sweep.block.md` |
| 5 | deduplicated, attributable RAG context（skill 4，三次） | **執行後**：`context.py` 在 `hybrid_rrf` 下的曲線——1 筆 170 B / 52.4% 含 Exact、5 筆 894 B / 76.5%、20 筆 3,700 B / 87.9%；每行帶商品 id；dedup 以 title 為單位（一 id 一 doc，id 層是 no-op），20 筆時全 split 丟 115 條；deploy 警告 `context` summary 讀 disk，故意不 silence | **成立但形式不同**：dedup 的意義在這份語料上是 title 層，作者半揭露 | `chapters/ch05/README.md` *For the chapter text*；`expected/validation-context.block.md`、`context-running-shoes.block.md` |
| 6 | choose rerank counts with NDCG and p95/p99 latency（heading 7） | **執行後（ch06 step 6，2026-09-22）**：取代分數的 second phase 任何 count 都 ≤ floor、≥100 −0.014 real；帶分數（`firstPhase + 0.002 × max_sim`）25 起 0.494、平到 400、無下降（+0.013 real）；cross-encoder 讀 title+bullets 單獨 @10 +0.014 real（0.94 s）、@25 +0.030 real 還在升（2.2 s）；funnel `phased` 0.502 / 0.499 對 first stage +0.021 / +0.010 real；只讀標題的 cross-encoder test noise | **成立但形式不同**：兩個家族各一半——late interaction 的數量看 NDCG 高原（膝點不是峰值，延遲無關）、cross-encoder 的數量看延遲預算（NDCG 還在升）；兩個條件：帶前一階段分數、讀便宜階段沒讀的文字（D78） | `chapters/ch06/README.md` *For the chapter text*；`chapters/ch06/expected/validation-rerank-{colbert,colbert-replace,cross,cross-extended}.block.md`、`compare-*-vs-first-stage.block.md` |
| 7 | a learned model beats the hand-tuned profile（隱含） | **執行後（ch07 step 6，2026-09-24）**：學到的 second phase 對第一階段 validation +0.013 [+0.005, +0.022] real / test +0.004 noise，rerank mode 兩 split real；學到的 funnel `ltr_global` 0.510 / 0.504 對 `phased` +0.008 / +0.004 noise、對第一階段 +0.028 / +0.014 real；形狀在引擎內選（3×100），offline 選的 3×200 在引擎 noise、31×800 −0.079；`cross_logit` 佔 57 % gain（log 修正後） | **成立但形式不同**：對第一階段贏在 validation、對手調 funnel 持平；原因是 log 只有判過的 pair（C3） | `chapters/ch07/README.md` *For the chapter text*；`expected/compare-{validation,test}-vs-{first-stage,phased}.block.md` |
| 8 | filter selectivity, strategy, HNSW exploration affect recall and latency（What will you build） | **執行後（ch08 step 6，2026-09-27，D104）**：post 每階都輸、沒有交叉點；強迫 pre 在 <20% 整題空手（marketplace 99 / nike 557 / small brand 720 題 of 735；filter-first 走法）、exploration 無效；關 filter-first 全找回、2–4× 慢；預設 2% 以下退回 exact 全對且最便宜；5.3% 階夾在兩門檻之間最弱；101k 上 exact 每階 15–17 ms | **成立但形式不同**：不是 pre / post 二選一有交叉點，是 Vespa 兩個門檻決定三條路、中段最弱；ladder 是五個現有欄位條件 | `chapters/ch08/README.md` *For the chapter text*；`expected/validation-filtered-ann-summary-explore{0,500}.block.md` |
| 8 | negative tests detect leakage（principle 3） | **執行後**：5 發明員工 × 3 retriever × 735 題漏出 0；偽造賣家 4,514 / 7,350 / 7,350 全漏（偵測列）；授權 filter 繼承 filter-first 的空手題（marketplace 員工向量查詢 7,350 可能命中回 6,279）；typed query profile 的 mandatory 值缺了就拒絕（D107） | **成立**：安全 ≠ 完整，兩件事各測 | `expected/leakage-validation.block.md`、`authorized-profile-missing-tenant.block.md` |
| 10 | offline evaluation with Recall@K and NDCG（What will you build） | **執行後（ch10 step 6 / 5b，2026-09-28，D111）**：推薦 own recall@10/50/100 0.092 / 0.218 / 0.278，shuffled ≈ 0.001、popular ≈ 0.000–0.005，own 對 shuffled +0.091 / +0.216 / +0.276 real；搜尋：品牌分布 own = baseline = shuffled（兩層 noise）、上界 +0.045 real、顏色 +0.008 real、**脈絡向量 +0.039 real、對別人的向量 +0.075 real** | **成立但形式不同**：Recall@K 給推薦、NDCG 給搜尋，都帶 shuffled / popular 對照；有查詞時有用的是脈絡向量不是品牌分布（Phase 1 押錯訊號） | `chapters/ch10/README.md` *For the chapter text*；`expected/recommend-reporting-*.block.md`、`personalized-report.block.md`、`personalized-lexical-report.block.md` |
| 10 | personalization is as much a freshness problem（principle 3） | **執行後**：ack → GET p50 2.4 ms、→ 推薦前十改變 p50 9.2 ms（50 users，ours）；快照日設計（2026-11-27，`--now` 預設快照、demo 新事件 = 快照 + 1 天）；前後前十示範、過期視窗退回 popular | **成立但形式不同**：可見時間量到、fresh 勝 stale 不量（順序是我們排的） | `expected/freshness.block.md`、`demo-generic-recommend-*.block.md` |
| 10 | offline metrics biased by the logging policy（heading 7、principle 2） | **執行後**：無點擊日誌，反事實限制用例子講；本章的回答是 shuffled / popular 對照（用自己的贏過用別人的、贏過大家同一份）與「查詞級標籤看不到個人化」（上界 +0.045 對 own 0） | **成立但形式不同**：講不量，但對照列是可量的替代 | `chapters/ch10/README.md` *What it cannot do*；`expected/personalized-report.block.md` |
| 11 | oracle vs retrieved quantifies the retrieval share of error（principle 2） | 872 題（D119 補充 1）、成功率半寬 ±0.033；已判斷池 + S ∪ E oracle（D119）；規則 agent 給正解必答對 → 退化（LEDGER F1）；正式來源改 LLM planner 一次紀錄（D117） | **成立但形式不同**（規則 = 天花板，LLM = 量測） | `probes/q11-multihop/VERDICT.md`、ch11 LEDGER F1 |
| 11 | retrieving more can hurt（heading 3、principle 1） | hit@k 對 k 單調（LEDGER F2）→ 單一答案任務 + LLM 紀錄看方向；規則線只報成本面 precision@k / bytes（D117） | **待**（作者跑，D118） | Q11、ch11 LEDGER F2 |
| 11 | human evaluation sets mislead once the caller is a model（heading 7、principle 3） | 統計量 A+B（D28）；agent 題庫 = 任何 trajectory log（D117） | **待**（作者跑，D118） | — |


---

## ch2 Getting Started

**問題**：從零到「查詢回來了」要幾步，每一步 Vespa 在做什麼。

**預期結論**（`bootstrap.sh` 三條路實測、Q6、Q2）
- `./bootstrap.sh ch02` 一條命令：venv、corpus、容器、deploy、feed 2,000 筆 + 三項 smoke check。既有環境 6.4 s、`--fresh` 42.9 s、空 cache 且無 build 的首次執行 14m 18.6 s（corpus 串流 811 s）（cost，M4 Pro / Docker 4 CPU / 10 GB；`chapters/ch02/review/bootstrap-*.txt`，D40 更新）。「有 cache 無 build」那條路的秒數在 step 5 loop-back 補。
- 2,000 筆的結果刻意差：corpus 的前兩千筆是什麼就是什麼——這是 ch3 要餵全量的理由，先埋。證據是一個查詢的結果 block（`expected/query-2000.block.md`，D40），不是散文。

**量什麼**：smoke 三項（quality，布林）；feed 計數 documents / failed / retried（quality）；feed 秒數與 docs/s、bootstrap 秒數（cost，帶 Q4 條件句）。Q6 的報告欄位缺口（batch_size / limit / label）在 step 3 補。

**散文的論點**
1. 容器節點與內容節點：一個收請求、一個存資料並在資料旁邊算——先用「櫃台與倉庫」講，再給名字。
2. schema 是三個決定：能不能搜（index）、能不能篩／排（attribute）、要不要回傳（summary）。每個欄位對一次。
3. feed 與查詢都是 HTTP：讀者看得到 curl。
4. 五個階段（匹配 → 第一階段 → 第二階段 → 全域 → summary）用一次查詢的 trace 指出來，後面每章各放大一個。
5. 誠實：2,000 筆下結果很爛，且說為什麼。

**與大綱的已知差異**：大綱 10,000 筆，我們 2,000（smoke 用）+ ch3 全量；heading 6 的 YQL 範例移到 ch3（需要全量才有意思）；heading 8 圖不是我們的。

## ch3 Text Search Foundations

**問題**：關鍵字搜尋能做到多好，怎麼調，哪裡是它的極限。

**預期結論**（`probes/q13-lexical-baseline/VERDICT.md`、`probes/q01-validation-size/VERDICT.md`）
- 全量 plain feed（101,341 筆）是本章 bootstrap 的事：Phase 1 量到 3m 29s @ 484 docs/s（cost；D40 從 ch2 段搬來，ch3 step 5 以自己的報告取代）。
- 加欄位會變差，而且是 real：手調 3/1/0.5/1 對 title alone −0.015 [−0.024, −0.006]（test）；描述權重 0.5 −0.053；nativeRank 三欄 −0.085。
- 贏在 BM25 自己的參數：k1 0.6 對預設 1.2 +0.012 real（標題短，詞頻很快飽和）。
- 贏在 exact-match boost：+5×queryCompleteness +0.012 real；兩招合起來 +0.016（validation）、**test 0.443 對 title 0.424，+0.019 [+0.013, +0.024] real**。
- 多欄位讓 recall@100 微升（0.626→0.638）但 ndcg@10 降：撒寬、排亂。（recall 無區間，只寫方向）
- 詞彙盲區：test 17,659 個相關商品裡 1,452 個（8.2%）跟查詢沒有一個字相同，647 個是 Exact——關鍵字永遠找不到。（`probes/q14-semantic-effect/reports/test-reach.json`）

**量什麼**：Q1 題數、Q4 latency、Q13 的 profile 表（重量進 `chapters/ch03/expected/`）、詞彙盲區計數。

**散文的論點**
1. BM25 是「這個標題跟你打的字有多對得上」的計分法，三個旋鈕各是什麼（`internal/explain-standard.md` 的三段就是範本）。
2. 直覺「多看幾個欄位」是錯的，數字說為什麼：描述又長又雜，是雜音蓋過訊號。
3. 調 BM25 自己的假設（k1）比加資料有用：先搞清楚你的資料長什麼樣。
4. 使用者打的每個字都重要：全中就加分。
5. 極限：8.2% 的相關商品關鍵字永遠碰不到，其中一半是完全符合的商品。這是下一章存在的理由——但下一章不會全部解決（先埋：向量只撈回其中 14.5%）。

**與大綱的已知差異**：heading 5（跟 ES/OpenSearch/Solr/Mongo 比）不是我們的；heading 2 的 YQL 範例是我們的、要有；「tune a BM25 profile」成立但贏的地方不在 field weights。

## ch4 Semantic Search and the Tensor Model

**問題**：向量檢索加了什麼、沒加什麼；模型怎麼選。

**預期結論**（`probes/q14-semantic-effect/VERDICT.md`）
- 對 tuned BM25，bge-small 的 ndcg@10 **持平**：test +0.009 [−0.005, +0.024]，1,050 題判不出。
- 找回率明顯：recall@100 0.644→0.686；只有向量找到 2,151（12.2%）對只有關鍵字 1,307（7.4%）；多找到 844 個。
- 盲區 1,452 個：向量深度 100 撈回 14.5%、200 撈 19.6%、400 撈 26.5%。大部分還是找不到。
- 模型取捨：bge-base 對 tuned +0.034 [+0.018, +0.050] real、對 small +0.018 real，代價查詢 47.6 vs 16.0 ms（3×）、向量記憶體 2×、feed 約 3×。
- 多 embed 品牌與描述：+0.002 noise，慢 4.6 ms。標題就是訊號（跟 ch3 同一課）。
- 舊 ch4 的 prefix 實驗保留（用錯 prefix −0.030 real、不用 prefix noise）——ch4 step 5 重量。

**量什麼**：Q14 的表（重量進 `chapters/ch04/expected/`）、ANN vs exact（舊 hnsw sweep，Q4 定方法後）、memory（Q5）、bge-base 對照（我們量一次，cost 表）。

**散文的論點**
1. 向量是「意思相近」的搜尋：先舉盲區的例子（查詢跟商品沒有一個字相同，人一看就知道相關）。
2. **它是撒更大的網，不是排得更好**：前十名持平，前一百名多了 844 個相關商品。兩個數字並排，讀者自己看到差別。
3. 為什麼多了卻沒浮上來：撈進來的大多排在 11–100 名——**這是 ch5、ch6 存在的理由**，在這裡埋、不在這裡宣稱。
4. 誠實的天花板：盲區只撈回 14.5%，大部分「意思相近」的商品連向量也排不進前 100。
5. 模型怎麼選：不是選最大的。大模型贏 +0.034，代價 3 倍延遲——給讀者判準（延遲預算、記憶體），不給答案。多 embed 文字沒有用，再一次「訊號在標題」。
6. Prefix 是模型的一部分：用錯 −0.030 real 且沒有任何錯誤訊息。

**與大綱的已知差異**：「precomputed vs in-app」比較用同一個 app 兩個欄位（D5），不手改 schema；heading 6/7（多向量、tensor 通用性）由 ColBERT 段承接（ch6 才量重排效果）；大綱期待的「semantic 贏」在 ndcg 上不成立、在 recall 上成立——這是差異，記錄給作者。

## ch5 Hybrid Search

**問題**：兩種分數合起來，能不能把 ch4 撈進來的東西排上去；分數不同尺度怎麼合。

**預期結論**（待 ch5 step 5；舊 build 跡象：hybrid_linear 對 semantic +0.024 real、對 lexical +0.078 real，但那是對弱 baseline；新 build 的 semantic 對 tuned 是 noise，所以 hybrid 對 tuned 的贏會比舊的小，幅度未知）
- **前提（ch4 埋的）**：廣撒網 + 好排序 → 只有向量找到的相關商品浮進前十。ch5 是第一個驗的地方：hybrid 對 tuned BM25 與對 semantic 的 ndcg@10 差要 real。不 real 就寫「融合沒解決，重排（ch6）才解決」——那也是結論。
- RRF vs 加權融合：權重掃描每列帶區間、不指名贏家（`indistinguishable_from` 保留）；alpha 用 validation 735 選、test 報。
- 「餓死的第一階段」：第一階段拿不到全局的分數分布，normalisation 做不到；hybrid_starved 的 recall@100 幾乎等於純關鍵字（舊 0.645 vs 0.643）——向量搜了卻被丟掉。

**量什麼**：hybrid_rrf / hybrid_linear 對 tuned 與對 semantic 的 ndcg / recall（含區間）；alpha sweep；RAG context 大小曲線（bytes vs 含 Exact 的比例）；p50/p95（cost）。

**散文的論點**
1. 情境：ch4 說向量多撈到 844 個，但前十沒變——它們排在 11–100。這章要把它們往前搬。
2. 分數不能直接加：BM25 是 5–20、cosine 是 0–1；先用一個具體查詢的兩個分數示範「直接加等於只看 BM25」。
3. 兩條路：把排名合起來（RRF，不看分數）或把分數縮到同尺度再加權（linear）。各自在哪種查詢上贏。
4. 權重表每列帶區間，說「0.3 到 0.5 之間分不出來」是結論不是逃避。
5. 餓死的第一階段：為什麼在 Vespa 的第一階段做不到 normalisation（沒有全局資訊），這是 ch6 兩階段存在的另一個理由。
6. RAG context：抓多少筆、多少 bytes、含答案的比例——這是給下游 LLM 的成本曲線。

**與大綱的已知差異**：heading 5 filters 薄（ch8 的）；「deduplicated context」大綱說三次、目前沒做——記錄給作者；hybrid 對 tuned 的贏可能小或 noise，spec 允許「融合不夠、要重排」的結論。

## ch6 Multi-Stage Ranking

**前提**（`probes/q07-rerank/`，舊 build 已量、新 build 待跑）：重排前 100 名 ndcg 升 +0.028 real 後**過 100 反而降**——有最佳重排數，且不是延遲決定的；ColBERT 每筆 8 µs、cross-encoder 每筆 25 ms；query encode 57.8 ms 是主要成本。這是 ch4 前提的第二個驗證點。

*（以下四段 2026-09-20 補寫，D70：Phase 1 凍結時這段只有上面的前提——寫在 Q7 新 build 跑完之前，之後只回填了對照表第 6 列，沒回來補段。證據全部來自 `probes/q07-rerank/VERDICT.md`，新 build、validation 735。）*

**問題**：同一批候選，先用一個便宜的第一階段全部打分，再讓越來越貴的模型只重排越來越少的候選，前十能好多少、每一階段各花多少；「重排多少筆」是由品質還是由延遲決定的；以及 ch5 說「只有向量找到的商品大多還在前十外」（D68 (2)）——重排是不是把它們搬進來的那一步。

**預期結論**（`probes/q07-rerank/VERDICT.md`，新 build；Q7 量在 `semantic` 之上，ch6 量在 ch5 的第一階段之上，形狀可能移動——所以每條都寫兩個分支）
- **ColBERT MaxSim 在 second-phase**：重排 100 對第一階段 +0.022 real（Q7 上 0.4537 → 0.4754，深度 400）；25 到 100 之間 noise（−0.002 [−0.009, +0.003]）；**過 100 下降是 real 但小**——200 對 100 −0.003 [−0.005, −0.000]，400 對 100 −0.005 [−0.009, −0.002]。延遲幾乎不隨數量動（p50 84 → 89 ms 橫跨 0–400），成本在每個查詢的 token 編碼（rerank 0 就付：73 ms 對 15 ms）。**分支**：在 ch5 第一階段之上若峰值仍在 25–100 → 寫「重排數由 NDCG 定、延遲定的是重排器」；若曲線變成單調或峰值移動 → 寫實際形狀，結論的骨架不變（仍是「有一個由品質決定的深度」或「這份資料上沒有」）。
- **cross-encoder 在 global-phase**：每筆約 24 ms；50 筆 +0.025 [+0.013, +0.037] real、p50 1,193 ms；25 筆 +0.020 為 +590 ms；50 筆處還在升。跟 ColBERT 100 筆的 +0.022 是同量級的品質、三個量級的延遲。**分支**：若在 ch5 第一階段之上兩者的贏都縮到 noise → 那就是結論——「融合已經拿走了重排能拿的大半」，並揭露 Q7 在較弱的第一階段之上量到的 real 贏。
- **誰被搬進前十**（ch5 C6 的計數重算）：無 probe 證據，兩個分支都預先允許——重排把只有向量找到的商品搬進前十（數字上升）或沒有（仍是重排兩邊都找到的）。
- **feature log**：不是結論，是交付——ch7 在同一批 judged pair 上學（Q8 用了 49 個 lexical feature；這裡再加 `vector`、`max_sim`）。

**量什麼**：rerank-count 曲線 × 兩種重排器（validation；候選深度 ≥ 最大 rerank 數且印出——Q7 抓到的 artifact）；選定深度在 test 一次；每階段 p50 / p95（p99 只在 jitter <30%，Q4）；per-query vs per-document 成本從 rerank 0 對 N 讀出；wider-net 計數重算；memory（兩個新 attribute 欄位）；一次 full feed（D5）；feature log（train / validation / test，rerank mode）。→ `measurement.md` Q7、Q4、Q5、Q6、Q12 ch6 兩列。

**散文的論點**
1. 情境：ch5 融合把前十排好了，但一百名裡只有向量找到的商品大多沒進前十；而且每個查詢我們只付得起一個便宜的分數給幾千個 match。要更好的判斷就得更貴的模型，貴的模型只能給少數候選——這就是 funnel。
2. 兩種貴法相反：ColBERT 每個查詢貴（編碼一次）、每筆幾乎免費；cross-encoder 每個查詢便宜、每筆 24 ms。所以一個放 second-phase（每個節點、多筆）、一個放 global-phase（合併後、少筆）。
3. 重排多少筆：曲線帶區間；「25 到 100 分不出」是結論；過 100 反而差一點——MaxSim 在像的候選裡判得準、在不像的裡判不準，深候選是雜訊（同 Q13 的邏輯）。深度由 NDCG 定；延遲幾乎不動——所以延遲定的是「用哪一種」，不是「用多少」。
4. Feature normalization 為什麼只能在 global-phase（ch5 已講）；這章把 `lexical`、`vector`、`max_sim`、cross logit 四個尺度並排給讀者看，並在作者半描述「把正規化後的三個 feature 混合」的替代設計（D72：只描述不實作）。
5. Feature log：引擎每筆算了幾十個 feature，人只手調得了三個（ch3 的三輪）——把它們記下來，是 ch7 的起點。
6. 單一節點：global-phase「合併後」在這台機器上示範不出分散式的差別，明講。

**與大綱的已知差異**：dataset / code list 換成 ESCI 與本 repo 工具（D42 前提 1）；heading 7「用 NDCG 和 p95/p99 選 rerank 數」**成立但形式不同**——數量由 NDCG 定、延遲定重排器（對照表第 6 列）；heading 4「distributed result merging」單節點只能敘事；「a low-cost first phase, a feature-rich second phase, an expensive global reranker」在我們的 funnel 裡第二階段是 MaxSim（一個 feature、貴在編碼）不是「feature-rich」——feature-rich 的那一層是 ch7 的學習模型，作者半說明；heading 5 的 feature normalization 做給讀者看（尺度並排）、不做成 funnel 的一層（D72）。

## ch7 Machine-Learned Ranking

**問題**：讓模型從 rank feature 學排序，比人手寫的表達式好多少；模型放在引擎裡跟放在外面差在哪。

**預期結論**（`probes/q08-ltr/VERDICT.md`，新 build）
- 49 個 lexical rank feature + LightGBM lambdarank，對 tuned BM25：validation +0.034 real，**test +0.025 [+0.015, +0.034] real**（offline，同一批 judged 候選）。比舊 build 的 +0.008 大得多：訓練題從 560 變 1,715。
- 模型大小兩邊都有代價：3 葉就 +0.027；31 葉 × 800 輪開始過擬合（0.7396 < 0.7455）。validation 選 15 × 300。
- 這一輪沒有向量 feature——贏的是「人沒手調到的 lexical 結構」；加 `closeness(title_embedding)` 是 step 3 的延伸，預期再加。
- **offline 與引擎不一樣**：同一個 t_tuned，offline 0.711、引擎 rerank 模式 0.684。offline 排的是「所有 judged 商品」，引擎排的是「檢索得到的 judged 商品」。相對比較公平，絕對值不是引擎的。**ch7 一律在引擎內量**（LightGBM 原生 `lightgbm("ranker.json")`，第二階段），offline 只當訓練時的參考。

**量什麼**：in-engine ndcg（rerank 模式 + retrieval 模式各一）對 tuned；模型大小網格（validation）；parity 測試（同一批 pair 的引擎分數 vs offline 分數）；ONNX 匯出後同樣的 parity；外部推論 benchmark（cost）。

**散文的論點**
1. 情境：ch3 手調三個旋鈕花了三輪；引擎其實每筆算了幾百個 feature，人只看得了幾個。
2. 學到什麼：贏 +0.025，比 ch4 換模型（+0.034）小、比 ch6 重排（+0.022）差不多——所以它是「多一層」不是「取代」。
3. 模型不是越大越好：3 葉就贏，31 葉過擬合。用「背答案」講。
4. **offline 分數不等於引擎分數**：兩個任務不同（排全部 vs 排找得到的）。這是 parity 測試存在的理由，也是本章最容易被讀者踩的坑。
5. 模型放哪：引擎內（資料不搬）vs 外部服務（候選要搬出去）——benchmark 的 cost 表帶條件句。
6. 版本、回滾、形狀驗證：模型是檔案，檔案要有版本。

**與大綱的已知差異**：feature log 來自 ch6（大綱寫法）；訓練集就是 build 的 train split（大綱「author-provided split」）；heading 5 分散式評估單機做不到，敘事處理。

*（2026-09-21 補，D79，在 ch6 step 6 之後）*
- **第二個 baseline**：ch6 的 `phased`（first stage → +ColBERT 25 → +cross-encoder 10 讀 title + bullets）ndcg@10 0.502 / 0.499（validation / test）是書裡最強的手寫 profile；ch7 對 tuned BM25 的 +0.025 real（Q8）仍成立，對 `phased` 預期**小贏或持平**：離線 55 feature LTR 對 fused first stage validation +0.015 [+0.005, +0.024] real、test +0.006 [−0.002, +0.013] noise（`internal/checks/ch07-fallback-2026-09-20.json`）。兩個分支都寫得出章：贏 → 「學到的比手調的 funnel 多」；持平 → 「學到的 ≈ 手調 funnel，但不用手調 w_sim / w_cross」。
- **能拉開的 feature 是帶新資訊的**：ch6 feature log 56 欄（49 lexical + `lexical` / `vector` / `max_sim` / `cross_logit`，`cross_logit` 讀 title + bullets 單獨在引擎裡 +0.014 real @10）；ch7 不再是「49 個 lexical feature」的故事。
- **model placement 是實際限制**：含 `cross_logit` 的模型只能放 global-phase @10–25（每題 ≈1 s）；不含的可放 second-phase。這正是 heading「in-engine vs external inference」與大綱 principle 1 的實例。
- **可重現性**：讀者重生 feature log 差千分位（D59）→ LightGBM 樹可能不同 → ch7 出貨訓練好的模型檔，書裡數字用它評，訓練命令照給。

## ch8 Filtering, Constraints, Access Control

**問題**：加上過濾條件後，向量搜尋還找得到嗎；授權怎麼在比對階段強制、怎麼證明沒漏。

**已決**（D23、D24；`probes/q09-tenants/VERDICT.md`）
- selectivity ladder 用現有欄位五階：有描述 ~50%、有品牌 ~95%、無品牌平台自營 5.3%、單一大品牌 nike 0.6%、小品牌 ≈0.01%。不造欄位。
- 報：ANN 找回率 vs 精確搜尋（每階 × pre/post-filter × HNSW 探索參數）、延遲、漏出 = 0 的 negative test。不報過濾後的排序品質（相關商品落在單一 tenant 內的題只有 10–16 題）。
- 租戶 = 品牌 = 賣家，是樓梯最嚴的一階；授權 = 「這個使用者只能看這幾個賣家」，同一個機制。

**預期結論**（待 ch8 step 5；系統性質，任何 query 都能量）：過濾越嚴，post-filter 的 ANN 找回率掉越多，pre-filter 在嚴的那幾階勝出；交叉點落在 ladder 中段；漏出 = 0。**量到（2026-09-27，D104）**：post 每階都輸、沒有交叉點；強迫 pre 在兩成以下整題空手（filter-first 走法在稀疏圖上走不出去，exploration 無效）；嚴階贏的是預設自選的精確算（2% 以下）；夾在兩個門檻（0.2 / 0.02）中間的 5% 階最弱；漏出 = 0 成立，但授權過濾繼承同樣的空手題。

**量什麼**：agreement@100 vs exact 對 ladder 五階 × 兩策略 × 探索參數；p50/p95；negative test 計數。

**散文的論點**
1. 情境先講：「只看 nike 的跑鞋」——十萬件裡只有 600 件是 nike，向量搜尋先找最像的 100 件再過濾，可能一件 nike 都不剩。
2. 樓梯是「過濾條件的性質」：同一個搜尋，條件從「有描述」到「某小品牌」，向量搜尋的反應從沒差到全漏。每階一列。
3. 兩種策略在哪一階換手，數字說。
4. 授權在比對階段做、不在結果端做：漏出測試是 0 或非 0，不是統計。用「這個賣家的員工只看得到自己賣家的商品」講。
5. 誠實的天花板：「過濾後排得好不好」在這個資料上量不出（相關商品在 tenant 內太少），作者半說明。

**與大綱的已知差異**：「data-tenant」欄位 = `tenant_id`，從品牌派生（正規化品牌，無品牌 → `__marketplace__`；D101，2026-09-27 改，原句「= 品牌，不另造」——「不造」指不發明 selectivity 欄位，D23 不變）；heading 4 的 ladder 不是 tenant 欄位而是多個現有欄位；heading 8 的「retrieval correctness」報 ANN vs exact，不報相關度。

## ch10 Recommendation and Personalization

**問題**：把「推薦」與「個人化」當成同一套檢索 + 排序多一個輸入——一個從這個人的判斷推導出來的意圖脈絡 tensor——而不是另一套系統，能拿到什麼。三件事：(一) 不帶查詞、只帶一個 user 向量，最近鄰能不能把這個人接下來會判 Exact 的商品找回來——自己的向量對別人的向量（shuffled）、對大家都一樣的熱門清單（popular）差多少；(二) 帶查詞時，把同一個人的品牌脈絡加進 ch06 的漏斗，前十能好多少、跟拿陌生人的脈絡比差多少；(三) 脈絡用 partial update 改了之後多久查得到，排名怎麼跟著變；以及離線指標在推薦上為什麼只能說到這裡。

**已決**（D25、D30、D109、D110、D111；2026-09-28 重寫，D70 類；2026-09-29 STOP 1 後改預期結論 / 論點 / 差異，D104 類）：user = brand-affinity（同品牌 Exact 商品的查詢歸同一 user，上限 30 題，seed 42；一題可同時屬於多個 user，章要明講）；評估池 = build train ∪ 擴池（D25 B）→ 4,210 個可切 user、7,100 個 held-out 題，每個 user 前半題建 profile、後半題評估，tuning / reporting 兩半 by user；全部在 train split，validation / test 不碰；路二推薦是主線、路一搜尋個人化是第二段；profile 住在 `user` document type（D109 補充）；時間 = 快照日 2026-11-27（D109 補充 3）；**profile 叫「意圖脈絡」，不叫偏好（D111）**。

**量到（2026-09-28 step 5 / 5b，取代 Phase 1 的預期；證據 `chapters/ch10/LEDGER.md` C1–C14）**
- **路二（推薦，主線）**：own recall@10 / @50 / @100 0.092 / 0.218 / 0.278，shuffled ≈ 0.001，popular ≈ 0.000–0.005；own 對 shuffled +0.091 / +0.216 / +0.276 real、對 popular 同量級；扣掉 profile 出現過的品牌仍 0.096 / 0.229 / 0.293（不是品牌記憶）。離線檢查的 0.036 / 0.125 / 0.187 是規劃期預期，不引用。
- **路一（搜尋個人化，第二段）**：**Phase 1 的兩支預期都不成立**——二階品牌分布 own = baseline = shuffled（漏斗 +0.000、純 lexical +0.001，都 noise）；真效果在**脈絡向量**：+0.039 [+0.033, +0.045] real 對 baseline、送別人的向量 −0.036、兩者差 +0.075 [+0.068, +0.082] real；上界（定義 user 的品牌，循環）+0.045 / +0.046 real；顏色 +0.008 [+0.005, +0.011] real（w 0.1；w 0.5 −0.045）；權重太大每項都輸。探索性覆蓋率分組（tuning half）+0.007 / −0.003。Q15 的 +0.008（1,221 題、weighted terms、`bm25_tuned`）沒重現，原因 hypothesis（D106）。
- **freshness**：ack → GET p50 2.4 ms、→ 推薦前十改變 p50 9.2 ms（系統性質，ours）；排名改變只示範。

**量什麼**（不變）：(1) 路二 recall@10 / @50 / @100 over users，own / shuffled / popular / own-cross-brand；(2) 路一 ndcg@10 對 baseline 與對 shuffled，列 baseline / own（品牌）/ shuffled / upper / colour / vector / vector_shuffled，w 在 tuning half 選、reporting half 報一次；同一組 user 在 `bm25_tuned` 上的對照（D110 A）；覆蓋率分組（探索性）；(3) partial update 可見時間；(4) 延遲；(5) memory（product / user 各一）；(6) `user` feed 與事件套用速率；(7) demo：同一個 user 事件前後、過期視窗。

**散文的論點（D111）**
1. **方法先行**：離線評估推薦或個人化，唯一站得住的檢定是「用自己的贏過用別人的」（shuffled）與「贏過大家同一份」（popular）。這是本章對大綱 heading 7 / principle 2 的回答；每張表都帶這兩列。
2. **推薦 = 檢索 + 排序，多一個輸入**：使用者的意圖脈絡（一組連貫的購物意圖曾被哪些商品滿足，表示成一個向量與一個品牌分布 tensor），不是另一套系統。沒有查詞時脈絡本身就是查詢（路二）；有查詞時脈絡解開查詞沒說清楚的部分（路一）。
3. **主線的表**：own / shuffled / popular / own-cross-brand。shuffled 幾乎為零證明找回的是這個人的脈絡；popular 幾乎為零證明「大家同一份」在這種目錄上沒用；cross-brand 證明不是靠牌子。
4. **搜尋個人化**：同一個脈絡向量當 first-phase 加分項 +0.039、送錯人 −0.036——效果取決於「誰的」。品牌分布留作對照：零；上界 +0.045 說明機器不是瓶頸、訊號才是——「脈絡裡出現過的標籤不是脈絡，滿足過它的商品才是」。顏色一列小正結果，帶權重敏感度；w 由 tuning half 選，太大每項都輸（個人化是加一點，不是換掉相關度）。作者半講 Q15 為什麼沒重現（假說）與大綱 "preferences" 一詞為何改成 context。
5. **freshness 獨立成段（D30、D109 補充 3）**：快照日設計先用 D22 標準講清楚（事件序 = 時間、`--now` 預設快照、demo 新事件 = 快照 + k 天），並列一般設計（timestamp + now()、半衰期示意表、同一個時鐘、放幾天再加事件 demo 就變的取捨）；正規化衰減平均與 now 無關，視窗（`--max-age`）是 now 唯一看得到的效果；數字是 ack → 可見的時長（ours）；順序是我們排的。
6. **做不到的**：判斷不是行為，看過不代表喜歡，真的偏好需要選擇行為（這份資料沒有）；離線指標的反事實限制用推薦系統的例子講，無點擊日誌所以講不量；user 是品牌興趣簇不是人，一題可同時餵多個 user；事件是判斷（中性詞彙）。
7. **同一份紀錄兩個時刻**（大綱 heading 1 的主張）：推薦與搜尋用同一個 `user` 文件、同一個 partial update 路徑、同一個 tensor。

**與大綱的已知差異**：dataset / code list 換成 ESCI 與本 repo 工具（D42 前提 1）；「synthetic … sessions … clicks, dwell time, saves, timestamps」→ 從判斷推導的事件、中性詞彙、一個寫死的快照日；Overview 的 "represent **preferences** as tensors" → 我們表示的是意圖脈絡（heading 3 的 "context features"），資料撐不起偏好（D111）；heading 4 recency decay / diversity / exploration 只示範機制；heading 6「serving learned recommendation models」無模型（D109 (4)）；heading 7 講不量，本章的回答是 shuffled / popular 對照；「offline evaluation with Recall@K and NDCG」量得出：recall@K over users（路二）、ndcg@10（路一），都帶對照；「fresh beats stale」不量。

## ch11 Agentic Search

**狀態：D117 改寫（2026-09-29）；D118 起本章只做規劃 + 範例，細節留給作者。**

**問題**：同一套檢索服務一個不會自己糾錯的呼叫者時，什麼變了；錯誤有多少來自檢索而非推理——而且這個問題只對「會被錯證據帶偏的消費者」有意義。

**已決**（D26–D29、D116、D117；`probes/q11-multihop/VERDICT.md`）
- 題集，兩種題型，都從同一組人工判斷推導：**題型 1**（結構化條件）對查詢 q 的頂級商品 p，「找一個不是 brand(p) 的替代品」；oracle = q 的 S 商品且品牌 ≠ brand(p)；hard negatives = q 的 I 商品；**檢索限定在 q 的已判斷池**（`where id in (…)`；未判斷商品不出現，D119）；**oracle = q 的 S ∪ E 商品且品牌 ≠ brand(p)**（別的牌子的 exact 是更好的替代品，D119）；門檻 oracle ≥ 3 → test **872** 題（S ∪ E oracle；無品牌 anchor 42 題先丟、品牌小寫比，D27 / D119 補充 1；S-only 是 669，probe 的 680 是未丟的中間值）。**題型 2**（grouping，D117 (3)）「除 brand(p) 外哪些牌子有替代品、各幾個」；oracle₂ = oracle 集合 group by brand；指標 = grouped 表的品牌覆蓋（recall / precision 對 oracle₂ 的品牌），不是表格全等（D119）。
- **任務答案是一個**：agent 每題交一個商品（題型 2 交一張品牌計數表），成功 = 交的東西 ∈ oracle（題型 2 = 品牌覆蓋 recall 1.0，D119）。
- agent：**harness planner-agnostic**。規則 planner（拆解 = 從 p 抽品牌與品類詞；固定兩跳；確定性）= 工具面示範、基線、讀者重現的數字。LLM planner 走 Vespa 內建 `ai.vespa.llm.clients.OpenAI` + `LLMSearcher` chain（D116；`llm.json_schema` 吐 tool call）= 兩個消費者相關主張的正式來源，數字標「一次紀錄，讀者讀不重跑」。同一套 `tools_schema` 兩個 planner 共用。
- 工具面回**失敗狀態**：`malformed`（YQL 錯）/ `empty`（無條款也零命中）/ `over_constrained`（去掉結構條款有命中）/ `filtered`（去掉租戶條款有命中）；後兩者靠重跑判別。
- 指標：任務成功率，二項區間，872 題半寬 ±0.033 → 只判 ≥ 0.07 的差。規則線另報 hit@k、precision@k、context bytes。
- shift：A 描述（查詢長度、詞數、詞彙重疊分布）+ B 主張（同一組檢索設定在人寫題庫與 agent 題庫上的排名是否一致）；agent 題庫 = 任何 trajectory log；A 的來源含 LLM 紀錄。
- 「多拿反而差」：k=3 vs k=20 極端對比，**只在 LLM 單一答案任務上有內容**；規則線只給成本面（precision@k 降、bytes 升）。

**預期結論**（待 step 5；D118 下由作者跑）：
- oracle 對照：規則 planner 給正解必答對 → 成功率 = 1 是**構造上的天花板，不是發現**；LLM planner 上 oracle > retrieved，預期落差大（一次紀錄）。
- k：規則線 hit@k 隨 k 升、precision@k 降、bytes 升（成本曲線，確定性）；LLM 單一答案 k=20 對 k=3 方向未知、可能 noise。
- 題型 2：規則 planner 用 grouping 一次拿到的品牌表覆蓋 oracle₂ 的品牌（示範機制，不是主張）。
- shift：A 一定成立；B 待量。
- 失敗狀態：題集上各狀態的計數（`over_constrained` 預期最多——品牌條款把小 S 集合濾光）。

**量什麼**：成功率 oracle vs retrieved（兩個 planner）；hit@k / precision@k / bytes 在 k=3、20（規則）；題型 2 品牌覆蓋；失敗狀態計數；shift A 與 B；agent loop 的 p95 延遲（fan-out：一題幾次查詢；規則 planner，ours）。

**散文的論點**
1. 情境先講：人會略過不相關的結果、agent 會把它當事實。同一份結果對兩種呼叫者是不同的產品。
2. Oracle 對照是第一個該做的量測——但它需要一個會被錯證據帶偏的消費者。規則 agent 給正解必答對，那是天花板；落差要用真 LLM 量，本章給一份紀錄。
3. 精確優先：agent 只交一個答案，每多一筆候選都花 context 也多一個干擾項；規則線畫成本曲線，LLM 紀錄看方向。
4. 給 agent 用的查詢面，每個工具對到一個題型：結構化條件（品牌 ≠ x）→ 題型 1；grouping → 題型 2；可選 rank profile 與 query 參數 → 同一題換設定；失敗狀態 → agent 能分支的回應。
5. 權限在檢索時強制（接 ch8）：agent 會忠實地把拿到的東西講出去；`filtered` 狀態就是它看不到的那部分。
6. 誠實的天花板：規則 agent 不是 LLM；LLM 的數字是一次紀錄；680 題只判大差；「多跳」實為兩跳；shift 的 B 若做不出來給做法與範例。
7. 什麼綁語料、什麼不綁：題集推導綁 ESCI 判斷；工具面、trajectory harness、oracle 協定、失敗分類、shift 分析不綁——換語料只換第一項。

**與大綱的已知差異**：可重現的數字來自規則 agent，LLM 數字不可重現（D26、D117）；「多跳」實為兩跳（資料的性質）；heading 9 的 tail latency 只能單機量；dataset 是 ESCI 不是 wiki_dpr（D42 前提 1）；**本章交付的是規劃 + 範例，不是完成的章（D118）**——全題集、數字、散文由作者做。作者選項：C 標籤的真第二跳（LEDGER F7，未 probe）。
