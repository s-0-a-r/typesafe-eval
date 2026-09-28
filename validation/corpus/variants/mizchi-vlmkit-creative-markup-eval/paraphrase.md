# 設計: 参照なし(創造的)マークアップの評価シナリオ

日付: 2026-07-30 / ステータス: Layer A は実装完了(同日)、Layer B / S14a は着手前

## 実装状況(2026-07-30)

実装順序 1〜4 をリリース:
- `packages/vlmkit-markup/src/inspect/integrity-check.ts` — Layer A のプローブ一式
  (A1-A9)。A3 の stylesheet/script/font は **wire 検知**(requestfailed +
  非 OK response)へ切り替え — Chromium は 404 になった `<link>` にも空の
  CSSStyleSheet を付与するので、`link.sheet != null` では死んだ stylesheet を
  区別できない(実装の途中で実測)。A2 は DOM 側の textBlocks も判定材料に入れる
  (テキストだけのページではグリフが minArea に届かず components が 0 になり、
  pixel だけで見ると偽の degenerate になる)。
- CLI `check integrity` および MCP `check_integrity`(8 本目)。
- S14b mutation バッテリー: **9/9 クラスを検知**(回帰テストとして常設)。
- S14c 偽陽性監査(自作分): hero オーバーレイ / ellipsis / 位置決め
  アンカー / aria-hidden 装飾 → verdict は clean、候補はすべて `exempted` に記録された。
- 初回 dogfood: S8 edit fixture(1280 で DONE を検証済み)に、375 で 67px の
  実際のオーバーフローがあることを検出(帰属は `div.plans`) — 参照ありゲートの
  死角(target の無い幅)を直接裏付ける結果。
- S14c 外部 dogfood も実施済み(同日): 実ページ 5 本で免除ルールを 4 クラス
  修正(最も重要なのは image replacement / sr-only)。
  `docs/reports/2026-07-30-integrity-external-dogfood.md`。
- S14a 実走済み(同日): Haiku は DONE(修正ラウンド 1 回)、検証フェーズでの
  gate 沈黙欠陥は 0。`docs/reports/2026-07-28-verifier-tooling-and-s6.md`
  の追記13。派生した課題: 高密度ブリーフの負荷版、check copy の状態ごとの検証。
- Layer B ワークシート: **凍結(需要ゲート、2026-07-30)** — 決定論への降格で
  残りは 2 軸にまで縮み、gate 沈黙欠陥を実際に観測することが着手の条件(後述の Layer B 節)。

### Layer A 拡張(2026-07-30 第 2 陣) — B 軸からの決定論降格

S14 で得た判別の語彙(部分切れ vs 完全隠し / positioned+z-index は意図 /
近接=事故)を用いて、Layer B 側に残していた判断 4 件を決定論に置き換えた:

- **A10 `container-protrusion`** — overflow visible のままの painted parent
  (枠線や背景を持つ box)から、in-flow の子が外へはみ出す(どのゲートも
  反応しなかった、最も頻度の高いクラス)。positioned な子(badge)と負の水平マージン
  (full-bleed breakout)はツール側で exempt。
- **A11 `invisible-text` / `low-contrast-text`** — 対象は単色背景だけで、
  αブレンドと累積 opacity を含めて WCAG 比を実測(<1.15 で fail、<3 で warn)。
  背景画像/グラデーションは、ページ単位にまとめた exempt 行で明示的にスキップ
  (引き続き Layer B の領域)。disabled / text-shadow は exempt。
  **image-replacement などで視覚的に隠されたテキスト(自要素か祖先の
  クリップの外)はスキップ** — zen garden の dogfood で見つかった偽陽性クラス
  (閉じたドロップダウンの中の白文字を invisible と誤って報告)への対応。
