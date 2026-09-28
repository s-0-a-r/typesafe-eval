---
title: "Pull Request駆動で小説を開発する"
emoji: "📜"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["GitHub","textlint","Tech","小説","GitHubActions"]
published: true
published_at: 2022-05-20 14:45
---
##  謝辞
先日、こんな記事を書いた。
https://zenn.dev/haoblackj/articles/8cbadb26ca16e4
ありがたいことに多くの反応をいただいた。
この場を借りて御礼申し上げる。

# 要点
- Pull Request 駆動で小説を開発する
  - 情報整理の場としての Pull Request
  - 校正の場としての Pull Request

# Pull Request 駆動で小説を開発する
:::message
ここでは敢えて平易な表現を優先する。
:::
小説を書いて GitHub にアップロード(コミット→プッシュ)していく中で、「こういう表現にしたほうがよくなるんじゃないか」と思いつくことがある。
GitHub ではいつでも過去のデータにアクセスして文章を取り戻せるから、大掛かりな変更や修正も気軽にできる。

だが、更新頻度の高いファイルほど、取り戻したい特定の時点を探し出す手間が増える。
コミットメッセージを記載していたとしても、同じ箇所を別の時点で修正している可能性がある。

あなたがコマンドラインを使うのに抵抗がなければ、こういった検索方法もある。
https://solutionware.jp/blog/2021/01/29/git-%E3%81%AE%E5%B1%A5%E6%AD%B4%E3%82%92%E6%9F%94%E8%BB%9F%E3%81%AB%E6%A4%9C%E7%B4%A2%E3%81%99%E3%82%8B/
VSCode を使っているなら、こういう記事も参考になる。
https://atelier-light.com/blog/vscode-git-history/


GitHub に残っていくコミット履歴が、やがて快適さを妨げる負荷になる。
それを回避するために提案するのが、Pull Request 駆動での執筆だ。

##  Pull Request とは
> 分散バージョン管理システム（VCS）の機能の一つで、コードなどを追加・修正した際、本体への反映を他の開発者に依頼する機能。「変更を本人以外がレビューしてから反映させる」という手順を容易に実現することができる。
(プルリクエスト（マージリクエスト）とは - IT 用語辞典 e-Words 2021 年 2 月 7 日更新)

https://e-words.jp/w/%E3%83%97%E3%83%AB%E3%83%AA%E3%82%AF%E3%82%A8%E3%82%B9%E3%83%88.html#:~:text=%E3%83%97%E3%83%AB%E3%83%AA%E3%82%AF%E3%82%A8%E3%82%B9%E3%83%88%E3%81%A8%E3%81%AF%E3%80%81%E5%88%86%E6%95%A3,%E5%AE%9F%E7%8F%BE%E3%81%99%E3%82%8B%E3%81%93%E3%81%A8%E3%81%8C%E3%81%A7%E3%81%8D%E3%82%8B%E3%80%82

要は、過去のある時点の原稿と、たった今修正した原稿を比較できる仕組みだ。
比較した後、修正後の原稿を**正**として手軽にコミット(**マージ**)できる機能も備わっている。

##  Pull Request の使い方
1.  **元ブランチから修正用ブランチを発行する**

GitHub は(正確には Git は)コミット履歴を枝分かれさせ、各々を比較する機能を備えている。
この分かれた枝それぞれのことをブランチと呼ぶ。

2.  **修正用ブランチ上で原稿を修正する**

原稿の修正作業に説明は不要のはずだ。
適宜修正し、コミットし、プッシュする。
コミット履歴は修正用ブランチ上に記録されていく。

3.  **修正用ブランチから元ブランチに対して Pull Request を発行する**

ある程度コミット履歴が蓄積されたら、いよいよ Pull Request を発行する。
修正用ブランチ上に記録されたコミットが一覧として表示され、最終的なファイルの変更箇所なども簡単に確認できるようになる。

4.  **Pull Request で修正を適用するか検討し、必要に応じて原稿を再修正する**

ここも説明は不要のはずだ。
適宜修正し、修正用ブランチにコミットし、プッシュする。
修正用ブランチにコミットするたび、Pull Request は自動で更新されていく。
(Pull Request 発行後、元ブランチにコミットしても自動では反映されないので注意)

5.  **修正が完了したら、修正用ブランチを元ブランチにマージする**

「Merge pull request」からマージすることで、修正用ブランチ上で修正した原稿が元ブランチに保存される。
必要に応じて修正用ブランチを削除したり、継続して使用したりする。
そのあたりの思想は千差万別なので、ここで言及はしない。
**GitHub Flow**で検索すると頭が痛くなること請け合いなので、検索してみるといい。


##  情報整理の場としての Pull Request
上記の流れで Pull Request を使っていくと、自ずとコミット履歴は分割・整理されていき、検索性が上がる。
コミット履歴を直接確認するのではなく、当時作成した Pull Request から辿ればいいからだ。
Pull Request にはコメントを投稿する機能もあるから、それらを駆使すれば更にわかりやすく整理できる。
私の場合は、自分の原稿に対するツッコミや悩んでいることを適当に投稿している。

Pull Request のメリットは、コミット履歴の分割に留まらない。
ある一時点からのコミット履歴が積み重なることで、直近のペースが目に見えてわかるようになる。
仮に原稿修正のペースが落ちてしまっても、コメントに案レベルの修正を書き込むことで進捗を生み出せる。
思いついた設定や伏線をコメントすることで、プロットへ転記する前に忘れてしまう悲劇を回避できる。

