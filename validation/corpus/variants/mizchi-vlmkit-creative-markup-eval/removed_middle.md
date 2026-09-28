# 設計: 参照なし(創造的)マークアップの評価シナリオ

日付: 2026-07-30 / ステータス: Layer A 実装済み(同日)、Layer B / S14a は未着手

## 実装状況(2026-07-30)

実装順序 1〜4 を出荷:
- `packages/vlmkit-markup/src/inspect/integrity-check.ts` — Layer A 全プローブ
  (A1-A9)。A3 の stylesheet/script/font は **wire 検知**(requestfailed +
  非 OK response)に変更 — Chromium は 404 の `<link>` にも空の
  CSSStyleSheet を付けるため `link.sheet != null` では死んだ stylesheet を
  見分けられない(実装中に実測)。A2 は DOM 側 textBlocks を判定に含める
  (テキストのみのページはグリフが minArea 未満で components 0 になるため、
  pixel 単独では偽 degenerate になる)。
- CLI `check integrity` + MCP `check_integrity`(8 本目)。
- S14b mutation バッテリー: **9/9 クラス検知**(回帰テストとして常設)。
- S14c 偽陽性監査(自作分): hero オーバーレイ / ellipsis / 位置決め
  アンカー / aria-hidden 装飾 → verdict clean、全候補が `exempted` に記録。
- 初回 dogfood: S8 edit fixture(1280 で DONE 検証済み)が 375 で 67px の
  実在オーバーフローを持つことを検出(`div.plans` 帰属) — 参照ありゲートの
  死角(target が無い幅)をそのまま裏付ける結果。
- S14c 外部 dogfood 実施済み(同日): 5 実ページで免除ルール 4 クラスを
  修正(image replacement / sr-only が最重要)。
  `docs/reports/2026-07-30-integrity-external-dogfood.md`。
- S14a 実走済み(同日): Haiku DONE(1 修正ラウンド)、検証フェーズで
  gate 沈黙欠陥 0。`docs/reports/2026-07-28-verifier-tooling-and-s6.md`
  追記13。派生課題: 高密度ブリーフの負荷版、check copy の状態別検証。
- Layer B ワークシート: **凍結(需要ゲート、2026-07-30)** — 決定論降格で
  残余 2 軸まで縮小し、gate 沈黙欠陥の実観測が着手条件(下記 Layer B 節)。

### Layer A 拡張(2026-07-30 第 2 陣) — B 軸からの決定論降格

S14 の判別語彙(部分切れ vs 完全隠し / positioned+z-index は意図 /
近接=事故)を使い、Layer B に残していた判断 4 つを決定論化:

- **A10 `container-protrusion`** — overflow visible のまま painted parent
  (枠線・背景を持つ box)から in-flow の子がはみ出す(どのゲートも
  沈黙していた最頻クラス)。positioned な子(badge)と負の水平マージン
  (full-bleed breakout)はツール側 exempt。
- **A11 `invisible-text` / `low-contrast-text`** — 単色背景のみ対象に
  αブレンド + 累積 opacity 込みで WCAG 比を実測(<1.15 fail、<3 warn)。
  背景画像/グラデーションはページ単位の集約 exempt 行で明示スキップ
  (Layer B 領域のまま)。disabled / text-shadow は exempt。
  **image-replacement 等で視覚的に隠れたテキスト(自要素または祖先の
  クリップ外)はスキップ** — zen garden dogfood で発見した偽陽性クラス
  (閉じたドロップダウン内の白文字を invisible と誤報)への対処。
- **A12 `near-misalignment`(warn)** — 同型兄弟 3+ が left/center/right/top
  のいずれかで正確に揃っているとき、2-8px だけ外れた要素を警告。
  「0px も 9px 以上も正常、帯域内だけ事故」という near-miss 原理の整列版。
  他軸で正確に揃う要素(左揃えリスト内の中央揃え)は意図としてスキップ。