- **A12 `near-misalignment`(warn)** — 同じ型の兄弟 3+ が left/center/right/top
  のどれかで正確に揃っているとき、2-8px だけずれた要素を警告。
  「0px でも 9px 以上でも正常、帯域内だけが事故」という near-miss 原理を整列に当てはめたもの。
  別の軸で正確に揃う要素(左揃えリストの中の中央揃え)は意図とみなしてスキップ。
- **`check layout --contract`(別ゲート、`inspect/layout-contract.ts`)** —
  ブリーフが求める構造(幅±許容、1 行ごとのセル数、full-width への折りたたみ、
  積み順、可視性、個数)を宣言 JSON と照らし合わせる。S14a-stress の検証者が手で書いて
  いた DOM 計測を正式にしたもの。MCP `check_layout`(9 本目)。

dogfood(zen garden / danluu / HN / 自作 fixture のすべて)で偽陽性が 0 になるよう調整
済み。attempt-stress の #changelog が low-contrast warn(2.56:1)で
引っかかったのは真陽性(Haiku が書いた、実際に薄すぎる文字)。

## 背景と目的

これまでの評価軸(S1-S13)はどれも **お手本がある** — target 画像・reference
HTML・copy manifest のどれかが正解として用意されていて、gate は「一致したかどうか」を
判定してきた。ところが実際の運用では「ブリーフだけを渡してゼロからマークアップさせる」
創造的なタスクがよく出てくる。この場合は正解画像がないが、**それでもはっきり
評価できる項目はある**:

- レイアウト崩れ(テキストの衝突、はみ出し、潰れたコンテナ、水平スクロール)
- JS エラーで UI の構築に失敗する(白画面、部品の欠落)
- リソース切れ(壊れた画像、読み込めなかった CSS)
- スタイルが当たっていない(UA デフォルトのままの「素 HTML」)

これらは「デザインの良し悪し」ではなく **欠陥(defect)** であって、
(a) 決定論によるレイアウト検査と (b) VLM による視覚判断の 2 層で検知できる。
この設計では、2 層の役割分担・新ゲート `check integrity`・検証シナリオ S14 を定める。

## 設計原則(このリポジトリの実測から持ち込むもの)

1. **VLM に数値を答えさせない**。座標・寸法・重なりの量・比率は全部
   決定論(pixel + DOM 計測)で出す。VLM がやるのは「読む・判断する」だけ
   (diff-region A/B で実測された net-negative に基づく)。
2. **降格と免除を決めるのはツール**。意図的なオーバーレイ(hero テキストなど)の
   免除はツール側のルールとして JSON に明記し、エージェントが合理化する余地を
   なくす(合理化 7 例を繰り返さないため)。
3. **ピクセルを書いた本人の自己レビューは無効**(same-eyes)。Layer B の VLM 判定は、
   マークアップしたエージェントとは別の読み手であることを必須にする。
4. **VLM の主張は決定論で反証(refutation)する**。vlm-region-diff の
   refutation gate(2026-06-08)と同じ形: VLM が「崩れている」と指摘した領域を
   Layer A の計測と突き合わせ、裏付けが取れない行は低信頼へ降格する。

## 欠陥タクソノミー(参照なしで判定可能なもの)

### Layer A — 決定論(hard、単体で FAIL 判定可)

