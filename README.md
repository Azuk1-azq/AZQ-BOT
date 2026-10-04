# 🛡️ AZQ BOT

サーバー管理をまるごとお任せできる、高機能Discord Bot。`bot.py` 1ファイルで動きます(discord.py 2.x)。
このソフトウェアはApache License 2.0で公開されています。

**[サーバーに導入する](https://discord.com/oauth2/authorize?client_id=1556124525459013713&permissions=8&integration_type=0&scope=bot+applications.commands)**

## 機能

| 分類 | 内容 |
|---|---|
| 🛡️ 荒らし対策 | 連投・同一メッセージ・メンション爆撃・招待リンク・NGワード・レイド(大量参加)を自動検知。削除、違反が重なるとタイムアウト |
| 📊 過疎検出 | `/kaso` でサーバーの活発度を診断。しきい値を下回ると自動アラート |
| 🧠 脳内メーカー | `/nounai`、ユーザー右クリック → アプリ → 脳内メーカー |
| 🖼️ 名言画像 | `/meigen`、メッセージ右クリック → アプリ → 名言画像にする(アイコンと@ID入り、丸ゴシック) |
| 🏓 ping | `/ping`(BOT速度)、`/ping target:example.com`(Webサイトの応答時間) |
| 🔨 モデレーション | kick / ban / unban / timeout / warn / purge / slowmode / lock / ロール付与・剥奪 |
| ⚙️ その他 | ログ、ウェルカムメッセージ、自動ロール、`/userinfo` `/serverinfo` `/avatar` `/help` |

## コマンド一覧

**誰でも使える**: `/kaso` `/nounai` `/meigen` `/ping` `/userinfo` `/serverinfo` `/avatar` `/help`

**管理者のみ**
- モデレーション: `/kick` `/ban` `/unban` `/timeout` `/untimeout` `/warn` `/warnings` `/clearwarns` `/purge` `/slowmode` `/lock` `/unlock` `/role_add` `/role_remove`
- 設定: `/config log_channel` `/config welcome` `/config autorole` `/config kaso` `/config automod_set` `/config ngword` `/config show`

## セットアップ

### 1. Discord Developer Portal の設定
1. アプリの **Bot** タブで、次の特権インテントを ON にして保存します。
   - **Server Members Intent**: 参加・退出の検知(ウェルカム、自動ロール、レイド検知)とメンバー数の集計
   - **Message Content Intent**: 荒らし判定のためのメッセージ本文の読み取り、編集・削除ログ
2. OAuth2 → URL Generator で、scope に `bot` と `applications.commands` を選んで招待します(上の導入URLでも可)。
3. BOTのロールは、管理対象のロールより**上**に配置します。

### 2. 設定を書き換える
`bot.py` の上部を編集します。

```python
TOKEN = "ここにBOTトークンを貼り付け"
DEV_GUILD_ID = ""   # サーバーIDを入れるとスラッシュコマンドがそのサーバーに即時反映(空ならグローバル)
DATA_DIR = "data"   # 設定の保存先フォルダ
```

### 3. 起動
```
python bot.py
```
`discord.py` と `Pillow` が無ければ、起動時に自動でインストールされます。

## SnapDeploy でのデプロイ
1. `bot.py` を **private** のGitHubリポジトリにpushします。
2. SnapDeploy でそのリポジトリとブランチを接続します。
3. 起動コマンドに `python bot.py` を指定してDeployします。

ホスティング側のヘルスチェック用に、`PORT`(既定8080)でHTTP応答も返します。

## データの保存
- サーバー設定と警告履歴は `data/guilds.json` に保存されます。
- 名言画像用のフォント(Zen Maru Gothic)は、初回に自動ダウンロードして `data/` に保存されます。
- コンテナの再デプロイで `data/` が消える環境では、設定が初期化されます。永続ストレージがあれば `DATA_DIR` をそこに向けてください。

## ホームページ・規約
`site/` フォルダに、ホームページ(`index.html`)、利用規約(`terms.html`)、プライバシーポリシー(`privacy.html`)があります。3つを同じ場所に公開してください。公開したURLは、Developer Portal の「Terms of Service URL」「Privacy Policy URL」に設定できます。

## お問い合わせ
Discord: `azuk1_dev`

AZQ BOT は非公式のBotであり、Discord Inc. とは関係ありません。