- **`check layout --contract`(別ゲート、`inspect/layout-contract.ts`)** —
  ブリーフの構造要求(幅±許容、1 行あたりセル数、full-width 折りたたみ、
  積み順、可視性、個数)を宣言 JSON で照合。S14a-stress の検証者が手書き
  していた DOM 計測の正式化。MCP `check_layout`(9 本目)。

dogfood(zen garden / danluu / HN / 自作 fixture 全て)で偽陽性 0 に調整
済み。attempt-stress の #changelog が low-contrast warn(2.56:1)として
検出されたのは真の陽性(Haiku が書いた実際に薄すぎる文字)。

## 背景と目的

これまでの評価軸(S1-S13)はすべて **お手本あり** — target 画像・reference
HTML・copy manifest のいずれかが正解として存在し、gate は「一致したか」を
判定してきた。しかし実運用では「ブリーフだけ渡してゼロからマークアップさせる」
創造的タスクが頻出する。このとき正解画像は存在しないが、**それでも明確に
評価できる項目がある**:

- レイアウト崩れ(テキスト衝突、はみ出し、潰れたコンテナ、水平スクロール)
- JS エラーによる UI 構築の失敗(白画面、部品欠落)
- リソース切れ(壊れた画像、読めなかった CSS)
- スタイル未適用(UA デフォルトのままの「素 HTML」)

これらは「デザインの良し悪し」ではなく **欠陥(defect)** であり、
(a) 決定論のレイアウト検査と (b) VLM の視覚判断の 2 層で検知できる。
本設計はその 2 層の分担・新ゲート `check integrity`・検証シナリオ S14 を定める。

## 設計原則(このリポジトリの実測から持ち込むもの)

1. **VLM に数値を言わせない**。座標・寸法・重なり量・比率はすべて
   決定論(pixel + DOM 計測)。VLM は「読む・判断する」だけ
   (diff-region A/B の net-negative 実測より)。
2. **降格・免除はツールの判定**。意図的オーバーレイ(hero テキスト等)の
   免除はツール側ルールとして JSON に明示し、エージェントの合理化余地を
   残さない(合理化 7 例の再発防止)。
3. **ピクセル作者の自己レビューは無効**(same-eyes)。Layer B の VLM 判定は
   マークアップしたエージェントと別の読み手であることを必須とする。
4. **VLM の主張は決定論で反証(refutation)する**。vlm-region-diff の
   refutation gate(2026-06-08)と同じ形: VLM が「崩れている」と言った領域を
   Layer A の計測でクロスチェックし、裏が取れない行は低信頼に降格する。

## 欠陥タクソノミー(参照なしで判定可能なもの)

### Layer A — 決定論(hard、単体で FAIL 判定可)

### Layer B — VLM 視覚判定(soft、advisory / 反証付き)

### 対象外(このゲートで判定しないもの)

## 新ゲート: `check integrity`

## 検証シナリオ: S14 バッテリー

### S14b — mutation バッテリー(最優先: 検知率の証明)

clean なページ(既存 fixture の DONE 到達 attempt を流用)に、
タクソノミー各クラスの欠陥を 1 つずつ注入し、gate が**そのクラスとして**
検知することを確認する。CSS-challenge と同じ検知率表の方法論。

| 注入 | 期待検知 |
|---|---|
| `<script>throw new Error(...)</script>` を head に(構築前 fatal) | A1 fatal |
| 初期化 JS の関数名を 1 字壊す(部品が出ない) | A1 + A2 or A6 |
| `img src` を 404 に | A3 |
| 2 つの absolute テキストを同座標に | A4 |
| コンテナ width を 40px に(テキスト切れ) | A5 |
| flex 親の height:0 + overflow:hidden | A6 |
| 固定 width 1500px の要素を挿入 | A7 (page-overflow-x) |
| stylesheet の href を 404 に | A8 (+A3) |
| 375px でだけ潰れる min-width 指定 | A9 経由で該当クラス |

**合格基準: 9/9 クラス検知**(検知率 100% が目標 — 注入は自明ケースなので、
落ちるならプローブの設計不良)。誤クラス検知(A6 を A2 と報告等)は
帰属の質の問題として別カウント。

