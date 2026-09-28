---
title: "Visual Studio Code (VS Code)のオススメ設定と拡張機能の紹介"
emoji: "♾️"
type: "tech"
topics: ["vscode"]
published: true
published_at: 2024-04-01 06:00
---
本記事ではC言語やTypeScriptなど特定の言語を使う際に便利な設定と拡張機能ではなく、言語にかかわらずVS Codeで使えるオススメの設定と拡張機能を紹介します。参考になれば幸いです。

更新履歴は[こちら](#更新履歴)に記載しています。

個々の設定について後ろで解説していますが、まとめて設定をコピー＆ペーストできるように、以下に設定をまとめています。

```json:settings.json
{
  "editor.bracketPairColorization.enabled": true,
  "editor.cursorBlinking": "expand",
  "editor.cursorSmoothCaretAnimation": "on",
  "editor.cursorStyle": "line-thin",
  "editor.dragAndDrop": false,
  "editor.fontFamily": "'Moralerspace Neon HWNF', Consolas, 'Courier New', monospace",
  "editor.guides.bracketPairs": true,
  "editor.minimap.maxColumn": 80,
  "editor.minimap.showSlider": "always",
  "editor.mouseWheelZoom": true,
  "editor.renderLineHighlight": "all",
  "editor.renderWhitespace": "all",
  "editor.showFoldingControls": "always",
  "editor.smoothScrolling": true,
  "editor.wordSegmenterLocales": "ja",
  "editor.wrappingIndent": "indent",
  "explorer.confirmDelete": false,
  "explorer.confirmDragAndDrop": false,
  "files.autoGuessEncoding": true,
  "files.candidateGuessEncodings": ["utf8", "shiftjis", "eucjp"],
  "files.insertFinalNewline": true,
  "files.trimFinalNewlines": true,
  "files.trimTrailingWhitespace": true,
  "git.autofetch": "all",
  "git.confirmSync": false,
  "git.pruneOnFetch": true,
  "git.suggestSmartCommit": false,
  "scm.alwaysShowRepositories": true,
  "scm.defaultViewMode": "tree",
  "scm.diffDecorationsGutterWidth": 5,
  "scm.inputFontFamily": "editor",
  "scm.inputFontSize": 14,
  "search.showLineNumbers": true,
  "terminal.integrated.cursorBlinking": true,
  "terminal.integrated.cursorStyle": "line",
  "terminal.integrated.enableImages": true,
  "terminal.integrated.enableVisualBell": false,
  "terminal.integrated.mouseWheelZoom": true,
  "terminal.integrated.smoothScrolling": true,
  "workbench.colorTheme": "Default High Contrast",
  "workbench.editor.closeOnFileDelete": true,
  "workbench.editor.scrollToSwitchTabs": true,
  "workbench.editor.wrapTabs": true,
  "workbench.list.smoothScrolling": true,
  "workbench.view.alwaysShowHeaderActions": true
}
```

括弧の対応を色分けして表示します。

![Bracket pair colorizationのON/OFFの比較画像](/images/1577b6dc5ab7d9/on-off-comparison.drawio.webp)

画像出典: [Bracket pair colorization 10,000x faster](https://code.visualstudio.com/blogs/2021/09/29/bracket-pair-colorization)

```json:settings.json
"editor.bracketPairColorization.enabled": true
```

本設定が登場する前は、同様の機能を`Bracket Pair Colorizer`や`Bracket Pair Colorizer 2`という拡張機能を入れて実現していましたが、拡張機能のインストールは必要なくなりました。

カーソルのアニメーション方式を設定します。

`expand`にすると、カーソルが拡大縮小するアニメーションになるため、カッコよくオススメです。

![editor.cursorBlinkingをexpandにしたときの動画](/images/1577b6dc5ab7d9/editor-cursorBlinking-expand.webp)

```json:settings.json
"editor.cursorBlinking": "expand"
```

ONにすることでカーソルの移動時にアニメーションを滑らかにします。

```json:settings.json
"editor.cursorSmoothCaretAnimation": "on"
```

カーソルの形状を`line-thin`として、デフォルト (`line`) より細くします。
補足することで、カーソル周辺の文字が見やすくなります。

![editor.cursorStyle"をlineにしたときの画像](/images/1577b6dc5ab7d9/editor-cursorStyle-line.webp)

![editor.cursorStyleをline-thinにしたときの画像](/images/1577b6dc5ab7d9/editor-cursorStyle-line-thin.webp)

```json:settings.json
"editor.cursorStyle": "line-thin"
```

デフォルトは`true`ですが、`false`にすることで、テキストをドラッグ＆ドロップで移動できなくなります。

私はこの機能が邪魔に感じることがあるため、OFFにしています。

```json:settings.json
"editor.dragAndDrop": false
```

等幅フォントとしてMoralerspaceを使っているので、最優先のフォントとして、`Moralerspace Neon HWNF`を設定しています。

Moralerspaceについては、以下のリンクからダウンロードできます。

@[card](https://github.com/yuru7/moralerspace)

Moralerspace Neon HWNF以降のフォントは、VS CodeのデフォルトフォントであるConsolas、Courier New、monospaceを設定しています。

```json:settings.json
"editor.fontFamily": "'Moralerspace Neon HWNF', Consolas, 'Courier New', monospace"
```

括弧の対応を表示します。

![Bracket pairsの表示画像](/images/1577b6dc5ab7d9/bracket-pair-guides.webp)

画像出典: [Improved bracket pair guides](https://code.visualstudio.com/updates/v1_62#_improved-bracket-pair-guides)

```json:settings.json
"editor.guides.bracketPairs": true
```

ミニマップの最大表示列数を設定します。

デフォルトは`120`ですが`80`にすることで、ミニマップの幅を狭くしてミニマップ以外の表示幅を増やします。

個人的には、`80`もあれば全体のなんとなくの構造が把握できるので、`80`に設定しています。

```json:settings.json
"editor.minimap.maxColumn": 80
```

ミニマップのスライダーを常に表示します。

```json:settings.json
"editor.minimap.showSlider": "always"
```

Ctrlキーを押しながらマウスホイールを使用してエディターのズームを有効にします。

```json:settings.json
"editor.mouseWheelZoom": true
```

カーソルがある行をハイライト表示する設定です。

デフォルトは`line`ですが、`all`にすることで、カーソルがある行全体をハイライト表示します。

違いが分かりにくいですが、`all`にすると以下の画像のように行番号を含むカーソルがある行全体がハイライト表示されます。

![editor.renderLineHighlightをlineにしたときの画像](/images/1577b6dc5ab7d9/editor-renderLineHighlight-line.webp)

![editor.renderLineHighlightをallにしたときの画像](/images/1577b6dc5ab7d9/editor-renderLineHighlight-all.webp)

```json:settings.json
"editor.renderLineHighlight": "all"
```

空白文字が常に表示されるようにします。

具体的には、赤線のようにスペースは薄い"・"のような表示になり、タブは薄い"→"のような表示になります。

編集しているファイルのインデントが混在している場合、空白文字を表示することで、インデントの混在を確認しやすくなります。

![editor.renderWhitespaceをallにしたときの画像](/images/1577b6dc5ab7d9/editor-renderWhitespace-all.webp)

```json:settings.json
"editor.renderWhitespace": "all"
```

画像赤線のように、折りたたみコントロールが常に表示されます。

![editor.showFoldingControlsをalwaysにしたときの画像](/images/1577b6dc5ab7d9/editor-showFoldingControls-always.webp)

```json:settings.json
"editor.showFoldingControls": "always"
```

`true`にすることで、スクロール時のアニメーションを滑らかにします。

```json:settings.json
"editor.smoothScrolling": true
```

単語の分割を行うロケールを設定します。

設定をすると、画像のように`Ctrl + →`や`Ctrl + ←`で単語の先頭や末尾に移動する際に、日本語の単語を区切りとして扱ってくれます。

(画像では拡張機能と書いていますが、正しくは設定のことです。以前[Word Divider](https://marketplace.visualstudio.com/items?itemName=yutotnh.word-divider)で作成した画像を流用したため、誤解を招くかもしれませんが、設定のことです)

![editor.wordSegmenterLocalesの動作イメージ](/images/1577b6dc5ab7d9/editor-wordSegmenterLocales.webp)

```json:settings.json
"editor.wordSegmenterLocales": "ja"
```

日本語の移動を便利にする拡張機能として以下の拡張機能がありますが、本設定を使うことでこれらの拡張機能を使わずに日本語の単語間移動ができるようになります。本設定を利用する場合は、以下の拡張機能を無効にしたり、アンインストールする必要があります。

-   [Japanese Word Handler](https://marketplace.visualstudio.com/items?itemName=sgryjp.japanese-word-handler)
-   [CJK Word Handler](https://marketplace.visualstudio.com/items?itemName=SharzyL.cjk-word-handler)
-   [たんごカーソル](https://marketplace.visualstudio.com/items?itemName=TaiyoFujii.japanese-morpheme-handler)
-   [Word Divider](https://marketplace.visualstudio.com/items?itemName=yutotnh.word-divider)

本設定に関しては私がVS Codeに追加したため、不具合がある場合は本記事のコメントか[VS CodeのIssue](https://github.com/microsoft/vscode/issues)で報告していただけると幸いです。

`indent`にすることで、折り返し行のインデントが元の行のインデント+1になります。

デフォルトの`same`だと、折り返し行のインデントが元の行のインデントと同じになります。

![editor.wrappingIndentをsameにしたときの画像](/images/1577b6dc5ab7d9/editor-wrappingIndent-same.webp)

![editor.wrappingIndentをindentにしたときの画像](/images/1577b6dc5ab7d9/editor-wrappingIndent-indent.webp)

```json:settings.json
"editor.wrappingIndent": "indent"
```

Windowsなどファイルやフォルダーを削除してゴミ箱にファイルを送る場合、確認ダイアログを表示しないようにします。

間違ってファイルを削除しても、Ctrl+Zで元に戻せるので、確認ダイアログを表示しないようにしています。

```json:settings.json
"explorer.confirmDelete": false
```

ファイルをドラッグ＆ドロップで移動する際に確認ダイアログを表示しないようにします。

これも間違ってファイルを移動しても、Ctrl+Zで元に戻せるので、確認ダイアログを表示しないようにしています。

```json:settings.json
"explorer.confirmDragAndDrop": false
```

ファイルのエンコーディングを自動で推測するようにします。

私は複数のエンコーディングを使うことがあるため、推測機能をONにしています。

推測機能は完璧ではなため別のエンコーディングとして判定されることがありますが、[VS Code #208550](https://github.com/microsoft/vscode/pull/208550)がマージされれば、新規設定によって推測機能が改善されるため、今後のアップデートに期待です。

もしUTF-8しか使わない場合は、OFFにしておくとエンコーディングの誤検知を防げます。

```json:settings.json
"files.autoGuessEncoding": true
```

files.autoGuessEncodingにtrueを指定した時にファイルのエンコーディングを推測する際の候補として使うエンコーディングを設定します。

これを設定することで、推測機能で日本語のファイルをWindows 1252などと誤検知してしまうことを防ぐことができます。

私はUTF-8、Shift_JIS、EUC-JPを使うことが多いため、これらのエンコーディングを候補として設定しています。

```json:settings.json
"files.candidateGuessEncodings": ["utf8", "shiftjis", "eucjp"],
```

本設定に関しては私がVS Codeに追加したため、不具合がある場合は本記事のコメントか[VS CodeのIssue](https://github.com/microsoft/vscode/issues)で報告していただけると幸いです。

ファイルの保存時に末尾に改行を挿入します。

```json:settings.json
"files.insertFinalNewline": true
```

ファイルの保存時に末尾の余分な改行を削除します。

たとえば、以下のようなファイルの末尾の余分な改行が削除されます。

```plaintext
Hello, World!



```

↓

```plaintext
Hello, World!

```

```json:settings.json
"files.trimFinalNewlines": true
```

ファイルの保存時に行末の空白文字を削除します。

```json:settings.json
"files.trimTrailingWhitespace": true
```

定期的に自動ですべてのリモートリポジトリから最新の情報を取得します。

もしfetch時にパスワードを求められるような場合は`false`にして無効にしてください。

```json:settings.json
"git.autofetch": "all"
```

同期時に確認ダイアログを表示しないようにします。

個人的には同期しても問題ないため、確認ダイアログを表示しないようにしています。

```json:settings.json
"git.confirmSync": false
```

`true`にすることで、fetch時にリモートリポジトリから削除されたブランチをローカルリポジトリから削除します。

```json:settings.json
"git.pruneOnFetch": true
```

ステージングされた変更がない場合にすべての変更をコミットするスマートコミットを提案する機能を無効にします。

すべての変更をコミットすることは、意図しない変更をコミットする可能性があるため、OFFにしています。

```json:settings.json
"git.suggestSmartCommit": false
```

`true`にすることで、サイドバーにリポジトリを常に表示します。

画像のようにリポジトリの状態が一目でわかるため、リポジトリを常に表示することをオススメします。

![scm.alwaysShowRepositoriesをtrueにしたときの画像](/images/1577b6dc5ab7d9/scm-alwaysShowRepositories-true.webp)

```json:settings.json
"scm.alwaysShowRepositories": true
```

デフォルトの変更ファイル一覧の表示をツリー表示にします。

デフォルトは`list`ですが、`tree`にすることで、変更ファイル一覧をツリー表示にします。

![scm.defaultViewModeをlistにしたときの画像](/images/1577b6dc5ab7d9/scm-defaultViewMode-list.webp)

![scm.defaultViewModeをtreeにしたときの画像](/images/1577b6dc5ab7d9/scm-defaultViewMode-tree.webp)

```json:settings.json
"scm.defaultViewMode": "tree"
```

差分の行数を表示するガターの幅を設定します。

デフォルトは`3`ですが、`5`にすることで、差分がある行をよりわかりやすく表示します。

![scm.diffDecorationsGutterWidthを3にしたときの画像](/images/1577b6dc5ab7d9/scm-diffDecorationsGutterWidth-3.webp)

![scm.diffDecorationsGutterWidthを5にしたときの画像](/images/1577b6dc5ab7d9/scm-diffDecorationsGutterWidth-5.webp)

```json:settings.json
"scm.diffDecorationsGutterWidth": 5
```

デフォルトだとコミットメッセージの入力箇所がエディターと異なるフォントになるため、エディターと同じフォントに設定しています。

画像の"ABCDEFG"の個所が適用箇所です。

![scm.inputFontFamilyをeditorにしたときの画像](/images/1577b6dc5ab7d9/scm-inputFontFamily-editor.webp)

```json:settings.json
"scm.inputFontFamily": "editor"
```

デフォルトの13だと少し小さく感じるため、14に設定しています。

```json:settings.json
"scm.inputFontSize": 14
```

画像の赤線のようにサイドバーでの検索結果に行番号を表示します。

![search.showLineNumbersをtrueにしたときの画像](/images/1577b6dc5ab7d9/search-showLineNumbers-true.webp)

```json:settings.json
"search.showLineNumbers": true
```

ターミナルのカーソルを点滅させます。

点滅させたほうがカーソルの位置がわかりやすいため、点滅させるようにしています。

```json:settings.json
"terminal.integrated.cursorBlinking": true
```

ターミナルのカーソルの形状を`line`に設定します。

デフォルトの`block`だと、個人的に文字の間にカーソルがあるときに文字の削除や挿入の位置がわかりにくいため、`line`に設定しています。

![terminal.integrated.cursorStyleをblockにしたときの画像](/images/1577b6dc5ab7d9/terminal-integrated-cursorStyle-block.webp)

![terminal.integrated.cursorStyleをlineにしたときの画像](/images/1577b6dc5ab7d9/terminal-integrated-cursorStyle-line.webp)

```json:settings.json
"terminal.integrated.cursorStyle": "line"
```

ターミナルで画像を表示できるようにします。

有効にすると、img2sixelなどの画像表示機能を使うことで、ターミナルで画像を表示できるようになります。

![terminal.integrated.enableImagesをtrueにしたときの画像](/images/1577b6dc5ab7d9/terminal-integrated-enableImages-true.webp)

```json:settings.json
"terminal.integrated.enableImages": true
```

ターミナルでのベルがなったときに、画像の赤線箇所のようにターミナル名の横にベルマークを表示させます。

音を鳴らさないような環境で作業をすることがあるため、ベルマークを表示させるようにしています。

![terminal.integrated.enableVisualBellをtrueにしたときの画像](/images/1577b6dc5ab7d9/terminal-integrated-enableVisualBel-true.webp)

```json:settings.json
"terminal.integrated.enableVisualBell": false
```

ターミナルでCtrlキーを押しながらマウスホイールを使用してエディターのズームを有効にします。

```json:settings.json
"terminal.integrated.mouseWheelZoom": true
```

ターミナルでスクロール時のアニメーションを滑らかにします。

デフォルトのfalseだとスクロールがカクカクするため、違和感を覚えると思います。

```json:settings.json
"terminal.integrated.smoothScrolling": true
```

好みのテーマに変更してください。

私は、各要素の区切りがはっきりしている`Default High Contrast`を使っています。

ただし、テーマによっては特定の要素が見づらくなることがあるため、何らかの要素が見づらくなった場合は、一時的に他のテーマに変更して閲覧することをオススメします。私は一時的に変更するときは、`Visual Studio Dark`に変更しています。

```json:settings.json
"workbench.colorTheme": "Default High Contrast"
```

外部要因でファイルが削除されたときにエディターを閉じるかどうかを設定します。

デフォルトでは、端末でファイルを削除した時に、エディターでそのファイルを開いてた時にファイルを保存するとファイルが復活するため、ファイルを削除したときにエディターを閉じるようにしています。

```json:settings.json
"workbench.editor.closeOnFileDelete": true
```

エディターのタブ部分でマウスのスクロールを行うと、タブが切り替わるようにします。

```json:settings.json
"workbench.editor.scrollToSwitchTabs": true
```

タブが画面幅を超えたときに折り返すようにします。

デフォルトの`false`だと、タブが画面幅を超えたときに折り返さないため、タブで開いているファイルを把握しにくくなります。

![workbench.editor.wrapTabsをfalseにしたときの画像](/images/1577b6dc5ab7d9/workbench-editor-wrapTabs-false.webp)

![workbench.editor.wrapTabsをtrueにしたときの画像](/images/1577b6dc5ab7d9/workbench-editor-wrapTabs-true.webp)

```json:settings.json
"workbench.editor.wrapTabs": true
```

`true`にすることで、サイドバーのスクロール時にアニメーション使用して滑らかにします。

```json:settings.json
"workbench.list.smoothScrolling": true
```

`true`にすることで、サイドバーのヘッダーアクションを常に表示します。

デフォルトだとマウスを合わせると表示されるため、マウスをのせない状態だと何ができるのかわかりません。

そのため、常に表示させるようにしています。

いくつかの表示に影響しますが、たとえばエクスプローラーのヘッダーアクションは以下の画像の赤線箇所の表示に影響します。

![workbench.view.alwaysShowHeaderActionsをtrueにしたときの画像](/images/1577b6dc5ab7d9/workbench-view-alwaysShowHeaderActions-true.webp)

```json:settings.json
"workbench.view.alwaysShowHeaderActions": true
```

個々の設定について後ろで解説していますが、まとめて設定をコピー＆ペーストできるように、以下に設定をまとめています。

```json:keybindings.json
[
  {
    "key": "ctrl+oem_1 ctrl+oem_1",
    "command": "workbench.action.editor.changeEncoding"
  },
  {
    "key": "ctrl+0",
    "command": "workbench.action.terminal.focus"
  },
]
```

私は複数エンコーディングを扱うことがあり、頻繁にエンコーディングを変更するため、ショートカットを設定します。

files.candidateGuessEncodingsが登場したことでエンコーディングの自動推測が改善されましたが文字数が少ない場合など推測が外れる場合があり、その際にエンコーディングを変更するため、ショートカットを設定しています。

```json:keybindings.json
{
  "key": "ctrl+oem_1 ctrl+oem_1",
  "command": "workbench.action.editor.changeEncoding"
},
```

`Ctrl+0`でターミナルに移動できるように設定します。

WindowsやLinuxではターミナル画面に移動するためのショートカットがないため、ターミナル画面に移動するためのショートカットを設定しています。

```json:keybindings.json
{
  "key": "ctrl+0",
  "command": "workbench.action.terminal.focus"
},
```

各拡張機能の設定は製品ページに飛んだ方がわかりやすいため、各拡張機能の製品ページへのリンクを貼っています。

ファイルにブックマークをつけることができる拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=alefragnani.Bookmarks)

括弧の対応を表示する拡張機能です。

インストール数は比較的少ないですが、非常に便利な拡張機能です。

ただし、利用シーンによってはかなり処理が重くなることがあるため、VS Codeが重くなった場合は、一時的に無効にすることをオススメします。

@[card](https://marketplace.visualstudio.com/items?itemName=wraith13.bracket-lens)

スペルミスをチェックする拡張機能です。

固有名詞や技術用語などスペルミスと判定されることがありますが、その場合は単語を登録することで、スペルミスと判定されなくなります。

@[card](https://marketplace.visualstudio.com/items?itemName=streetsidesoftware.code-spell-checker)

CSVファイルを編集する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=janisdd.vscode-edit-csv)

`.editorconfig`ファイルを読み込んで、エディターの設定を変更する拡張機能です。

`.editorconfig`ファイルを使っている場合は、この拡張機能を使うことで、`.editorconfig`ファイルに記述した設定をVS Codeに反映させることができます。

@[card](https://marketplace.visualstudio.com/items?itemName=EditorConfig.EditorConfig)

ExcelファイルやCSVファイルをVS Codeで閲覧する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=GrapeCity.gc-excelviewer)

Gitの履歴をグラフで表示する拡張機能です。

検索もしやすいため、Gitの履歴を確認する際に便利です。

@[card](https://marketplace.visualstudio.com/items?itemName=mhutchie.git-graph)

日付のフォーマットが日本人にはわかりにくいため、以下の設定に変更してわかりやすい形にします。

```json:settings.json
"git-graph.date.format": "ISO Date & Time"
```

Gitの履歴を表示する拡張機能です。

個人的にはGit Graphはリポジトリ全体の履歴を確認するのに使い、Git Historyはファイルごとの履歴を確認するのに使っています。

@[card](https://marketplace.visualstudio.com/items?itemName=donjayamanne.githistory)

GitHub Actions関連の機能を提供する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-github-actions)

GitHubのプルリクエストをVS Codeで直接管理できる拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-pull-request-github)

VS CodeデフォルトのGit機能を強化する拡張機能です。

また、編集中のファイルの各行の変更履歴を表示する機能があるため、コードの変更履歴を確認する際に便利です。

@[card](https://marketplace.visualstudio.com/items?itemName=eamodio.gitlens)

バイナリファイルを16進数で表示する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=ms-vscode.hexeditor)

VS Codeを日本語化する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=MS-CEINTL.vscode-language-pack-ja)

ファイルアイコンをデフォルトよりもわかりやすいアイコンに変更する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=PKief.material-icon-theme)

アイコンを変更するには、拡張機能のインストール後、VS Codeの設定で以下の設定を追加してください。

```json:settings.json
"workbench.iconTheme": "material-icon-theme"
```

VS Codeの出力に色をつける拡張機能です。

視認性が向上するため、出力を見る機会が多い方にオススメです。

@[card](https://marketplace.visualstudio.com/items?itemName=IBM.output-colorizer)

ファイルパスを入力する際に補完機能を提供する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=christian-kohler.path-intellisense)

VS Codeのテーマをプロジェクトごとに変更する拡張機能です。

同時に複数のプロジェクトを開いている場合、どのプロジェクトを編集しているかわかりやすくなります。

@[card](https://marketplace.visualstudio.com/items?itemName=johnpapa.vscode-peacock)

CSVファイルの列を色分けして表示する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=mechatroner.rainbow-csv)

行末の改行コードをファイル内で可視化する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=medo64.render-crlf)

メモリ使用量やCPU使用量を表示する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=mutantdino.resourcemonitor)

TODOコメントを一覧表示する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=Gruntfuggly.todo-tree)

行末の余分な空白を表示する拡張機能です。

`"files.trimTrailingWhitespace": true`を設定している場合には保存時に自動で削除されるため、あまり必要ないかもしれませんが、環境によって`false`にしている場合もあるため、必要に応じてインストールしてください。

@[card](https://marketplace.visualstudio.com/items?itemName=shardulm94.trailing-spaces)

日本語の文章を校正する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=ICS.japanese-proofreading)

表外漢字を強調表示する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=noy-shimotsuki.hyogai-kanji-checker)

今回紹介した以外のオススメの拡張機能や設定があれば、コメントで教えていただけると嬉しいです。

初版作成

-   files.candidateGuessEncodingsの紹介を追加
-   editor.wordSegmenterLocalesの紹介を追加
-   拡張機能のWord Dividerの紹介を削除 (VS Code本体に同等の機能を実現するeditor.wordSegmenterLocalesが追加されたため)