Pull Request はファイルごとに作成してもいいし、修正したい内容に応じて作成してもいい。
Issue にするほどでもない課題でも、Pull Request のコメントなら気軽に書き込んでしまっていい。
適当に作成して、適当に原稿を修正して、適当に情報を放り込んで、適当にマージする。
マージしたあとも Pull Request 自体は閲覧できるから、適宜そこから必要な情報にアクセスすればよい。

##  校正の場としての Pull Request
先の記事で textlint を紹介した。
https://www.npmjs.com/package/textlint
VSCode を使っているなら、vscode-textlint を使って自動で赤入れをしてもらえばいい。
https://marketplace.visualstudio.com/items?itemName=taichi.vscode-textlint
だがブラウザや素のメモ帳(notepad.exe)など、textlint が介入できない環境は多々ある。

その環境下でも校正をそれなりに自動化できるのが、 GitHub Actions と Reviewdog である。
:::message
ブラウザに入力した文字列に対して textlint を適用する Chrome 拡張機能もあるが、今回は割愛する。
:::

### Reviewdog を飼う
Reviewdog とは、text**lint** を含む各種 lint ツール(linter という)の吐いた結果を Pull Request にコメントしてくれる賢い犬だ。
https://github.com/reviewdog/reviewdog

Reviewdog をリポジトリに**飼う**ことで、ブラウザや textlint 非対応のエディタからの編集でも textlint の恩恵を受けられるのだ。

### 導入手順
1.  `.\github\workflow\reviewdog.yml` **を作成し、以下の内容をペースト**
```yml:reviewdog.yml
name: reviewdog
on: [pull_request]
jobs:
  textlint:
    name: runner / textlint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
        with:
          submodules: true
      - name: textlint-github-pr-review
        uses: tsuyoshicho/action-textlint@v3
        with:
          github_token: ${{ secrets.github_token }}
          reporter: github-pr-review
          level: warning
          textlint_flags: "episodes/**"
```
2.  **デフォルトブランチ(通常はmaster または main)に コミット & プッシュ**
これで導入は完了だ。

自動修正に対応した textlint ルール(句読点修正、空白抜け、全半角など)では、Pull Request に対するレビューとして修正サジェストを投稿してくれる。
表示された場合は Commit suggestion から、校正したファイルをそのままコミットできる。
自動修正に対応していないものは再びコメントとして投稿されるため、言われるがまま直せばよろしい。

※2022 年 5 月 9 日追記
Commit suggestion については、以下の記事が画像などもあり、わかりやすい。
https://blog.wyrd.co.jp/2021/11/04/%E3%81%93%E3%82%93%E3%81%AA%E6%A9%9F%E8%83%BD%E3%81%82%E3%81%A3%E3%81%9F%E3%82%93%E3%81%A0-github-suggested-changes%E7%AF%87/

注意点として、導入完了後に作成された Pull Request から校正が走るという点だ。
私はこれで 30 分ほど無駄にした。

Reviewdog のおかげで、出先でちょこちょこ原稿を修正し続けて、表記規則がめちゃめちゃなまま放置、ということも防げるようになった。
ちなみに iPad で GitHub を使うなら、Safari で GitHub にログインして使用するか、2000 円少し課金することを前提に下記アプリを使うといい。
https://apps.apple.com/jp/app/working-copy-git-client/id896694807

:::message
GitHub Codespaces を用いることで、アプリを購入することなく GitHub 下のリポジトリで作業できる。
ブラウザ上で VSCode ライクな UI を使える。
VSCode の設定や拡張機能も流用できる。
下記の記事に、参考記事含め詳しく書いている。

(2022 年 8 月 26 日追記)
:::
https://zenn.dev/haoblackj/articles/novel-codespaces

# まとめ
Pull Request 駆動で小説を執筆するようになると、情報をよりわかりやすく集約できたり、エディタとは別の校正プラットフォームを用意できたりする。
特に後段で書いた Reviewdog を導入すれば、VSCode をインストールできない環境でも手軽に執筆できるようになる。
インターネットが繋がり、文字を入力できる環境であれば、どこでも小説を書けるようになった。

これで各小説投稿サイトが GitHub Actions からのデプロイに対応すれば、私としては言うことなしである。
https://github.com/fuji-nakahara/jekyll-deploy-shosetsu
↑のようなものもあるが、今も動くのかは定かではない。

# 後書きに代えて

実は、Git や GitHub を用いて小説を執筆するというテーマには元ネタがある。
下に掲げる読書猿さんの記事だ。

https://readingmonkey.blog.fc2.com/blog-entry-717.html

この記事では小説をソースコードと捉え、コメントやコメントアウトを用いて情報を都度記録するという試みを紹介している。
私もこういった手法で工夫していたのだが、どうしても情報の一覧性に欠けるところがあった。
一方で、情報を原稿と密に記録できるというメリットは捨てがたい。
これを保ちつつ一覧性を確保するよう追求していった結果、GitHub に落ち着いた。


他にも GitHub Actions で Issue を整理したり、集団で執筆する際に原稿レビューを自動で依頼するようにしたりしているが、それは本職開発者の方々がたっぷり記事を書いてくださっている。
小説を書くという用途ならではの特色が見えたら、また記事にする予定だ。