| # | 欠陥クラス | 検知法 | 再利用資産 |
|---|---|---|---|
| A1 | JS エラー / UI 構築の失敗 | load〜idle の間 `page.on("pageerror")` + `console.error` + `requestfailed` を集める。first-paint より前の fatal(構築を止めた)か後(装飾的)かで分ける | `inspect/smoke-runner.ts:295` にある pageerror 監視 |
| A2 | 空・退化したレンダー | スクリーンショットから component を抽出し、成分数 0 / 背景率 >98% / ink が viewport の上部 10% だけ、を退化とみなす | `component-bbox.ts` `extractComponentsFromRgba`(target なしで current 単体に適用) |
| A3 | 壊れたリソース | `img.naturalWidth === 0`(src があり lazy でない)、`link[rel=stylesheet]` の sheet がロードされていない、`@font-face` の失敗 | 新規(in-page スクリプト 1 本) |
| A4 | テキストの衝突(重なり) | `COLLECT_TEXT_BLOCKS` の矩形同士をペアワイズで交差判定。**免除**: 祖先が `position:absolute/fixed` で z-index に差がある意図的オーバーレイ、`opacity:0`/装飾 (`aria-hidden`) | `inspect/copy-target.ts` `COLLECT_TEXT_BLOCKS` |
| A5 | テキストのはみ出し / 切れ | 要素の `scrollWidth > clientWidth`(overflow が visible でない)+ ink が親の painted box の外へ出ているかの pixel 検査 | scroll-scan の `clipped-content` プローブと同じ型 |
| A6 | 潰れたコンテナ | 子の高さの合計 ≫ 自分の height(float/absolute の取り込み失敗、height:0 による崩れ) | 新規(DOM 計測だけ) |
| A7 | 水平オーバーフロー / スクロールの異常 | 既存の `scan scroll` の `page-overflow-x` / `nested-scroll` / `clipped-content` をそのまままとめて実行 | `inspect/scroll-scan.ts`(全体を再利用) |
| A8 | スタイル未適用(FOUC / 素 HTML) | stylesheet の宣言があるのに、computed style の UA デフォルト比率が高い(font-family serif・margin 8px body・青いリンク等の指紋) | 新規 |
| A9 | ビューポート横断 | A2-A8 を 1280 / 768 / 375 の 3 viewport で回す(創造的マークアップは狭い幅で崩れるのがお決まり) | breakpoint sweep の運転の形 |

各検知には `severity: fail | warn` と **セレクタ帰属**(どの要素のどの矩形か)が
付く。S9 リプレイで実証された「帰属付き kickback で rounds が半分になる」を、
この gate にも最初から当てはめる。

### Layer B — VLM 視覚判定(soft、advisory / 反証付き)

> **状態 2026-07-30: 凍結(需要ゲート)。** 下の表のうち B1 は A12 へ、
> B2 の主要部分(コントラスト)は A11 へ、B4 構造は `check layout --contract` へ、
> B4 コピーは manifest と決定論側へ移った。残っているのは B3 + 複合背景
> コントラスト + 美観だけで、S14a の 3 ラン全ての検証フェーズで gate 沈黙
> 欠陥は 0 — B3 が拾うはずの欠陥はまだ観測されていない。着手の条件は
> 「gate 沈黙欠陥を実際に観測すること」。以降は当初の設計の記録として残しておく。

決定論では書けない「見た目がおかしい」という層。固定ルーブリックによる
**強制択一 + 根拠となる領域の指名**で回答させる(自由記述で印象を批評させることはしない):

| 軸 | 質問(強制択一) | 反証チェック |
|---|---|---|
| B1 整列 | 「明らかに揃っていない要素のまとまりはあるか — あれば領域名を示せ」 | 示された領域の bbox 左端/中心線の分散を実測。閾値より分散が小さければ refuted |
| B2 視覚階層 | 「見出し・本文・CTA を区別できるか(yes/no)」 | 示された領域の font-size / weight / 色差を実測 |
| B3 破綻の見落とし網 | 「壊れているように見える箇所はあるか — 領域名 + 一語で理由」 | Layer A のすべての検知と照合。**双方向**: VLM が示したのに A が反応しない → A の穴の候補として記録 / A が検知したのに VLM が反応しない → VLM の盲点として記録 |
| B4 ブリーフ充足 | 「ブリーフで必須の要素 X が見えるか」(要素ごと) | copy sheet(A4 の矩形)に対応するテキストがあるかどうかで反証 |

- 出力の形式は `check equivalence` と同じく **keyless advisory**: API キーの
  ない環境では、ペア画像と質問ワークシートを作って「別の読み手」
  (人間か別のエージェント)に渡す。キーがあれば VLM を直接呼び出す。
