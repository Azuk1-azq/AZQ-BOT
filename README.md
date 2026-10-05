# 🛡️ AZQ BOT

導入 : https://discord.com/oauth2/authorize?client_id=1556124525459013713&permissions=1099780189206&integration_type=0&scope=bot+applications.commands

荒らし対策・メンバー認証・サポートチケット・ロールパネル・過疎診断・モデレーションなど、サーバー管理に必要な機能を1つにまとめた高機能 Discord Bot です。`discord.py` 製で、`bot.py` 1ファイルで動きます。

- 📢 サポートサーバー: https://discord.gg/tAKTK9MYdc
  (メンテナンス・障害・アップデートのお知らせはここでのみ配信します)
- 🌐 公式サイト: `index.html` / `terms.html` / `privacy.html`

---

## 主な機能

| 機能 | 内容 |
|---|---|
| 🛡️ 荒らし対策 | 連投・同一投稿・メンション爆撃・招待リンク・NGワード・レイド(短時間の大量参加)を自動検知して対処 |
| 🔐 メンバー認証 | ボタン / 計算 / 画像CAPTCHA、アカウント年齢制限、未認証ロール、時間内に認証しない人のキック、レイド時の自動強化 |
| 🎫 サポートチケット | パネルのボタンから非公開チャンネルを自動作成。担当者、記録(.txt)の保存・DM送信、無操作での自動クローズ |
| 🎭 ロールパネル | ボタンを押すとロールを付与・もう一度押すと解除。「1つだけ選択」モードあり |
| 📊 過疎診断 | `/kaso` でサーバーの活発度を診断。しきい値を下回ると通知(過疎アラート) |
| 🧠 脳内メーカー | `/nounai` で診断画像を作成 |
| 🖼️ 名言画像 | `/meigen` やメッセージの右クリックでアイコン付きの名言画像を作成 |
| 🔨 モデレーション | kick / ban / timeout / warn(上限で自動タイムアウト) / purge / slowmode / lock など |
| 👋 そのほか | ウェルカムメッセージ、自動ロール、ログチャンネル、`/userinfo` `/serverinfo` `/avatar` |

---

## コマンド一覧

BOT導入後は `/help` でも確認できます。★は管理者のみ実行できます。

### 誰でも使える

| コマンド | 内容 |
|---|---|
| `/help` | コマンド一覧 |
| `/ping` | BOTの応答速度、またはWebサイトのping |
| `/kaso` | サーバーの過疎度を診断 |
| `/nounai`、右クリック「脳内メーカー」 | 脳内メーカー |
| `/meigen`、右クリック「名言画像にする」 | 名言画像を作成(他の人のアイコン・名前を使うには**本人の許可が必要**) |
| `/meigenprivacy` | 自分のアイコン・名前を名言画像に使ってよいかを設定 |
| `/userinfo` `/serverinfo` `/avatar` | 情報表示 |

### チケット内

| コマンド | 内容 |
|---|---|
| `/ticket close` | チケットを閉じる(**作成者・スタッフ・管理者**) — 記録を保存し、チャンネルを閲覧のみにする |
| `/ticket delete` | クローズ済みのチケットを削除(★**管理者のみ**) |
| `/ticket add` `remove` `rename` | メンバーの追加・削除、名前変更(スタッフ用) |

### 管理者向け(★)

| グループ | コマンド |
|---|---|
| `/verify` | `setup` `set` `panel` `status` `approve` `revoke` `bulk_approve` `raid` `disable` |
| `/ticketconfig` | `setup` `set` `staff` `panel` `block` `unblock` `status` `disable` |
| `/rolepanel` | `create` `add` `remove` `delete` `list` |
| `/config` | `log_channel` `welcome` `autorole` `kaso` `automod_set` `ngword` `warn_limit` `automod_ignore` `meigen` `show` |
| モデレーション | `/kick` `/ban` `/unban` `/timeout` `/untimeout` `/warn` `/warnings` `/unwarn` `/clearwarns` `/purge` `/slowmode` `/lock` `/unlock` `/role_add` `/role_remove` |

---

## セットアップ

### 1. BOTを作る

