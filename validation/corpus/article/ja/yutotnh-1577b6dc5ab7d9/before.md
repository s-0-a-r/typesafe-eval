---
title: "Visual Studio Code (VS Code)のオススメ設定と拡張機能の紹介"
emoji: "♾️"
type: "tech"
topics: ["vscode"]
published: true
published_at: 2024-04-01 06:00
---

## はじめに

本記事ではC言語やTypeScriptなど特定の言語を使う際に便利な設定と拡張機能ではなく、言語にかかわらずVS Codeで使えるオススメの設定と拡張機能を紹介します。

個人的な好みや、私の置かれている環境が要因の設定も含まれているため、すべての設定が必ずしもオススメとは限りませんが、参考にしていただければ幸いです。

更新履歴は[こちら](#更新履歴)に記載しています。

## 設定

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

### editor

#### editor.bracketPairColorization.enabled

括弧の対応を色分けして表示します。

![Bracket pair colorizationのON/OFFの比較画像](/images/1577b6dc5ab7d9/on-off-comparison.drawio.webp)

画像出典: [Bracket pair colorization 10,000x faster](https://code.visualstudio.com/blogs/2021/09/29/bracket-pair-colorization)

```json:settings.json
"editor.bracketPairColorization.enabled": true
```

本設定が登場する前は、同様の機能を`Bracket Pair Colorizer`や`Bracket Pair Colorizer 2`という拡張機能を入れて実現していましたが、拡張機能のインストールは必要なくなりました。

#### editor.cursorBlinking

カーソルのアニメーション方式を設定します。

`expand`にすると、カーソルが拡大縮小するアニメーションになるため、カッコよくオススメです。

![editor.cursorBlinkingをexpandにしたときの動画](/images/1577b6dc5ab7d9/editor-cursorBlinking-expand.webp)

```json:settings.json
"editor.cursorBlinking": "expand"
```

#### editor.cursorSmoothCaretAnimation

ONにすることでカーソルの移動時にアニメーションを滑らかにします。

```json:settings.json
"editor.cursorSmoothCaretAnimation": "on"
```

#### editor.cursorStyle

カーソルの形状を`line-thin`として、デフォルト (`line`) より細くします。
補足することで、カーソル周辺の文字が見やすくなります。

##### editor.cursorStyleをlineにしたとき

![editor.cursorStyle"をlineにしたときの画像](/images/1577b6dc5ab7d9/editor-cursorStyle-line.webp)

##### editor.cursorStyleをline-thinにしたとき

![editor.cursorStyleをline-thinにしたときの画像](/images/1577b6dc5ab7d9/editor-cursorStyle-line-thin.webp)

```json:settings.json
"editor.cursorStyle": "line-thin"
```

#### editor.dragAndDrop

デフォルトは`true`ですが、`false`にすることで、テキストをドラッグ＆ドロップで移動できなくなります。

私はこの機能が邪魔に感じることがあるため、OFFにしています。

```json:settings.json
"editor.dragAndDrop": false
```

#### editor.fontFamily

等幅フォントとしてMoralerspaceを使っているので、最優先のフォントとして、`Moralerspace Neon HWNF`を設定しています。

Moralerspaceについては、以下のリンクからダウンロードできます。

@[card](https://github.com/yuru7/moralerspace)

```json:settings.json
"editor.fontFamily": "'Moralerspace Neon HWNF', Consolas, 'Courier New', monospace"
```

#### editor.guides.bracketPairs

括弧の対応を表示します。

![Bracket pairsの表示画像](/images/1577b6dc5ab7d9/bracket-pair-guides.webp)

画像出典: [Improved bracket pair guides](https://code.visualstudio.com/updates/v1_62#_improved-bracket-pair-guides)

```json:settings.json
"editor.guides.bracketPairs": true
```

#### editor.minimap.maxColumn

ミニマップの最大表示列数を設定します。

デフォルトは`120`ですが`80`にすることで、ミニマップの幅を狭くしてミニマップ以外の表示幅を増やします。

個人的には、`80`もあれば全体のなんとなくの構造が把握できるので、`80`に設定しています。

```json:settings.json
"editor.minimap.maxColumn": 80
```

#### editor.minimap.showSlider

ミニマップのスライダーを常に表示します。

```json:settings.json
"editor.minimap.showSlider": "always"
```

#### editor.mouseWheelZoom

Ctrlキーを押しながらマウスホイールを使用してエディターのズームを有効にします。

```json:settings.json
"editor.mouseWheelZoom": true
```

#### editor.renderLineHighlight

カーソルがある行をハイライト表示する設定です。

デフォルトは`line`ですが、`all`にすることで、カーソルがある行全体をハイライト表示します。

違いが分かりにくいですが、`all`にすると以下の画像のように行番号を含むカーソルがある行全体がハイライト表示されます。

##### editor.renderLineHighlightをlineにしたとき

![editor.renderLineHighlightをlineにしたときの画像](/images/1577b6dc5ab7d9/editor-renderLineHighlight-line.webp)

##### editor.renderLineHighlightをallにしたとき

![editor.renderLineHighlightをallにしたときの画像](/images/1577b6dc5ab7d9/editor-renderLineHighlight-all.webp)

```json:settings.json
"editor.renderLineHighlight": "all"
```

#### editor.renderWhitespace

空白文字が常に表示されるようにします。

具体的には、赤線のようにスペースは薄い"・"のような表示になり、タブは薄い"→"のような表示になります。

編集しているファイルのインデントが混在している場合、空白文字を表示することで、インデントの混在を確認しやすくなります。

![editor.renderWhitespaceをallにしたときの画像](/images/1577b6dc5ab7d9/editor-renderWhitespace-all.webp)

```json:settings.json
"editor.renderWhitespace": "all"
```

#### editor.showFoldingControls

画像赤線のように、折りたたみコントロールが常に表示されます。

![editor.showFoldingControlsをalwaysにしたときの画像](/images/1577b6dc5ab7d9/editor-showFoldingControls-always.webp)

```json:settings.json
"editor.showFoldingControls": "always"
```

#### editor.smoothScrolling

`true`にすることで、スクロール時のアニメーションを滑らかにします。

```json:settings.json
"editor.smoothScrolling": true
```

#### editor.wordSegmenterLocales

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

#### editor.wrappingIndent

`indent`にすることで、折り返し行のインデントが元の行のインデント+1になります。

デフォルトの`same`だと、折り返し行のインデントが元の行のインデントと同じになります。

##### editor.wrappingIndentをsameにしたとき

![editor.wrappingIndentをsameにしたときの画像](/images/1577b6dc5ab7d9/editor-wrappingIndent-same.webp)

##### editor.wrappingIndentをindentにしたとき

![editor.wrappingIndentをindentにしたときの画像](/images/1577b6dc5ab7d9/editor-wrappingIndent-indent.webp)

```json:settings.json
"editor.wrappingIndent": "indent"
```

### explorer

#### explorer.confirmDelete

Windowsなどファイルやフォルダーを削除してゴミ箱にファイルを送る場合、確認ダイアログを表示しないようにします。

間違ってファイルを削除しても、Ctrl+Zで元に戻せるので、確認ダイアログを表示しないようにしています。

```json:settings.json
"explorer.confirmDelete": false
```

#### confirmDragAndDrop

ファイルをドラッグ＆ドロップで移動する際に確認ダイアログを表示しないようにします。

これも間違ってファイルを移動しても、Ctrl+Zで元に戻せるので、確認ダイアログを表示しないようにしています。

```json:settings.json
"explorer.confirmDragAndDrop": false
```

### files

#### files.autoGuessEncoding

ファイルのエンコーディングを自動で推測するようにします。

私は複数のエンコーディングを使うことがあるため、推測機能をONにしています。

推測機能は完璧ではなため別のエンコーディングとして判定されることがありますが、[VS Code #208550](https://github.com/microsoft/vscode/pull/208550)がマージされれば、新規設定によって推測機能が改善されるため、今後のアップデートに期待です。

もしUTF-8しか使わない場合は、OFFにしておくとエンコーディングの誤検知を防げます。

```json:settings.json
"files.autoGuessEncoding": true
```

#### files.candidateGuessEncodings

files.autoGuessEncodingにtrueを指定した時にファイルのエンコーディングを推測する際の候補として使うエンコーディングを設定します。

これを設定することで、推測機能で日本語のファイルをWindows 1252などと誤検知してしまうことを防ぐことができます。

私はUTF-8、Shift_JIS、EUC-JPを使うことが多いため、これらのエンコーディングを候補として設定しています。

```json:settings.json
"files.candidateGuessEncodings": ["utf8", "shiftjis", "eucjp"],
```

本設定に関しては私がVS Codeに追加したため、不具合がある場合は本記事のコメントか[VS CodeのIssue](https://github.com/microsoft/vscode/issues)で報告していただけると幸いです。

#### files.insertFinalNewline

ファイルの保存時に末尾に改行を挿入します。

```json:settings.json
"files.insertFinalNewline": true
```

#### files.trimFinalNewlines

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

#### files.trimTrailingWhitespace

ファイルの保存時に行末の空白文字を削除します。

```json:settings.json
"files.trimTrailingWhitespace": true
```

### git

#### git.autofetch

定期的に自動ですべてのリモートリポジトリから最新の情報を取得します。

もしfetch時にパスワードを求められるような場合は`false`にして無効にしてください。

```json:settings.json
"git.autofetch": "all"
```

#### git.confirmSync

同期時に確認ダイアログを表示しないようにします。

個人的には同期しても問題ないため、確認ダイアログを表示しないようにしています。

```json:settings.json
"git.confirmSync": false
```

#### git.pruneOnFetch

`true`にすることで、fetch時にリモートリポジトリから削除されたブランチをローカルリポジトリから削除します。

```json:settings.json
"git.pruneOnFetch": true
```

#### git.suggestSmartCommit

ステージングされた変更がない場合にすべての変更をコミットするスマートコミットを提案する機能を無効にします。

すべての変更をコミットすることは、意図しない変更をコミットする可能性があるため、OFFにしています。

```json:settings.json
"git.suggestSmartCommit": false
```

### scm

#### scm.alwaysShowRepositories

`true`にすることで、サイドバーにリポジトリを常に表示します。

画像のようにリポジトリの状態が一目でわかるため、リポジトリを常に表示することをオススメします。

![scm.alwaysShowRepositoriesをtrueにしたときの画像](/images/1577b6dc5ab7d9/scm-alwaysShowRepositories-true.webp)

```json:settings.json
"scm.alwaysShowRepositories": true
```

#### scm.defaultViewMode

デフォルトの変更ファイル一覧の表示をツリー表示にします。

デフォルトは`list`ですが、`tree`にすることで、変更ファイル一覧をツリー表示にします。

##### scm.defaultViewModeをlistにしたとき

![scm.defaultViewModeをlistにしたときの画像](/images/1577b6dc5ab7d9/scm-defaultViewMode-list.webp)

##### scm.defaultViewModeをtreeにしたとき

![scm.defaultViewModeをtreeにしたときの画像](/images/1577b6dc5ab7d9/scm-defaultViewMode-tree.webp)

```json:settings.json
"scm.defaultViewMode": "tree"
```

#### scm.diffDecorationsGutterWidth

差分の行数を表示するガターの幅を設定します。

デフォルトは`3`ですが、`5`にすることで、差分がある行をよりわかりやすく表示します。

##### scm.diffDecorationsGutterWidthを3にしたとき

![scm.diffDecorationsGutterWidthを3にしたときの画像](/images/1577b6dc5ab7d9/scm-diffDecorationsGutterWidth-3.webp)

##### scm.diffDecorationsGutterWidthを5にしたとき

![scm.diffDecorationsGutterWidthを5にしたときの画像](/images/1577b6dc5ab7d9/scm-diffDecorationsGutterWidth-5.webp)

```json:settings.json
"scm.diffDecorationsGutterWidth": 5
```

#### scm.inputFontFamily

デフォルトだとコミットメッセージの入力箇所がエディターと異なるフォントになるため、エディターと同じフォントに設定しています。

画像の"ABCDEFG"の個所が適用箇所です。

![scm.inputFontFamilyをeditorにしたときの画像](/images/1577b6dc5ab7d9/scm-inputFontFamily-editor.webp)

```json:settings.json
"scm.inputFontFamily": "editor"
```

#### scm.inputFontSize

デフォルトの13だと少し小さく感じるため、14に設定しています。

```json:settings.json
"scm.inputFontSize": 14
```

#### search.showLineNumbers

画像の赤線のようにサイドバーでの検索結果に行番号を表示します。

![search.showLineNumbersをtrueにしたときの画像](/images/1577b6dc5ab7d9/search-showLineNumbers-true.webp)

```json:settings.json
"search.showLineNumbers": true
```

### terminal

#### terminal.integrated.cursorBlinking

ターミナルのカーソルを点滅させます。

点滅させたほうがカーソルの位置がわかりやすいため、点滅させるようにしています。

```json:settings.json
"terminal.integrated.cursorBlinking": true
```

#### terminal.integrated.cursorStyle

ターミナルのカーソルの形状を`line`に設定します。

デフォルトの`block`だと、個人的に文字の間にカーソルがあるときに文字の削除や挿入の位置がわかりにくいため、`line`に設定しています。

##### terminal.integrated.cursorStyleをblockにしたとき

![terminal.integrated.cursorStyleをblockにしたときの画像](/images/1577b6dc5ab7d9/terminal-integrated-cursorStyle-block.webp)

##### terminal.integrated.cursorStyleをlineにしたとき

![terminal.integrated.cursorStyleをlineにしたときの画像](/images/1577b6dc5ab7d9/terminal-integrated-cursorStyle-line.webp)

```json:settings.json
"terminal.integrated.cursorStyle": "line"
```

#### terminal.integrated.enableImages

ターミナルで画像を表示できるようにします。

有効にすると、img2sixelなどの画像表示機能を使うことで、ターミナルで画像を表示できるようになります。

![terminal.integrated.enableImagesをtrueにしたときの画像](/images/1577b6dc5ab7d9/terminal-integrated-enableImages-true.webp)

```json:settings.json
"terminal.integrated.enableImages": true
```

#### terminal.integrated.enableVisualBel

ターミナルでのベルがなったときに、画像の赤線箇所のようにターミナル名の横にベルマークを表示させます。

音を鳴らさないような環境で作業をすることがあるため、ベルマークを表示させるようにしています。

![terminal.integrated.enableVisualBellをtrueにしたときの画像](/images/1577b6dc5ab7d9/terminal-integrated-enableVisualBel-true.webp)

```json:settings.json
"terminal.integrated.enableVisualBell": false
```

#### terminal.integrated.mouseWheelZoom

ターミナルでCtrlキーを押しながらマウスホイールを使用してエディターのズームを有効にします。

```json:settings.json
"terminal.integrated.mouseWheelZoom": true
```

#### terminal.integrated.smoothScrolling

ターミナルでスクロール時のアニメーションを滑らかにします。

デフォルトのfalseだとスクロールがカクカクするため、違和感を覚えると思います。

```json:settings.json
"terminal.integrated.smoothScrolling": true
```

### workbench

#### workbench.colorTheme

好みのテーマに変更してください。

私は、各要素の区切りがはっきりしている`Default High Contrast`を使っています。

ただし、テーマによっては特定の要素が見づらくなることがあるため、何らかの要素が見づらくなった場合は、一時的に他のテーマに変更して閲覧することをオススメします。

```json:settings.json
"workbench.colorTheme": "Default High Contrast"
```

#### workbench.editor.closeOnFileDelete

外部要因でファイルが削除されたときにエディターを閉じるかどうかを設定します。

デフォルトでは、端末でファイルを削除した時に、エディターでそのファイルを開いてた時にファイルを保存するとファイルが復活するため、ファイルを削除したときにエディターを閉じるようにしています。

```json:settings.json
"workbench.editor.closeOnFileDelete": true
```

#### workbench.editor.scrollToSwitchTabs

エディターのタブ部分でマウスのスクロールを行うと、タブが切り替わるようにします。

```json:settings.json
"workbench.editor.scrollToSwitchTabs": true
```

#### workbench.editor.wrapTabs

タブが画面幅を超えたときに折り返すようにします。

デフォルトの`false`だと、タブが画面幅を超えたときに折り返さないため、タブで開いているファイルを把握しにくくなります。

##### workbench.editor.wrapTabsをfalseにしたとき

![workbench.editor.wrapTabsをfalseにしたときの画像](/images/1577b6dc5ab7d9/workbench-editor-wrapTabs-false.webp)

##### workbench.editor.wrapTabsをtrueにしたとき

![workbench.editor.wrapTabsをtrueにしたときの画像](/images/1577b6dc5ab7d9/workbench-editor-wrapTabs-true.webp)

```json:settings.json
"workbench.editor.wrapTabs": true
```

#### workbench.list.smoothScrolling

`true`にすることで、サイドバーのスクロール時にアニメーション使用して滑らかにします。

```json:settings.json
"workbench.list.smoothScrolling": true
```

#### workbench.view.alwaysShowHeaderActions

`true`にすることで、サイドバーのヘッダーアクションを常に表示します。

デフォルトだとマウスを合わせると表示されるため、マウスをのせない状態だと何ができるのかわかりません。

そのため、常に表示させるようにしています。

いくつかの表示に影響しますが、たとえばエクスプローラーのヘッダーアクションは以下の画像の赤線箇所の表示に影響します。

![workbench.view.alwaysShowHeaderActionsをtrueにしたときの画像](/images/1577b6dc5ab7d9/workbench-view-alwaysShowHeaderActions-true.webp)

```json:settings.json
"workbench.view.alwaysShowHeaderActions": true
```

## キーボードショートカット

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

### エンコーディングを変更

複数エンコーディングを扱うことがある際に頻繁にエンコーディングを変更するため、ショートカットを設定します。

```json:keybindings.json
{
  "key": "ctrl+oem_1 ctrl+oem_1",
  "command": "workbench.action.editor.changeEncoding"
},
```

### ターミナルへの移動

`Ctrl+0`でターミナルに移動できるように設定します。

WindowsやLinuxではターミナル画面に移動するためのショートカットがないため、ターミナル画面に移動するためのショートカットを設定しています。

```json:keybindings.json
{
  "key": "ctrl+0",
  "command": "workbench.action.terminal.focus"
},
```

## 拡張機能

各拡張機能の設定は製品ページに飛んだ方がわかりやすいため、各拡張機能の製品ページへのリンクを貼っています。

### Bookmarks

ファイルにブックマークをつけることができる拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=alefragnani.Bookmarks)

### Bracket Lens

括弧の対応を表示する拡張機能です。

インストール数は比較的少ないですが、非常に便利な拡張機能です。

ただし、利用シーンによってはかなり処理が重くなることがあるため、VS Codeが重くなった場合は、一時的に無効にすることをオススメします。

@[card](https://marketplace.visualstudio.com/items?itemName=wraith13.bracket-lens)

### Code Spell Checker

スペルミスをチェックする拡張機能です。

固有名詞や技術用語などスペルミスと判定されることがありますが、その場合は単語を登録することで、スペルミスと判定されなくなります。

@[card](https://marketplace.visualstudio.com/items?itemName=streetsidesoftware.code-spell-checker)

### Edit csv

CSVファイルを編集する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=janisdd.vscode-edit-csv)

### EditorConfig for VS Code

`.editorconfig`ファイルを読み込んで、エディターの設定を変更する拡張機能です。

`.editorconfig`ファイルを使っている場合は、この拡張機能を使うことで、`.editorconfig`ファイルに記述した設定をVS Codeに反映させることができます。

@[card](https://marketplace.visualstudio.com/items?itemName=EditorConfig.EditorConfig)

### Excel Viewer

ExcelファイルやCSVファイルをVS Codeで閲覧する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=GrapeCity.gc-excelviewer)

### Git Graph

Gitの履歴をグラフで表示する拡張機能です。

検索もしやすいため、Gitの履歴を確認する際に便利です。

@[card](https://marketplace.visualstudio.com/items?itemName=mhutchie.git-graph)

日付のフォーマットが日本人にはわかりにくいため、以下の設定に変更してわかりやすい形にします。

```json:settings.json
"git-graph.date.format": "ISO Date & Time"
```

### Git History

Gitの履歴を表示する拡張機能です。

個人的にはGit Graphはリポジトリ全体の履歴を確認するのに使い、Git Historyはファイルごとの履歴を確認するのに使っています。

@[card](https://marketplace.visualstudio.com/items?itemName=donjayamanne.githistory)

### GitHub Actions

GitHub Actions関連の機能を提供する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-github-actions)

### GitHub Pull Requests and Issues

GitHubのプルリクエストをVS Codeで直接管理できる拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-pull-request-github)

### GitLens

VS CodeデフォルトのGit機能を強化する拡張機能です。

また、編集中のファイルの各行の変更履歴を表示する機能があるため、コードの変更履歴を確認する際に便利です。

@[card](https://marketplace.visualstudio.com/items?itemName=eamodio.gitlens)

### Hex Editor

バイナリファイルを16進数で表示する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=ms-vscode.hexeditor)

### Japanese Language Pack for Visual Studio Code

VS Codeを日本語化する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=MS-CEINTL.vscode-language-pack-ja)

### Material Icon Theme

ファイルアイコンをデフォルトよりもわかりやすいアイコンに変更する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=PKief.material-icon-theme)

アイコンを変更するには、拡張機能のインストール後、VS Codeの設定で以下の設定を追加してください。

```json:settings.json
"workbench.iconTheme": "material-icon-theme"
```

### Output Colorizer

VS Codeの出力に色をつける拡張機能です。

視認性が向上するため、出力を見る機会が多い方にオススメです。

@[card](https://marketplace.visualstudio.com/items?itemName=IBM.output-colorizer)

### Path Intellisense

ファイルパスを入力する際に補完機能を提供する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=christian-kohler.path-intellisense)

### Peacock

VS Codeのテーマをプロジェクトごとに変更する拡張機能です。

同時に複数のプロジェクトを開いている場合、どのプロジェクトを編集しているかわかりやすくなります。

@[card](https://marketplace.visualstudio.com/items?itemName=johnpapa.vscode-peacock)

### Rainbow CSV

CSVファイルの列を色分けして表示する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=mechatroner.rainbow-csv)

### Render Line Endings

行末の改行コードをファイル内で可視化する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=medo64.render-crlf)

### Resource Monitor

メモリ使用量やCPU使用量を表示する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=mutantdino.resourcemonitor)

### Todo Tree

TODOコメントを一覧表示する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=Gruntfuggly.todo-tree)

### Trailing Spaces

行末の余分な空白を表示する拡張機能です。

`"files.trimTrailingWhitespace": true`を設定している場合には保存時に自動で削除されるため、あまり必要ないかもしれませんが、環境によって`false`にしている場合もあるため、必要に応じてインストールしてください。

@[card](https://marketplace.visualstudio.com/items?itemName=shardulm94.trailing-spaces)

### テキスト校正くん

日本語の文章を校正する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=ICS.japanese-proofreading)

### 表外漢字チェッカー

表外漢字を強調表示する拡張機能です。

@[card](https://marketplace.visualstudio.com/items?itemName=noy-shimotsuki.hyogai-kanji-checker)

## まとめ

今回紹介した以外のオススメの拡張機能や設定があれば、コメントで教えていただけると嬉しいです。

## 更新履歴

### 2024-04-01

初版作成

### 2024-07-06

-   files.candidateGuessEncodingsの紹介を追加
-   editor.wordSegmenterLocalesの紹介を追加
-   拡張機能のWord Dividerの紹介を削除 (VS Code本体に同等の機能を実現するeditor.wordSegmenterLocalesが追加されたため)