- Layer B だけで FAIL にはしない。**Layer A で裏付けが取れた行だけ**を kickback に
  昇格させる(refutation gate と同じ demotion 規約: `verification.refuted`
  フラグを付けるのはツールで、消費する側には解釈させない)。

### 対象外(このゲートで判定しないもの)

- 美的な良し悪しやブランドとの適合(正解を定義できない)
- コントラスト比の厳密な WCAG 判定 — 決定論でもできるが、背景の合成
  (グラデーションや画像の上のテキスト)を実装するのが重い。A8 とは別の枠の
  将来のプローブとして backlog に入れておく。
- copy が正しいかどうか — ブリーフが全文を引用しているなら既存の
  `check copy --target`(manifest 経路)をそのまま使える。この gate の
  役割ではない(S14a の運転で組み合わせる)。

## 新ゲート: `check integrity`

```
vlmkit check integrity <html-or-url> [--viewports 1280,768,375] [--brief brief.md]
                       [--json] [--out-dir .vlmkit/integrity]
```

- **入力はページ単体**(target 画像なし)。`--brief` を使うのは B4 の必須要素
  リストを抽出するときだけ(指定がなければ B4 はスキップ)。
- 実行の順序: 1 回のロードで A1/A3/A8 を集める → viewport ごとに
  screenshot + A2/A4/A5/A6/A7 → Layer B のワークシートを生成。
- 出力: `IntegrityReport { verdict: "clean" | "defects", findings: [...],
  advisory: [...], sheets: [...] }`。findings は
  `{ kind, severity, selector?, rect?, viewport, evidence, exempted?: reason }`
  — 免除された候補も `exempted` として残す(ツールの判定を見えるようにする)。
- kickback の形式は verify markup と同じ規約(`[kind]` タグ + セレクタ帰属 +
  「次のアクションの指示として使える形」)。
- **verify markup との関係**: 参照ありのフローでは、主 gate は引き続き verify markup。
  `check integrity` は (a) 参照なしタスクでの主 gate、(b) 参照ありの場合でも
  behavior gate 群と同じように verify markup に内部統合できる構造(純関数 +
  CLI の薄皮)にしておく。
- **MCP**: 第一弾で `check_integrity` として追加(パスを受け取り、
  findings に fail があれば isError)。キーが要らないので既存の 7 本と同じ扱い。

## 検証シナリオ: S14 バッテリー

gate そのものの妥当性を、従来と同じやり方(mutation testing + 外部 dogfood +
偽陽性監査)で証明したうえで運用に入れる。

### S14b — mutation バッテリー(最優先: 検知率の証明)

clean なページ(既存 fixture で DONE に到達した attempt を使い回す)に、
タクソノミーの各クラスの欠陥を 1 つずつ入れ、gate が**そのクラスとして**
検知するかを確かめる。CSS-challenge と同じ、検知率表による方法論。

| 注入 | 期待検知 |
|---|---|
| `<script>throw new Error(...)</script>` を head に入れる(構築前 fatal) | A1 fatal |
| 初期化 JS の関数名を 1 文字壊す(部品が表示されない) | A1 + A2 or A6 |
| `img src` を 404 にする | A3 |
| absolute のテキスト 2 つを同じ座標に置く | A4 |
| コンテナの width を 40px にする(テキストが切れる) | A5 |
| flex の親に height:0 + overflow:hidden | A6 |
| width 1500px 固定の要素を差し込む | A7 (page-overflow-x) |
| stylesheet の href を 404 にする | A8 (+A3) |
| 375px のときだけ潰れる min-width 指定 | A9 経由で該当するクラス |

**合格基準: 9/9 クラスを検知**(目標は検知率 100% — 注入するのは自明なケースなので、
取りこぼすならプローブの設計が悪い)。誤ったクラスでの検知(A6 を A2 として報告する等)は
帰属の質の問題として別に数える。

### S14c — 偽陽性監査(免除ルールの証明)