1. [Discord Developer Portal](https://discord.com/developers/applications) でアプリケーションを作成し、BOTを追加します。
2. **Bot** タブの **Privileged Gateway Intents** で、次の2つを **ON** にします。
   - **Message Content Intent**
   - **Server Members Intent**
3. BOTトークンをコピーします(他人に見せない・GitHubに上げない)。

### 2. サーバーに招待する

公式の招待URLです(自分で作ったBOTを使う場合は `client_id` を差し替えてください)。

```
https://discord.com/oauth2/authorize?client_id=1556124525459013713&permissions=1099780189206&integration_type=0&scope=bot+applications.commands
```

導入後は、**BOTのロールを、管理したいメンバー・付与したいロールより上**に移動してください。下にあると、ロールの付与・剥奪やキックなどが失敗します。

### 3. 起動する

Python 3.9 以上が必要です。

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
export DISCORD_TOKEN=ここにBOTトークン   # Windows: set DISCORD_TOKEN=...
python bot.py
```

`bot.py` 上部の `TOKEN = "YOUR-TOKEN"` に直接貼り付けても動きますが、環境変数のほうを推奨します。

### 4. 環境変数

| 変数 | 内容 | 既定 |
|---|---|---|
| `DISCORD_TOKEN` | BOTトークン(必須) | なし |
| `DEV_GUILD_ID` | 数字のサーバーID。指定するとそのサーバーだけコマンドが即時反映(開発用)。公開時は空 | 空(グローバル同期) |
| `DATA_DIR` | 設定の保存先 | `bot.py` と同じ場所の `data/` |
| `PORT` | ヘルスチェック用HTTPサーバーのポート。コンテナ環境向け | 未設定(起動しない) |

---

**1. トークンを `.env` に保存する**

```bash
echo 'DISCORD_TOKEN=ここにBOTトークン' > ~/myproject/.env
chmod 600 ~/myproject/.env
```

**2. `/etc/systemd/system/azq-bot.service` を作る**

```ini
[Unit]
Description=AZQ BOT (Discord)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=opc
WorkingDirectory=/home/opc/myproject
EnvironmentFile=/home/opc/myproject/.env
ExecStart=/home/opc/myproject/venv/bin/python /home/opc/myproject/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**3. 起動する**

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now azq-bot
journalctl -u azq-bot -f
```

ログに「ログイン: ○○」と出れば成功です。

---

## 保存されるデータ

`DATA_DIR`(既定は `data/`)に保存されます。**再起動で消えない場所**に置いてください。消えると、認証・チケット・ロールパネルなどの設定が初期化されます。

| ファイル | 内容 |
|---|---|
| `guilds.json` | サーバーごとの設定(認証・チケット・ロールパネル・警告など) |
| `user_prefs.json` | ユーザー個別の設定(名言画像の使用許可) |
| `bot.lock` | 二重起動を防ぐためのロック |
| フォントファイル | 名言画像用の日本語フォント(自動ダウンロード) |

BOTは会話の内容を保存しません。保存する内容の詳細は `privacy.html` を参照してください。

---

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| 「すでに別のプロセスでこのBOTが起動しています」と出て終了する | 同じ `data/` で別のBOTが動いています。`ps aux \| grep bot.py` で探し、`kill` で止めてください |
| コマンドが表示されない | 反映に時間がかかることがあります。開発中は `DEV_GUILD_ID` を指定すると即時反映されます |
| ロールの付与・キックに失敗する | BOTのロールが対象より下にないか、「ロールの管理」などの権限があるか確認してください |
| メンバーの参加やメッセージに反応しない | Developer Portal で **Message Content Intent** と **Server Members Intent** が ON か確認してください |
| 名言画像の文字が出ない | 日本語フォントを取得できていません。Oracle Linux では `sudo dnf install google-noto-sans-cjk-ttc-fonts` で入れられます |
| 再起動後にパネルのボタンが効かない | `data/guilds.json` が消えていないか確認してください(保存先を再起動で消えない場所にする) |

---

## 権限について

BOTが使う主な権限と用途です。

| 権限 | 用途 |
|---|---|
| チャンネルを見る / メッセージ履歴を読む | 荒らし判定、過疎診断の集計、チケット記録の作成 |
| メッセージを送信 / 埋め込みリンク / ファイルを添付 | ログ、ウェルカム、各コマンドの結果、パネル、記録(.txt)の送信 |
| メッセージの管理 | 荒らしメッセージの削除、`/purge` |
| メンバーをキック / BAN / メンバーをタイムアウト | モデレーション、未認証キック、警告上限での自動タイムアウト |
| ロールの管理 | 自動ロール、認証ロール、ロールパネル、`/role_add` `/role_remove` |
| チャンネルの管理 | `/slowmode` `/lock` `/unlock`、チケットチャンネルの作成・ロック・削除 |

---

## リンク

- サポートサーバー: https://discord.gg/tAKTK9MYdc
- GitHub: https://github.com/Azuk1-azq/AZQ-BOT