### S14c — 偽陽性監査(免除ルールの証明)

意図的パターンだけで構成した clean ページ群に gate を当て、
**findings 0 / exempted に正しく載る**ことを確認:

- hero 画像上のテキストオーバーレイ(A4 免除)
- ドロップダウン / バッジの重なり(A4 免除)
- 横スクロールカルーセル(A7 の nested-scroll 免除条件)
- `text-overflow: ellipsis` の意図的切り詰め(A5 免除)
- 装飾用 `aria-hidden` の重ね文字(A4 免除)

さらに外部ページ(APG dogfood と同様、curl ミラー経由)1-2 本で
実世界の偽陽性を拾う。**APG の教訓**: 自作 fixture だけでは
免除ルールの穴は見つからない — 外部 dogfood を S14c の必須手順にする。

### S14a — 創造的マークアップ実走(gate の実効性)

1. ブリーフのみ(target 画像なし)を書く。**ブリーフに全 copy を引用**し、
   ブリーフ自体が copy manifest を兼ねる形式(hidden-state copy carrier の
   既存規約を流用)。
2. Haiku にゼロからマークアップさせ、`check integrity` をループ駆動
   (DONE 条件 = verdict clean × 3 viewports + `check copy` manifest 一致)。
3. 行き詰まったら Sonnet へ kickback 逐語ハンドオフ(S9 と同じ運転)。
4. 検証フェーズ: 別の読み手が Layer B ワークシート + copy diff で監査
   (same-eyes 排除)。
5. 計測: rounds / 検知が修正を正しく誘導したか(帰属セレクタと実修正の
   対応)/ gate が沈黙したのに検証フェーズで見つかった欠陥(= gate の穴)。

### 指標(knowledge.md 台帳へ)

- クラス別検知率(S14b、9 クラス)
- 偽陽性率(S14c、意図的パターン n 個 + 外部ページ)
- S14a: rounds-to-clean、kickback 追従率、gate 沈黙欠陥数
- Layer B 反証率(VLM 主張のうち決定論で裏が取れた割合 — 低すぎるなら
  B は納品物から外し、A 単独運用に切り替える判断材料)

## 実装順序

1. `inspect/integrity-check.ts` — Layer A プローブ(A1-A8)+ viewport 運転
   (A9)。scroll-scan / copy-target / component-bbox / smoke-runner の
   既存資産を import で束ねる。ユニットテストは mutation 注入形。
2. CLI leaf `check integrity` + MCP `check_integrity`。
3. S14b mutation バッテリー(fixture + テスト化 — 回帰として常設)。
4. S14c 偽陽性 fixture + 外部 dogfood → 免除ルール調整。
5. Layer B ワークシート生成(check equivalence のペア画像 + 質問シートの
   流用)。キーがある環境での VLM 直結は Issue #88 のベンチ枠に相乗り。
6. S14a 実走 + 追記レポート + knowledge.md 台帳行。

## リスク / 判断保留

- **A4 の免除ルールが本丸**。重なり検知自体は自明だが、意図的オーバーレイの
  免除を狭くすると偽陽性の山、広くすると本物の衝突を握り潰す。S14c を
  先に厚くして閾値を実測で決める(z-index 差 + 祖先 positioning +
  背景 ink 密度の 3 条件から開始)。
- **A8 の UA デフォルト指紋**はリセット CSS 使用ページで誤爆しうる
  (destyle 等は意図的に素へ戻す)。stylesheet ロード成否(A3)と
  組み合わせ、「宣言があるのに効いていない」場合のみ fail にする。
- **A2 の退化判定**は全面画像ページ(ポスター的 LP)で背景率が計れない
  → component 抽出 0 個 かつ ink 分布退化の AND 条件にする。
- Layer B はキーなし環境では人間/別エージェント依存 — S14 の証明は
  Layer A 中心で成立させ、B は advisory として段階投入(check equivalence
  と同じ轍)。