意図的なパターンだけで組んだ clean なページ群に gate をかけ、
**findings が 0 / exempted に正しく載っている**ことを確かめる:

- hero 画像の上に重ねたテキストオーバーレイ(A4 免除)
- ドロップダウン / バッジの重なり(A4 免除)
- 横スクロールのカルーセル(A7 の nested-scroll 免除条件)
- `text-overflow: ellipsis` による意図的な切り詰め(A5 免除)
- 装飾目的の `aria-hidden` の重ね文字(A4 免除)

加えて、外部ページ(APG dogfood と同じく curl ミラー経由)1-2 本で
現実の偽陽性を拾う。**APG の教訓**: 自作 fixture だけでは
免除ルールの穴は見つからない — 外部 dogfood を S14c で必ず行う手順にする。

### S14a — 創造的マークアップ実走(gate の実効性)

1. ブリーフだけ(target 画像なし)を書く。**ブリーフに copy をすべて引用**し、
   ブリーフそのものが copy manifest も兼ねる形にする(hidden-state copy carrier の
   既存規約を使い回す)。
2. Haiku にゼロからマークアップさせて、`check integrity` でループを回す
   (DONE 条件 = verdict clean × 3 viewports + `check copy` manifest の一致)。
3. 詰まったら Sonnet に kickback を逐語でハンドオフ(S9 と同じ運転)。
4. 検証フェーズ: 別の読み手が Layer B ワークシートと copy diff で監査
   (same-eyes を排除)。
5. 計測: rounds / 検知が修正を正しく導いたか(帰属セレクタと実際の修正の
   対応)/ gate は沈黙したが検証フェーズで見つかった欠陥(= gate の穴)。

### 指標(knowledge.md 台帳へ)

- クラスごとの検知率(S14b、9 クラス)
- 偽陽性率(S14c、意図的パターン n 個 + 外部ページ)
- S14a: rounds-to-clean、kickback 追従率、gate 沈黙欠陥の数
- Layer B 反証率(VLM の主張のうち決定論で裏付けが取れた割合 — 低すぎれば
  B を納品物から外して A だけの運用に切り替える判断材料)

## 実装順序

1. `inspect/integrity-check.ts` — Layer A プローブ(A1-A8)+ viewport 運転
   (A9)。scroll-scan / copy-target / component-bbox / smoke-runner の
   既存資産を import でまとめる。ユニットテストは mutation を注入する形。
2. CLI leaf `check integrity` と MCP `check_integrity`。
3. S14b mutation バッテリー(fixture + テスト化 — 回帰として常設する)。
4. S14c 偽陽性 fixture + 外部 dogfood → 免除ルールの調整。
5. Layer B ワークシートの生成(check equivalence のペア画像 + 質問シートを
   使い回す)。キーのある環境での VLM 直結は Issue #88 のベンチ枠に便乗させる。
6. S14a 実走 + 追記レポート + knowledge.md の台帳行。

## リスク / 判断保留

- **本丸は A4 の免除ルール**。重なりの検知そのものは自明だが、意図的オーバーレイの
  免除を狭くすれば偽陽性が山になり、広くすれば本当の衝突を握り潰してしまう。S14c を
  先に厚くしておき、閾値は実測で決める(z-index 差 + 祖先 positioning +
  背景 ink 密度の 3 条件からスタート)。
- **A8 の UA デフォルト指紋**は、リセット CSS を使うページで誤検知するおそれがある
  (destyle などは意図して素の状態へ戻す)。stylesheet のロード成否(A3)と
  組み合わせて、「宣言はあるのに効いていない」ときだけ fail にする。
- **A2 の退化判定**は、全面が画像のページ(ポスター風の LP)では背景率を計測できない
  → component 抽出が 0 個 かつ ink 分布が退化、という AND 条件にする。
- Layer B はキーのない環境では人間/別エージェント頼み — S14 の証明は
  Layer A を中心に成り立たせ、B は advisory として段階的に投入(check equivalence
  と同じ轍)。
