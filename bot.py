import asyncio
import atexit
import bisect
import copy
import functools
import hashlib
import hmac
import ipaddress
import io
import ipaddress
import json
import logging
import os
import platform
import random
import re
import secrets
import signal
import threading
import time
from array import array
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional
from types import SimpleNamespace
from urllib.parse import quote, urlparse

import subprocess
import sys

for _mod, _pkg in (("discord", "discord.py>=2.4,<3"), ("PIL", "pillow")):
    try:
        __import__(_mod)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", _pkg])

import discord
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

import aiohttp
from aiohttp import web
from discord import app_commands
from discord.ext import commands, tasks


TOKEN = "YOUR-TOKEN"
TOKEN = os.getenv("DISCORD_TOKEN") or TOKEN
DEV_GUILD_ID = ""
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID", DEV_GUILD_ID).strip()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_URL = (os.getenv("DASHBOARD_URL") or "").strip().rstrip("/")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET") or ""
TLS_CERT = (os.getenv("TLS_CERT") or "").strip()
TLS_KEY = (os.getenv("TLS_KEY") or "").strip()
TLS_READY = bool(TLS_CERT and TLS_KEY)
WEB_URL = (os.getenv("WEB_URL") or "").strip().rstrip("/")
if WEB_URL and not re.match(r"^https?://", WEB_URL, re.I):
    WEB_URL = ("https://" if TLS_READY else "http://") + WEB_URL
WEB_READY = bool(WEB_URL)
RECAPTCHA_SITE_KEY = (os.getenv("RECAPTCHA_SITE_KEY") or "").strip()
RECAPTCHA_SECRET_KEY = (os.getenv("RECAPTCHA_SECRET_KEY") or "").strip()
RECAPTCHA_READY = bool(RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY)
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
VPN_LIST_URLS = [u for u in (os.getenv("VPN_LIST_URLS") or
                             "https://raw.githubusercontent.com/X4BNet/lists_vpn/main/output/vpn/ipv4.txt,"
                             "https://raw.githubusercontent.com/X4BNet/lists_vpn/main/output/datacenter/ipv4.txt").split(",") if u.strip()]
VPN_LIST_AUTO = os.getenv("VPN_LIST_AUTO", "1") != "0"
if DASHBOARD_URL and not re.match(r"^https?://", DASHBOARD_URL, re.I):
    DASHBOARD_URL = ("https://" if TLS_READY else "http://") + DASHBOARD_URL
DASH_BASE = DASHBOARD_URL or WEB_URL
OAUTH_READY = bool(DASH_BASE and CLIENT_SECRET)
DATA_DIR = os.getenv("DATA_DIR") or os.path.join(BASE_DIR, "data")
try:
    PORT = int(os.getenv("PORT", "0") or 0)
except ValueError:
    PORT = 0

BLUE, RED, GREEN, YELLOW, GRAY = 0x5865F2, 0xED4245, 0x57F287, 0xFEE75C, 0x99AAB5
SUPPORT_URL = "https://discord.gg/tAKTK9MYdc"
INVITE_RE = re.compile(r"(?:discord\.gg|discord(?:app)?\.com/invite)/[\w-]+", re.I)
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("azqbot")

DEFAULTS = {
    "log_channel": None,
    "welcome": {"channel": None, "message": "ようこそ {user} さん！ {server} へ 🎉 (あなたは {count} 人目です)",
                "image": {"enabled": False, "title": "WELCOME", "subtitle": "{server} へようこそ!", "style": "black",
                          "color": True, "show_count": True, "bg": False}},
    "autorole": None,
    "warn_limit": 3,
    "warn_timeout_minutes": 60,
    "warns": {},
    "automod": {
        "enabled": True,
        "spam_count": 5,
        "spam_seconds": 6,
        "dup_count": 3,
        "mention_limit": 5,
        "block_invites": True,
        "strikes_to_timeout": 3,
        "punish_minutes": 10,
        "raid_joins": 5,
        "raid_seconds": 10,
        "ng_words": [],
        "ignore_channels": [],
        "ignore_roles": [],
    },
    "kaso": {"enabled": False, "channel": None, "threshold": 20, "last_alert": 0},
    "verify": {
        "enabled": False,
        "mode": "button",
        "role": None,
        "unverified_role": None,
        "panel_channel": None,
        "panel_message": None,
        "panel_title": "✅ メンバー認証",
        "panel_text": "下のボタンを押して認証を完了すると、サーバーのチャンネルが利用できるようになります。\n荒らし・BOT対策へのご協力をお願いします。",
        "panel_button": "認証する",
        "min_account_days": 0,
        "kick_minutes": 0,
        "max_attempts": 3,
        "lockout_minutes": 10,
        "violation": "deny",
        "bot_check": False,
        "block_default_avatar": False,
        "block_rejoin": False,
        "block_cluster": False,
        "block_vpn": False,
        "block_alt_ip": True,
        "ip_hashes": {},
        "suspect_action": "hold",
        "flagged": {},
        "suspects": {},
        "pending": {},
        "stats": {"verified": 0, "failed": 0, "denied": 0, "kicked": 0},
    },
    "ticket": {
        "enabled": False,
        "category": None,
        "staff_roles": [],
        "transcript_channel": None,
        "panel_channel": None,
        "panel_message": None,
        "panel_title": "🎫 サポートチケット",
        "panel_text": "ご質問・ご相談・報告は、下のボタンからチケットを作成してください。\n専用の非公開チャンネルが作成され、スタッフが対応します。",
        "max_open": 1,
        "auto_close_hours": 0,
        "ping_staff": True,
        "dm_transcript": True,
        "counter": 0,
        "open": {},
        "blocked": [],
        "stats": {"created": 0, "closed": 0},
    },
    "rolepanel": {
        "panels": {},
    },
    "meigen": {"enabled": True},
}


def deep_merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


STORE_SAVE_DELAY = 1.5


class Store:
    def __init__(self, directory: str):
        os.makedirs(directory, exist_ok=True)
        self.path = os.path.join(directory, "guilds.json")
        self.data: dict = {}
        self.existed = os.path.exists(self.path)
        self._dirty = False
        self._task: Optional[asyncio.Task] = None
        self._write_lock = threading.Lock()
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    raw = json.load(f)
                for gid, cfg in raw.items():
                    self.data[gid] = deep_merge(copy.deepcopy(DEFAULTS), cfg)
            except Exception:
                log.exception("設定ファイルの読み込みに失敗しました。空の設定で起動します。")

    def get(self, guild_id: int) -> dict:
        key = str(guild_id)
        if key not in self.data:
            self.data[key] = copy.deepcopy(DEFAULTS)
        return self.data[key]

    def save(self) -> None:
        """保存の要求。短時間に何度呼ばれても、まとめて1回だけ別スレッドでファイルに書く(イベントループを止めない)。"""
        self._dirty = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return self.flush()
        if self._task is None or self._task.done():
            self._task = loop.create_task(self._flush_later())

    async def _flush_later(self) -> None:
        while self._dirty:
            await asyncio.sleep(STORE_SAVE_DELAY)
            await self.flush_async()

    def _dump(self) -> str:
        return json.dumps(self.data, ensure_ascii=False, separators=(",", ":"))

    def _write(self, payload: str) -> None:
        with self._write_lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp, self.path)

    async def flush_async(self) -> None:
        if not self._dirty:
            return
        self._dirty = False
        try:
            payload = self._dump()
            await asyncio.get_running_loop().run_in_executor(None, self._write, payload)
        except Exception:
            self._dirty = True
            log.exception("設定の保存に失敗しました")

    def flush(self) -> None:
        """今すぐ同期で保存する(終了時・ループ外用)"""
        if not self._dirty:
            return
        self._dirty = False
        try:
            self._write(self._dump())
        except Exception:
            self._dirty = True
            log.exception("設定の保存に失敗しました")


store = Store(DATA_DIR)
atexit.register(store.flush)


class UserPrefs:
    """ユーザー個別の設定(サーバーをまたいで共通)。{ユーザーID: {"meigen": "allow"|"deny", "asked": 確認DMの送信時刻}}"""

    def __init__(self, directory: str):
        self.path = os.path.join(directory, "user_prefs.json")
        self.data: dict = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                log.exception("ユーザー設定の読み込みに失敗しました。空の設定で起動します。")

    def rec(self, user_id: int) -> dict:
        return self.data.setdefault(str(user_id), {})

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


user_prefs = UserPrefs(DATA_DIR)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class AzqBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            activity=discord.Game("/help | AZQ BOT"),
            help_command=None,
        )
        self.started_at = time.time()
        self.session: Optional[aiohttp.ClientSession] = None
        self.web_runner: Optional[web.AppRunner] = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession(headers={"User-Agent": BROWSER_UA})
        self.tree.add_command(config_group)
        self.tree.add_command(verify_group)
        self.add_view(VerifyPanelView())
        self.tree.add_command(ticket_group)
        self.tree.add_command(ticketconfig_group)
        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())
        self.add_view(TicketClosedView())
        self.add_view(MeigenConsentView())
        self.tree.add_command(rolepanel_group)
        for _cfg in store.data.values():
            for _mid, _p in _cfg.get("rolepanel", {}).get("panels", {}).items():
                self.add_view(RolePanelView(_p["roles"]), message_id=int(_mid))
        srvadm_install()
        if DEV_GUILD_ID.isdigit():
            guild = discord.Object(id=int(DEV_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("スラッシュコマンドを GUILD_ID=%s に同期しました", DEV_GUILD_ID)
        else:
            await self.tree.sync()
            log.info("スラッシュコマンドをグローバル同期しました")
        await start_web()
        kaso_watch.start()
        cleanup_trackers.start()
        verify_watch.start()
        ticket_watch.start()
        activity_save.start()
        self._lag_task = asyncio.create_task(loop_lag_monitor())

    async def close(self):
        t = getattr(self, "_tls_task", None)
        if t:
            t.cancel()
        await store.flush_async()
        await act_flush_async()
        await srvadm_flush()
        if self.session:
            await self.session.close()
        if self.web_runner:
            await self.web_runner.cleanup()
        await super().close()


bot = AzqBot()


async def loop_lag_monitor():
    """処理がイベントループを塞いで応答が遅れていないかを監視し、詰まったらログに警告を出す(原因調査用)"""
    await bot.wait_until_ready()
    interval = 5
    while not bot.is_closed():
        t0 = time.monotonic()
        await asyncio.sleep(interval)
        lag = time.monotonic() - t0 - interval
        if lag > 1.0:
            log.warning("イベントループが約 %.1f 秒間、詰まりました。重い処理が応答を遅らせています。", lag)


def _tls_mtime() -> float:
    return max(os.path.getmtime(TLS_CERT), os.path.getmtime(TLS_KEY))


async def tls_reload_loop(ctx) -> None:
    """証明書ファイルが更新されたら読み込み直す(Let's Encrypt は約60日ごとに更新される)。新しい接続から反映される。"""
    try:
        last = _tls_mtime()
    except OSError:
        last = 0.0
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            m = _tls_mtime()
            if m != last:
                ctx.load_cert_chain(TLS_CERT, TLS_KEY)
                last = m
                log.info("TLS証明書を再読み込みしました")
        except Exception:
            log.exception("TLS証明書の再読み込みに失敗しました")


async def start_web():
    """SnapDeploy等のコンテナ環境向けヘルスチェック用の簡易HTTPサーバー"""

    async def health(_request):
        lat = bot.latency
        return web.json_response({
            "status": "ok",
            "guilds": len(bot.guilds),
            "latency_ms": None if lat != lat else round(lat * 1000),
        })

    port = PORT or (int(os.getenv("WEB_PORT") or 8080) if (DASH_BASE or WEB_READY) else 0)
    if not port:
        log.info("Webサーバーは無効です(PORT または WEB_URL を設定すると有効になります)")
        return
    app = web.Application(client_max_size=6 * 1024 * 1024)
    app.router.add_get("/health", health)
    if DASH_BASE:
        add_dashboard_routes(app)
    else:
        app.router.add_get("/", health)
    if WEB_READY:
        app.router.add_get("/v", web_verify_get)
        app.router.add_post("/v", web_verify_post)
    runner = web.AppRunner(app)
    await runner.setup()
    ssl_ctx = None
    if TLS_READY:
        try:
            import ssl
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(TLS_CERT, TLS_KEY)
        except Exception as e:
            log.error("TLS証明書を読み込めませんでした(%s)。HTTPでは起動しません。TLS_CERT / TLS_KEY のパスと権限を確認してください: %s", TLS_CERT, e)
            await runner.cleanup()
            return
    try:
        await web.TCPSite(runner, "0.0.0.0", port, ssl_context=ssl_ctx).start()
    except OSError as e:
        log.warning("Webサーバーを起動できませんでした(ポート %s: %s)。BOTは続行します。"
                    "すでに別のBOTプロセスが動いていないか確認してください。", port, e)
        await runner.cleanup()
        return
    bot.web_runner = runner
    if WEB_READY:
        bot._vpn_task = asyncio.create_task(vpn_list_loop())
    if ssl_ctx:
        bot._tls_task = asyncio.create_task(tls_reload_loop(ssl_ctx))
    if WEB_READY:
        log.info("Web認証のreCAPTCHA: %s", "有効" if RECAPTCHA_READY else "無効(RECAPTCHA_SITE_KEY / RECAPTCHA_SECRET_KEY が未設定)")
    log.info("Webサーバー起動: 0.0.0.0:%s (%s / ダッシュボード: %s)", port, "HTTPS" if ssl_ctx else "HTTP",
             "有効(OAuth)" if OAUTH_READY else "無効(DISCORD_CLIENT_SECRET が未設定)" if DASH_BASE else "無効")


def make_embed(title: str, desc: Optional[str] = None, color: int = BLUE) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=color, timestamp=discord.utils.utcnow())


async def send_log(guild: discord.Guild, embed: discord.Embed) -> None:
    try:
        record_log(guild.id, embed)
    except Exception:
        log.exception("管理ログの保存に失敗しました")
    channel_id = store.get(guild.id)["log_channel"]
    channel = guild.get_channel(channel_id) if channel_id else None
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass


def hierarchy_error(interaction: discord.Interaction, target: discord.Member) -> Optional[str]:
    guild = interaction.guild
    if target.id == interaction.user.id:
        return "自分自身には実行できません。"
    if target.id == guild.me.id:
        return "BOT自身には実行できません。"
    if target.id == guild.owner_id:
        return "サーバーオーナーには実行できません。"
    if interaction.user.id != guild.owner_id and target.top_role >= interaction.user.top_role:
        return "あなたと同位以上のロールを持つメンバーには実行できません。"
    if target.top_role >= guild.me.top_role:
        return "BOTのロールより上位(または同位)のメンバーです。サーバー設定でBOTのロールを上に移動してください。"
    return rank_conflict(interaction.user, target)


async def try_dm(user: discord.abc.User, text: str) -> None:
    try:
        await user.send(text)
    except discord.HTTPException:
        pass

@bot.tree.error
async def on_app_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, RankError):
        msg = str(error)
    elif isinstance(error, app_commands.MissingPermissions):
        msg = "❌ このコマンドを実行する権限がありません。"
    elif isinstance(error, app_commands.BotMissingPermissions):
        msg = "❌ BOTに必要な権限が不足しています: " + ", ".join(error.missing_permissions)
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ {error.retry_after:.0f}秒後にもう一度お試しください。"
    elif isinstance(error, app_commands.NoPrivateMessage):
        msg = "❌ このコマンドはサーバー内でのみ使えます。"
    elif isinstance(error, app_commands.CommandInvokeError) and isinstance(error.original, discord.Forbidden):
        msg = "❌ BOTの権限が不足しています。(ロールの順位・チャンネル権限を確認してください)"
    elif isinstance(error, app_commands.CheckFailure):
        msg = "❌ このコマンドは実行できません。"
    else:
        log.exception("コマンドエラー", exc_info=error)
        msg = "⚠️ エラーが発生しました。しばらくしてからもう一度お試しください。"
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)

recent_msgs = defaultdict(lambda: deque(maxlen=30))
recent_dups = defaultdict(lambda: deque(maxlen=10))
strikes = defaultdict(deque)
join_times = defaultdict(deque)
last_raid_alert = {}


async def punish(message: discord.Message, reason: str, heavy: bool = False, extra: Optional[list] = None):
    guild, member = message.guild, message.author
    am = store.get(guild.id)["automod"]

    targets = [m for m in (extra or []) if m.channel.id == message.channel.id] or [message]
    try:
        if len(targets) > 1:
            await message.channel.delete_messages(targets)
        else:
            await message.delete()
    except discord.HTTPException:
        pass

    now = time.time()
    key = (guild.id, member.id)
    dq = strikes[key]
    dq.append(now)
    while dq and now - dq[0] > 300:
        dq.popleft()

    timed_out = False
    if heavy or len(dq) >= am["strikes_to_timeout"]:
        try:
            await member.timeout(timedelta(minutes=am["punish_minutes"]), reason=f"[AZQ BOT AutoMod] {reason}")
            timed_out = True
            dq.clear()
        except discord.HTTPException:
            pass

    note = f"{member.mention} ⚠️ **{reason}** を検知したためメッセージを削除しました。"
    if timed_out:
        note += f"\n🔇 {am['punish_minutes']}分間タイムアウトしました。"
    try:
        await message.channel.send(note, delete_after=8)
    except discord.HTTPException:
        pass

    e = make_embed("🛡️ AutoMod 発動", color=RED)
    e.add_field(name="ユーザー", value=f"{member} (`{member.id}`)")
    e.add_field(name="チャンネル", value=message.channel.mention)
    e.add_field(name="理由", value=reason)
    e.add_field(name="処置", value="削除 + タイムアウト" if timed_out else f"削除 (警告 {len(dq)}/{am['strikes_to_timeout']})")
    if message.content:
        e.add_field(name="内容", value=message.content[:500], inline=False)
    await send_log(guild, e)


@bot.event
async def on_message(message: discord.Message):
    if message.guild and not message.author.bot and isinstance(message.channel, discord.TextChannel):
        record_activity(message.guild.id, message.channel.id, message.author.id, message.created_at.timestamp())
    if message.author.bot or not message.guild or not isinstance(message.author, discord.Member):
        return
    am = store.get(message.guild.id)["automod"]
    if not am["enabled"]:
        return
    member = message.author
    perms = member.guild_permissions
    if perms.administrator or perms.manage_messages:
        return
    if message.channel.id in am["ignore_channels"] or any(r.id in am["ignore_roles"] for r in member.roles):
        return

    content = message.content
    lowered = content.lower()
    key = (message.guild.id, member.id)
    now = time.time()

    for word in am["ng_words"]:
        if word and word.lower() in lowered:
            return await punish(message, "NGワード")
    if am["block_invites"] and INVITE_RE.search(content):
        return await punish(message, "招待リンクの投稿")
    if len(message.mentions) + len(message.role_mentions) >= am["mention_limit"]:
        return await punish(message, "メンション過多", heavy=True)

    dq = recent_msgs[key]
    dq.append((now, message))
    while dq and now - dq[0][0] > am["spam_seconds"]:
        dq.popleft()
    if len(dq) >= am["spam_count"]:
        msgs = [m for _, m in dq]
        dq.clear()
        return await punish(message, "連投(スパム)", heavy=True, extra=msgs)

    if content:
        dd = recent_dups[key]
        dd.append((now, content))
        if sum(1 for t, c in dd if c == content and now - t <= 30) >= am["dup_count"]:
            dd.clear()
            return await punish(message, "同一メッセージの連続投稿")


async def apply_autorole(member: discord.Member) -> None:
    cfg = store.get(member.guild.id)
    role = member.guild.get_role(cfg["autorole"]) if cfg["autorole"] else None
    if role:
        try:
            await member.add_roles(role, reason="AZQ BOT 自動ロール")
        except discord.HTTPException:
            pass


async def send_welcome(member: discord.Member, test: bool = False) -> tuple:
    """ウェルカムメッセージ(画像つき)を送る。失敗した理由を文字列で返す(成功なら None)。戻り値: (送れたか, 理由・補足)。送れなかった理由はログにも残す"""
    guild = member.guild
    wc = store.get(guild.id)["welcome"]
    ch = guild.get_channel(wc["channel"]) if wc["channel"] else None
    if not ch:
        return False, "送信先チャンネルが設定されていません(または削除されています)。"
    p = ch.permissions_for(guild.me)
    if not (p.view_channel and p.send_messages):
        log.warning("ウェルカムを送れません: BOTに #%s での「チャンネルを見る・メッセージを送信」権限がありません guild=%s", ch.name, guild.id)
        return False, f"BOTが #{ch.name} で「チャンネルを見る・メッセージを送信」を行えません。"
    text = (wc["message"].replace("{user}", member.mention)
            .replace("{server}", guild.name).replace("{count}", str(guild.member_count)))
    if test:
        text = "🧪 **テスト送信**(メンバーが参加したときは、この内容が送られます)\n" + text
    im, file, note = wc.get("image") or {}, None, ""
    if im.get("enabled"):
        if not p.attach_files:
            log.warning("ウェルカム画像を付けられません: BOTに #%s での「ファイルを添付」権限がありません guild=%s", ch.name, guild.id)
            note = f"画像は付けられませんでした。BOTに #{ch.name} での「ファイルを添付」権限がありません。"
        else:
            try:
                file = await make_welcome_file(member, im)
            except Exception as e:
                log.exception("ウェルカム画像の生成に失敗しました。文章だけ送ります。")
                note = f"画像を作れなかったので文章だけ送りました({type(e).__name__})。BOTのログを確認してください。"
    try:
        kw = {"file": file} if file else {}
        await ch.send(text[:2000], allowed_mentions=discord.AllowedMentions(users=[member]), **kw)
    except discord.HTTPException as e:
        log.warning("ウェルカムの送信に失敗 guild=%s channel=%s: %s", guild.id, ch.id, e)
        return False, f"Discordに送信を拒否されました({e.status})。BOTの権限を確認してください。"
    return True, note or None


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    cfg = store.get(guild.id)

    gated = verify_active(cfg) and not member.bot
    if gated:
        v = cfg["verify"]
        ur = guild.get_role(v["unverified_role"]) if v["unverified_role"] else None
        if ur:
            try:
                await member.add_roles(ur, reason="AZQ BOT 未認証ロール")
            except discord.HTTPException:
                log.warning("未認証ロールの付与に失敗 guild=%s", guild.id)
        v["pending"][str(member.id)] = int(time.time())
        reasons = detect_join_suspects(member, v)
        store.save()
        if reasons:
            await send_log(guild, make_embed("🛡️ 疑わしい参加(認証前)", f"{member.mention} (`{member.id}`)\n理由: " + " / ".join(reasons)
                                           + "\n認証ボタンを押しても、設定に従って保留またはキックされます。", YELLOW))
    else:
        await apply_autorole(member)
    try:
        await send_welcome(member)
    except Exception:
        log.exception("ウェルカムメッセージの送信で想定外のエラー guild=%s", guild.id)

    age_days = (discord.utils.utcnow() - member.created_at).days
    e = make_embed("📥 メンバー参加", f"{member.mention} (`{member.id}`)", GREEN)
    e.add_field(name="アカウント作成", value=discord.utils.format_dt(member.created_at, "R"))
    if gated:
        e.add_field(name="🔐 認証", value="認証待ち")
    if age_days < 3:
        e.add_field(name="⚠️ 新規アカウント", value=f"作成から{age_days}日", inline=False)
        e.color = YELLOW
    await send_log(guild, e)

    am = cfg["automod"]
    now = time.time()
    dq = join_times[guild.id]
    dq.append(now)
    while dq and now - dq[0] > am["raid_seconds"]:
        dq.popleft()
    if am["enabled"] and len(dq) >= am["raid_joins"]:
        boosted = verify_active(cfg)
        if boosted:
            raid_until[guild.id] = now + RAID_VERIFY_SECONDS
        if now - last_raid_alert.get(guild.id, 0) > 60:
            last_raid_alert[guild.id] = now
            text = (f"{am['raid_seconds']}秒以内に **{len(dq)}人** が参加しました。\n"
                    "`/lock` でチャンネルを閉じる、`/ban` 等で対処してください。")
            if boosted:
                text += (f"\n🔐 認証を **{RAID_VERIFY_SECONDS // 60}分間** 自動で強化しました"
                         f"(画像認証 + アカウント作成{RAID_MIN_ACCOUNT_DAYS}日以上)。解除: `/verify raid enabled:False`")
            await send_log(guild, make_embed("🚨 レイドの疑い", text, RED))


@bot.event
async def on_member_remove(member: discord.Member):
    v = store.get(member.guild.id)["verify"]
    if v["pending"].pop(str(member.id), None) is not None:
        store.save()
    for cid, info in list(store.get(member.guild.id)["ticket"]["open"].items()):
        if info["owner"] == member.id and not info.get("closed"):
            tch = member.guild.get_channel(int(cid))
            if tch:
                try:
                    await tch.send(f"⚠️ チケット作成者 ({member}) がサーバーから退出しました。不要なら `/ticket close` で閉じてください。")
                except discord.HTTPException:
                    pass
    e = make_embed("📤 メンバー退出", f"{member} (`{member.id}`)", GRAY)
    await send_log(member.guild, e)


@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot or not message.guild or not message.content:
        return
    e = make_embed("🗑️ メッセージ削除", color=GRAY)
    e.add_field(name="投稿者", value=f"{message.author} (`{message.author.id}`)")
    e.add_field(name="チャンネル", value=message.channel.mention)
    e.add_field(name="内容", value=message.content[:1000], inline=False)
    await send_log(message.guild, e)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.author.bot or not before.guild or before.content == after.content:
        return
    e = make_embed("✏️ メッセージ編集", color=GRAY)
    e.add_field(name="投稿者", value=f"{before.author} (`{before.author.id}`)")
    e.add_field(name="チャンネル", value=before.channel.mention)
    e.add_field(name="編集前", value=(before.content or "(なし)")[:500], inline=False)
    e.add_field(name="編集後", value=(after.content or "(なし)")[:500], inline=False)
    e.add_field(name="リンク", value=f"[ジャンプ]({after.jump_url})", inline=False)
    await send_log(before.guild, e)


@bot.event
async def on_connect():
    global act_conn_time
    if act_conn_time is None:
        act_conn_time = time.time()


@bot.event
async def on_ready():
    log.info("ログイン: %s (サーバー数: %d)", bot.user, len(bot.guilds))
    if getattr(bot, "_restored", False):
        return
    bot._restored = True
    init_activity_gaps()
    if not store.existed and bot.guilds:
        log.warning("設定ファイル %s がありません。初回起動か、再起動でデータが初期化された可能性があります。"
                    "DATA_DIR に永続ボリュームを指定してください。", store.path)
    try:
        await restore_panels()
    except Exception:
        log.exception("パネルの復元チェックでエラー")


async def _panel_gone(guild: discord.Guild, channel_id, message_id) -> Optional[discord.TextChannel]:
    ch = guild.get_channel(channel_id) if channel_id else None
    if not isinstance(ch, discord.TextChannel) or not message_id:
        return None
    try:
        await ch.fetch_message(int(message_id))
    except discord.NotFound:
        return ch
    except discord.HTTPException:
        pass
    return None


async def restore_panels() -> None:
    for guild in list(bot.guilds):
        cfg = store.data.get(str(guild.id))
        if not cfg or guild.unavailable:
            continue
        v, tc = cfg["verify"], cfg["ticket"]
        jobs = []
        if verify_active(cfg):
            jobs.append(("認証", v, post_panel))
        if tc["enabled"]:
            jobs.append(("チケット", tc, post_ticket_panel))
        for name, c, poster in jobs:
            ch = await _panel_gone(guild, c["panel_channel"], c["panel_message"])
            if ch and _can_post(ch, guild.me):
                try:
                    await poster(guild, ch)
                    log.info("%sパネルを自動復元しました guild=%s", name, guild.id)
                except discord.HTTPException:
                    log.warning("%sパネルの復元に失敗 guild=%s", name, guild.id)
        panels = cfg["rolepanel"]["panels"]
        for mid, p in list(panels.items()):
            ch = await _panel_gone(guild, p["channel"], mid)
            if ch and _can_post(ch, guild.me):
                try:
                    msg = await ch.send(embed=rp_embed(p), view=RolePanelView(p["roles"]))
                except discord.HTTPException:
                    log.warning("ロールパネルの復元に失敗 guild=%s", guild.id)
                    continue
                panels[str(msg.id)] = panels.pop(mid)
                store.save()
                bot.add_view(RolePanelView(p["roles"]), message_id=msg.id)
                log.info("ロールパネルを自動復元しました guild=%s", guild.id)


@bot.event
async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
    cfg = store.data.get(str(payload.guild_id)) if payload.guild_id else None
    if not cfg:
        return
    changed = False
    if cfg["rolepanel"]["panels"].pop(str(payload.message_id), None) is not None:
        changed = True
    for c in (cfg["verify"], cfg["ticket"]):
        if c["panel_message"] == payload.message_id:
            c["panel_message"] = None
            changed = True
    if changed:
        store.save()


@bot.event
async def on_guild_join(guild: discord.Guild):
    log.info("サーバーに参加: %s (%s) メンバー数=%s", guild.name, guild.id, guild.member_count)
    e = make_embed("🛡️ AZQ BOT を導入していただきありがとうございます!", color=BLUE)
    e.description = (
        "荒らし対策からメンバー認証・チケットまで、サーバー管理を1つのBotでまとめて行えます。\n\n"
        "**主な機能**\n"
        "🛡️ 荒らし対策: 連投・招待リンク・NGワード・レイドなどを自動検知\n"
        "🔐 メンバー認証: ボタン / 計算 / 画像CAPTCHA\n"
        "🎫 サポートチケット: 非公開chの自動作成、記録の保存\n"
        "📊 過疎診断 `/kaso` ・ 🔨 モデレーション ・ 🧠 脳内メーカー ・ 🖼️ 名言画像\n\n"
        "**はじめに**\n"
        "・コマンド一覧は `/help` で確認できます\n"
        "・BOTのロールを、管理したいメンバー・ロールより**上**に移動してください\n"
        "・ログなどの設定は管理者が `/config log_channel` から行えます\n\n"
        "📢 **サポートサーバーに参加してください**\n"
        "メンテナンス・障害・アップデートなどの**お知らせは、サポートサーバーでのみ配信**します。"
        "参加していないと、これらのお知らせを受け取れません。\n"
        f"👉 {SUPPORT_URL}"
    )
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="サポートサーバーに参加", emoji="📢", style=discord.ButtonStyle.link, url=SUPPORT_URL))
    me = guild.me
    targets = []
    if guild.system_channel:
        targets.append(guild.system_channel)
    targets += [c for c in guild.text_channels if c is not guild.system_channel]
    for ch in targets:
        p = ch.permissions_for(me)
        if p.view_channel and p.send_messages and p.embed_links:
            try:
                await ch.send(embed=e, view=view)
                return
            except discord.HTTPException:
                continue
    try:
        owner = guild.owner or await guild.fetch_member(guild.owner_id)
        await owner.send(content=f"**{guild.name}** にAZQ BOTが参加しました。", embed=e, view=view)
    except discord.HTTPException:
        log.info("参加メッセージを送信できませんでした guild=%s", guild.id)


@bot.event
async def on_guild_remove(guild: discord.Guild):
    log.info("サーバーから退出: %s (%s)", guild.name, guild.id)
    act.pop(guild.id, None)
    act_locks.pop(guild.id, None)
    try:
        os.remove(welcome_bg_path(guild.id))
    except OSError:
        pass


@tasks.loop(minutes=10)
async def cleanup_trackers():
    now = time.time()
    for tracker in (recent_msgs, recent_dups):
        for k in [k for k, dq in tracker.items() if not dq or now - dq[-1][0] > 120]:
            tracker.pop(k, None)
    for k in [k for k, dq in strikes.items() if not dq or now - dq[-1] > 300]:
        strikes.pop(k, None)
    for k in [k for k, (_, exp) in verify_challenges.items() if exp < now]:
        verify_challenges.pop(k, None)
    for k in [k for k, rec in verify_fails.items() if now - rec[1] > 900]:
        verify_fails.pop(k, None)
    for k in [k for k, until in verify_lock.items() if until < now]:
        verify_lock.pop(k, None)
    for k in [k for k, t in verify_last.items() if now - t > 60]:
        verify_last.pop(k, None)
    for k in [k for k, until in raid_until.items() if until < now]:
        raid_until.pop(k, None)
    for k in [k for k, t in ticket_last.items() if now - t > TICKET_COOLDOWN]:
        ticket_last.pop(k, None)


ACT_BUCKET = 900
ACT_KEEP = 8 * 86400
ACT_MAX_USERS = 300_000
ACT_SAVE_MINUTES = 5
ACT_FILE = os.path.join(DATA_DIR, "activity.json")
ACT_BACKFILL_CONCURRENCY = 4
act: dict = {}
act_locks: dict = {}
act_dirty = False
act_loaded_saved = 0.0
act_conn_time: Optional[float] = None
_scan_sem: Optional[asyncio.Semaphore] = None
_act_write_lock = threading.Lock()


def _load_activity() -> None:
    global act_loaded_saved
    if not os.path.exists(ACT_FILE):
        return
    try:
        with open(ACT_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        act_loaded_saved = float(raw.get("saved", 0))
        for gid, r in raw.get("g", {}).items():
            act[int(gid)] = {"b": {int(b): {int(c): int(n) for c, n in chs.items()} for b, chs in r.get("b", {}).items()},
                             "u": {int(u): float(t) for u, t in r.get("u", {}).items()},
                             "gaps": [[float(x), float(y)] for x, y in r.get("gaps", [])]}
    except Exception:
        log.exception("過疎診断の記録の読み込みに失敗しました。空の状態で始めます。")
        act.clear()


_load_activity()


def _act_rec(gid: int) -> dict:
    rec = act.get(gid)
    if rec is None:
        now = time.time()
        rec = act[gid] = {"b": {}, "u": {}, "gaps": [[now - ACT_KEEP, now]]}
    return rec


def record_activity(guild_id: int, channel_id: int, author_id: int, ts: float) -> None:
    global act_dirty
    rec = _act_rec(guild_id)
    chs = rec["b"].setdefault(int(ts // ACT_BUCKET), {})
    chs[channel_id] = chs.get(channel_id, 0) + 1
    if ts > rec["u"].get(author_id, 0):
        rec["u"][author_id] = ts
    act_dirty = True


def init_activity_gaps() -> None:
    """起動時(on_ready)に1回だけ。止まっていた期間・記録のなかったサーバーを「欠け」として登録し、BOTにいないサーバーの記録を捨てる"""
    global act_dirty
    end = act_conn_time or time.time()
    floor = end - ACT_KEEP
    ids = {g.id for g in bot.guilds}
    for gid in [g for g in act if g not in ids]:
        act.pop(gid, None)
    for gid in ids:
        rec = act.get(gid)
        if rec is None:
            act[gid] = {"b": {}, "u": {}, "gaps": [[floor, end]]}
        elif end - act_loaded_saved > 30:
            rec["gaps"].append([max(act_loaded_saved, floor), end])
    act_dirty = True


async def _backfill_activity(guild: discord.Guild, lo: float, hi: float) -> None:
    after = datetime.fromtimestamp(lo, timezone.utc)
    before = datetime.fromtimestamp(hi, timezone.utc)
    me = guild.me
    channels = [c for c in guild.text_channels
                if c.permissions_for(me).view_channel and c.permissions_for(me).read_message_history]
    sem = asyncio.Semaphore(ACT_BACKFILL_CONCURRENCY)

    async def one(c: discord.TextChannel):
        async with sem:
            try:
                async for m in c.history(after=after, before=before, limit=None):
                    if not m.author.bot:
                        record_activity(guild.id, c.id, m.author.id, m.created_at.timestamp())
            except discord.HTTPException:
                log.warning("過疎診断: 履歴の取得に失敗 guild=%s channel=%s", guild.id, c.id)

    await asyncio.gather(*(one(c) for c in channels))


async def ensure_activity(guild: discord.Guild, since: float) -> None:
    """集計したい期間(since〜現在)に欠けがあれば、その部分だけ履歴から埋める。埋めた部分は記録に残り、次からは取得しない"""
    global _scan_sem, act_dirty
    rec = _act_rec(guild.id)
    lock = act_locks.setdefault(guild.id, asyncio.Lock())
    async with lock:
        if not any(e > since for _, e in rec["gaps"]):
            return
        if _scan_sem is None:
            _scan_sem = asyncio.Semaphore(1)
        async with _scan_sem:
            rest = []
            for s, e in rec["gaps"]:
                if e <= since:
                    rest.append([s, e])
                    continue
                lo = max(s, (since // ACT_BUCKET) * ACT_BUCKET)
                if lo < e:
                    await _backfill_activity(guild, lo, e)
                if lo > s:
                    rest.append([s, lo])
            rec["gaps"] = rest
            act_dirty = True


async def measure_activity(guild: discord.Guild, hours: int = 24):
    since = time.time() - hours * 3600
    await ensure_activity(guild, since)
    rec = _act_rec(guild.id)
    sb = int(since // ACT_BUCKET)
    total, per = 0, {}
    for b, chs in list(rec["b"].items()):
        if b < sb:
            continue
        for cid, n in chs.items():
            per[cid] = per.get(cid, 0) + n
            total += n
    per_ch = {}
    for cid, n in per.items():
        ch = guild.get_channel(cid)
        if ch is not None:
            per_ch[ch] = n
    humans = sum(1 for m in guild.members if not m.bot)
    active = sum(1 for u, t in list(rec["u"].items()) if t >= since and guild.get_member(u) is not None)
    return total, active, humans, per_ch


def prune_activity() -> None:
    now = time.time()
    cut = now - ACT_KEEP
    cb = int(cut // ACT_BUCKET)
    for rec in act.values():
        for b in [b for b in rec["b"] if b < cb]:
            rec["b"].pop(b, None)
        for u in [u for u, t in rec["u"].items() if t < cut]:
            rec["u"].pop(u, None)
        if len(rec["u"]) > ACT_MAX_USERS:
            for u, _ in sorted(rec["u"].items(), key=lambda kv: kv[1])[:len(rec["u"]) - ACT_MAX_USERS]:
                rec["u"].pop(u, None)
        rec["gaps"] = [[max(s, cut), e] for s, e in rec["gaps"] if e > cut]


def _act_dump() -> str:
    global act_dirty
    act_dirty = False
    return json.dumps({"v": 1, "saved": time.time(), "g": {str(g): r for g, r in act.items()}}, separators=(",", ":"))


def _act_write(payload: str) -> None:
    with _act_write_lock:
        tmp = ACT_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, ACT_FILE)


async def act_flush_async() -> None:
    global act_dirty
    if not act_dirty:
        return
    try:
        payload = _act_dump()
        await asyncio.get_running_loop().run_in_executor(None, _act_write, payload)
    except Exception:
        act_dirty = True
        log.exception("過疎診断の記録の保存に失敗しました")


def act_flush_sync() -> None:
    global act_dirty
    if not act_dirty:
        return
    try:
        _act_write(_act_dump())
    except Exception:
        act_dirty = True
        log.exception("過疎診断の記録の保存に失敗しました")


atexit.register(act_flush_sync)


@tasks.loop(minutes=ACT_SAVE_MINUTES)
async def activity_save():
    prune_activity()
    await act_flush_async()


@activity_save.before_loop
async def _before_activity_save():
    await bot.wait_until_ready()


def kaso_level(total: int, hours: int, ratio: float):
    per_day = total * 24 / hours
    if per_day >= 200 or ratio >= 0.25:
        return "🔥 大盛況", GREEN, "とても活発です。この調子！"
    if per_day >= 50:
        return "😊 活発", GREEN, "健全に動いています。"
    if per_day >= 15:
        return "🙂 ふつう", BLUE, "もう少し話題があるとさらに盛り上がります。"
    if per_day >= 5:
        return "😴 やや過疎", YELLOW, "イベントや雑談チャンネルでテコ入れしましょう。"
    return "💀 過疎", RED, "ほぼ動いていません。企画・告知・ロール通知などで人を呼び戻しましょう。"


@bot.tree.command(name="kaso", description="サーバーの過疎度を診断します")
@app_commands.describe(hours="集計する時間(1〜168、既定24)")
@app_commands.guild_only()
@app_commands.checks.cooldown(1, 60, key=lambda i: i.guild_id)
async def kaso(interaction: discord.Interaction, hours: app_commands.Range[int, 1, 168] = 24):
    await interaction.response.defer()
    total, active, humans, per = await measure_activity(interaction.guild, hours)
    ratio = active / humans if humans else 0
    label, color, advice = kaso_level(total, hours, ratio)
    e = make_embed(f"📊 過疎診断: {label}", advice, color)
    e.add_field(name=f"メッセージ数({hours}h)", value=f"{total:,}")
    e.add_field(name="発言者数", value=f"{active:,} / {humans:,}人")
    e.add_field(name="発言率", value=f"{ratio * 100:.1f}%")
    if per:
        top = sorted(per.items(), key=lambda kv: kv[1], reverse=True)[:3]
        e.add_field(name="盛り上がっているチャンネル", value="\n".join(f"{c.mention}: {n:,}" for c, n in top), inline=False)
    e.set_footer(text="※ BOTが閲覧可能なチャンネルのみ・件数の上限なし / BOT発言は除外")
    await interaction.followup.send(embed=e)


@tasks.loop(hours=6)
async def kaso_watch():
    for guild in bot.guilds:
        k = store.get(guild.id)["kaso"]
        if not k["enabled"] or not k["channel"] or time.time() - k["last_alert"] < 86400:
            continue
        ch = guild.get_channel(k["channel"])
        if not ch:
            continue
        total, active, humans, _ = await measure_activity(guild, 24)
        if total < k["threshold"]:
            k["last_alert"] = time.time()
            store.save()
            e = make_embed("📉 過疎アラート", f"直近24時間のメッセージが **{total}件**(しきい値 {k['threshold']}件)でした。", YELLOW)
            e.add_field(name="発言者数", value=f"{active} / {humans}人")
            try:
                await ch.send(embed=e)
            except discord.HTTPException:
                pass


@kaso_watch.before_loop
async def _before_kaso_watch():
    await bot.wait_until_ready()
    await asyncio.sleep(60)


async def build_nounai(name: str):
    name = name.strip()[:30]
    url = f"https://maker.usoko.net/nounai/img/{quote(name, safe='')}.gif"
    e = make_embed(f"🧠 {name} の脳内", color=BLUE)
    e.set_footer(text="powered by maker.usoko.net")
    try:
        async with bot.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200 and resp.content_length is not None and resp.content_length < 8_000_000:
                data = await resp.read()
                e.set_image(url="attachment://nounai.gif")
                return e, discord.File(io.BytesIO(data), filename="nounai.gif")
    except Exception:
        log.warning("脳内メーカー画像の取得に失敗。URL埋め込みにフォールバックします", exc_info=True)
    e.set_image(url=url)
    return e, None


@bot.tree.command(name="nounai", description="脳内メーカーで脳内を覗きます")
@app_commands.describe(name="診断する名前(省略すると自分)", user="ユーザーを指定する場合")
async def nounai(interaction: discord.Interaction, name: Optional[str] = None, user: Optional[discord.User] = None):
    await interaction.response.defer()
    target = name or (user or interaction.user).display_name
    embed, file = await build_nounai(target)
    if file:
        await interaction.followup.send(embed=embed, file=file)
    else:
        await interaction.followup.send(embed=embed)


@bot.tree.context_menu(name="脳内メーカー")
async def nounai_ctx(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()
    embed, file = await build_nounai(member.display_name)
    if file:
        await interaction.followup.send(embed=embed, file=file)
    else:
        await interaction.followup.send(embed=embed)


FONT_SOURCES = [
    ("MPLUS1p-Regular.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/mplus1p/MPLUS1p-Regular.ttf"),
    ("NotoSansJP-Regular.otf", "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Regular.otf"),
]
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\YuGothR.ttc", r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\msgothic.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
]
KINSOKU = set("、。，．・」』）】〉》〕｝！？!?,.)]}:;…ー々ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ")
OPENERS = set("「『（【〈《〔｛([{")

MG_W, MG_H = 1200, 630

try:
    HEAVY_WORKERS = int(os.getenv("HEAVY_WORKERS") or 0)
except ValueError:
    HEAVY_WORKERS = 0
if HEAVY_WORKERS < 1:
    HEAVY_WORKERS = max(2, min(4, os.cpu_count() or 2))
HEAVY_POOL = ThreadPoolExecutor(max_workers=HEAVY_WORKERS, thread_name_prefix="heavy")
CAPTCHA_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="captcha")


async def run_heavy(fn, *args, pool=None):
    return await asyncio.get_running_loop().run_in_executor(pool or HEAVY_POOL, fn, *args)

MG_CX = 855
MG_AREA_W = 590
MG_TITLE_MAX, MG_TITLE_MIN = 60, 20
MG_AUTHOR_SIZE, MG_HANDLE_SIZE = 35, 20
MG_SHEAR = 0.17
MG_AUTHOR_DX = 1.5
MG_TITLE_BASE = 306.0
MG_GAP_AUTHOR = 66.0
MG_GAP_HANDLE = 30.0
MG_TOP_RATIO = 49 / 60
MG_BOTTOM_OFF = 2
MG_LINE_RATIO = 1.35
MG_FADE = (220, 570)
MG_BLOCK_MAX = 520
_font_path: Optional[str] = None


def _font_ok(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        ImageFont.truetype(path, 20)
        return True
    except OSError:
        return False


async def ensure_font() -> str:
    """名言画像用フォントを用意する。無ければ自動ダウンロード、全部失敗ならOS標準の日本語フォントを使う"""
    global _font_path
    if _font_path:
        return _font_path
    for name, url in FONT_SOURCES:
        path = os.path.join(DATA_DIR, name)
        if _font_ok(path):
            _font_path = path
            return path
        try:
            async with bot.session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                resp.raise_for_status()
                data = await resp.read()
            if len(data) < 100_000:
                raise RuntimeError("フォントのダウンロードに失敗しました")
            with open(path + ".tmp", "wb") as f:
                f.write(data)
            os.replace(path + ".tmp", path)
            if _font_ok(path):
                _font_path = path
                return path
        except Exception:
            log.warning("フォントの取得に失敗: %s", url, exc_info=True)
    for path in FONT_CANDIDATES:
        if _font_ok(path):
            _font_path = path
            return path
    raise RuntimeError("日本語フォントが見つかりません")


def _wrap(text: str, font, max_w: int) -> list:
    """幅に合わせて自動改行。句読点の行頭/開き括弧の行末を避け、英単語は途中で切らない"""
    lines = []
    for para in text.split("\n"):
        cur = ""
        for tok in re.findall(r"[A-Za-z0-9_'’\-]+|\s+|.", para):
            if not cur and tok.isspace():
                continue
            if font.getlength(cur + tok) <= max_w or (cur and tok in KINSOKU):
                cur += tok
                continue
            tail = ""
            if cur and cur[-1] in OPENERS:
                tail, cur = cur[-1], cur[:-1]
            if cur.strip():
                lines.append(cur.rstrip())
            cur = tail
            if tok.isspace():
                continue
            if font.getlength(cur + tok) > max_w:
                for ch in tok:
                    if cur and font.getlength(cur + ch) > max_w and ch not in KINSOKU:
                        lines.append(cur)
                        cur = ch
                    else:
                        cur += ch
            else:
                cur += tok
        lines.append(cur)
    return lines


def _ellipsize(text: str, font, max_w: int) -> str:
    if font.getlength(text) <= max_w:
        return text
    while text and font.getlength(text + "…") > max_w:
        text = text[:-1]
    return text + "…"


def _draw_oblique(img, text: str, font, cx: float, baseline: float, fill, shear: float) -> None:
    """日本語フォントには斜体が無いので、基準線を軸に傾けて擬似斜体にする"""
    pad = int(font.size * 0.6) + 4
    w, h = int(font.getlength(text)) + pad * 2, font.size * 2
    base = int(font.size * 1.3)
    layer = Image.new("L", (w, h), 0)
    ImageDraw.Draw(layer).text((pad, base), text, font=font, fill=255, anchor="ls")
    layer = layer.transform((w, h), Image.Transform.AFFINE, (1, shear, -shear * base, 0, 1, 0),
                            Image.Resampling.BICUBIC)
    x = round(cx - font.getlength(text) / 2) - pad
    img.paste(Image.new("RGB", (w, h), fill), (x, round(baseline) - base), layer)


def draw_quote_text(img, text: str, author: str, handle: str, fg, sub, font_path: str) -> None:
    draw = ImageDraw.Draw(img)
    for size in range(MG_TITLE_MAX, MG_TITLE_MIN - 1, -2):
        font = ImageFont.truetype(font_path, size)
        lines = _wrap(text, font, MG_AREA_W)
        lh = round(size * MG_LINE_RATIO)
        fixed = MG_TOP_RATIO * size + MG_GAP_AUTHOR + MG_GAP_HANDLE + MG_BOTTOM_OFF
        if fixed + (len(lines) - 1) * lh <= MG_BLOCK_MAX:
            break
    else:
        keep = max(1, int((MG_BLOCK_MAX - fixed) // lh) + 1)
        if len(lines) > keep:
            lines = lines[:keep]
            lines[-1] = _ellipsize(lines[-1].rstrip() + "…", font, MG_AREA_W)
    n = len(lines)
    top_off = MG_TOP_RATIO * size
    block_h = top_off + (n - 1) * lh + MG_GAP_AUTHOR + MG_GAP_HANDLE + MG_BOTTOM_OFF
    center = (MG_TITLE_BASE - MG_TOP_RATIO * MG_TITLE_MAX
              + MG_TITLE_BASE + MG_GAP_AUTHOR + MG_GAP_HANDLE + MG_BOTTOM_OFF) / 2
    base = center - block_h / 2 + top_off
    for i, line in enumerate(lines):
        draw.text((MG_CX - font.getlength(line) / 2, base + i * lh), line, font=font, fill=fg, anchor="ls")
    a_base = base + (n - 1) * lh + MG_GAP_AUTHOR
    h_base = a_base + MG_GAP_HANDLE
    af = ImageFont.truetype(font_path, MG_AUTHOR_SIZE)
    hf = ImageFont.truetype(font_path, MG_HANDLE_SIZE)
    _draw_oblique(img, _ellipsize("- " + author, af, MG_AREA_W), af, MG_CX + MG_AUTHOR_DX, a_base, fg, MG_SHEAR)
    handle = _ellipsize(handle, hf, MG_AREA_W)
    draw.text((MG_CX - hf.getlength(handle) / 2, h_base), handle, font=hf, fill=sub, anchor="ls")


def render_meigen(avatar_bytes: bytes, text: str, author: str, handle: str, style: str, color: bool, font_path: str) -> io.BytesIO:
    dark = style == "black"
    bg = (0, 0, 0) if dark else (245, 245, 245)
    fg = (250, 250, 250) if dark else (10, 10, 10)
    sub = (70, 70, 70) if dark else (185, 185, 185)

    img = Image.new("RGB", (MG_W, MG_H), bg)
    av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    flat = Image.new("RGBA", av.size, bg + (255,))
    flat.alpha_composite(av)
    av = ImageOps.fit(flat.convert("RGB"), (MG_H, MG_H), Image.Resampling.LANCZOS)
    if not color:
        av = ImageOps.grayscale(av).convert("RGB")
    f0, f1 = MG_FADE
    mask = Image.new("L", (MG_H, MG_H), 0)
    md = ImageDraw.Draw(mask)
    for x in range(MG_H):
        t = min(1.0, max(0.0, (x - f0) / (f1 - f0)))
        md.line([(x, 0), (x, MG_H)], fill=round(255 * (1 - t * t * (3 - 2 * t))))
    img.paste(av, (0, 0), mask)

    draw_quote_text(img, text, author, handle, fg, sub, font_path)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


WELCOME_STYLES = {"black": ((18, 20, 28), (40, 44, 66), (245, 246, 250), (160, 166, 190), (88, 101, 242)),
                  "white": ((250, 250, 252), (222, 228, 250), (24, 26, 34), (110, 116, 140), (88, 101, 242)),
                  "blue": ((38, 52, 150), (88, 101, 242), (255, 255, 255), (214, 220, 255), (255, 255, 255))}


def _wl_vars(text: str, name: str, guild_name: str, count: int) -> str:
    return text.replace("{user}", name).replace("{server}", guild_name).replace("{count}", str(count))


def render_welcome(avatar_bytes: bytes, name: str, title: str, subtitle: str, count_text: str, style: str,
                   color: bool, font_path: str, bg_bytes: Optional[bytes] = None) -> io.BytesIO:
    W, H = 1000, 360
    bg1, bg2, fg, sub, accent = WELCOME_STYLES.get(style, WELCOME_STYLES["black"])
    img = Image.new("RGB", (W, H), bg1)
    d = ImageDraw.Draw(img)
    if bg_bytes:
        photo = ImageOps.fit(Image.open(io.BytesIO(bg_bytes)).convert("RGB"), (W, H), Image.Resampling.LANCZOS)
        img = Image.blend(photo, Image.new("RGB", (W, H), bg1), 0.6)
        d = ImageDraw.Draw(img)
    else:
        for x in range(W):
            t = x / (W - 1)
            d.line([(x, 0), (x, H)], fill=tuple(round(bg1[i] + (bg2[i] - bg1[i]) * t) for i in range(3)))
    S, cx, cy = 220, 40 + 110 + 20, H // 2
    av = Image.open(io.BytesIO(avatar_bytes)).convert("RGB")
    av = ImageOps.fit(av, (S, S), Image.Resampling.LANCZOS)
    if not color:
        av = ImageOps.grayscale(av).convert("RGB")
    ring = S + 16
    big = Image.new("L", (ring * 4, ring * 4), 0)
    ImageDraw.Draw(big).ellipse((0, 0, ring * 4 - 1, ring * 4 - 1), fill=255)
    img.paste(Image.new("RGB", (ring, ring), accent), (cx - ring // 2, cy - ring // 2), big.resize((ring, ring), Image.Resampling.LANCZOS))
    m = Image.new("L", (S * 4, S * 4), 0)
    ImageDraw.Draw(m).ellipse((0, 0, S * 4 - 1, S * 4 - 1), fill=255)
    img.paste(av, (cx - S // 2, cy - S // 2), m.resize((S, S), Image.Resampling.LANCZOS))
    left, area = cx + ring // 2 + 44, W - (cx + ring // 2 + 44) - 40
    tf, nf, sf = (ImageFont.truetype(font_path, z) for z in (70, 40, 26))
    title = _ellipsize(title, tf, area)
    name = _ellipsize(name, nf, area)
    lines = _wrap(subtitle, sf, area)[:2]
    if count_text:
        lines.append(count_text)
    block = 70 + 18 + 40 + 16 + len(lines) * 36
    y = (H - block) // 2
    d.text((left, y + 62), title, font=tf, fill=fg, anchor="ls")
    d.rectangle((left, y + 80, left + 80, y + 85), fill=accent)
    d.text((left, y + 138), name, font=nf, fill=fg, anchor="ls")
    for i, ln in enumerate(lines):
        d.text((left, y + 190 + i * 36), ln, font=sf, fill=sub, anchor="ls")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


WELCOME_BG_DIR = os.path.join(DATA_DIR, "welcome_bg")


def welcome_bg_path(guild_id: int) -> str:
    return os.path.join(WELCOME_BG_DIR, f"{int(guild_id)}.jpg")


def save_welcome_bg(guild_id: int, data: bytes) -> None:
    """アップロードされた画像を検証し、1000x360 に整えて保存する(別スレッドで実行)"""
    try:
        im = Image.open(io.BytesIO(data))
        fmt, (w, h) = im.format, im.size
    except Exception:
        raise SettingsError("画像として読み込めませんでした。PNG・JPEG・WebP・GIF を選んでください。")
    if fmt not in ("PNG", "JPEG", "WEBP", "GIF"):
        raise SettingsError("PNG・JPEG・WebP・GIF の画像だけ使えます。")
    if w * h > 40_000_000:
        raise SettingsError("画像が大きすぎます。(4000万画素まで)")
    try:
        im = ImageOps.fit(ImageOps.exif_transpose(im).convert("RGB"), (1000, 360), Image.Resampling.LANCZOS)
    except Exception:
        raise SettingsError("画像を処理できませんでした。別の画像でお試しください。")
    os.makedirs(WELCOME_BG_DIR, exist_ok=True)
    tmp = welcome_bg_path(guild_id) + ".tmp"
    im.save(tmp, "JPEG", quality=88)
    os.replace(tmp, welcome_bg_path(guild_id))


def _read_welcome_bg(guild_id: int) -> Optional[bytes]:
    try:
        with open(welcome_bg_path(guild_id), "rb") as f:
            return f.read()
    except OSError:
        return None


async def make_welcome_file(member: discord.Member, im: dict) -> discord.File:
    font_path = await ensure_font()
    avatar = await member.display_avatar.replace(size=512, format="png").read()
    g, n = member.guild, member.display_name
    bg = await run_heavy(_read_welcome_bg, g.id) if im.get("bg") else None
    buf = await run_heavy(
        render_welcome, avatar, n, _wl_vars(im.get("title") or "WELCOME", n, g.name, g.member_count),
        _wl_vars(im.get("subtitle") or "", n, g.name, g.member_count),
        f"{g.member_count} 人目のメンバー" if im.get("show_count", True) else "",
        im.get("style", "black"), bool(im.get("color", True)), font_path, bg)
    return discord.File(buf, filename="welcome.png")


async def make_meigen_file(user: discord.abc.User, text: str, author: Optional[str], style: str, color: bool) -> discord.File:
    font_path = await ensure_font()
    avatar = await user.display_avatar.replace(size=1024, format="png").read()
    buf = await run_heavy(render_meigen, avatar, text, author or user.display_name,
                          f"@{user.name}", style, color, font_path)
    return discord.File(buf, filename="meigen.png")


MEIGEN_ASK_COOLDOWN = 24 * 3600


def meigen_pref_embed(state: Optional[str]) -> discord.Embed:
    label = {"allow": "✅ 許可している", "deny": "🚫 許可しない"}.get(state, "❓ 未設定(使われそうになったときにDMで確認します)")
    e = make_embed("🖼️ 名言画像への使用設定", color=BLUE)
    e.description = ("他の人が `/meigen` や「名言画像にする」で、**あなたのアイコン・名前**を使った名言画像を作ってよいかを選べます。\n"
                     "自分自身の名言画像を作ることは、この設定に関係なくできます。")
    e.add_field(name="現在の設定", value=label, inline=False)
    e.set_footer(text="このメッセージのボタンから、いつでも変更できます。(/meigenprivacy でも変更できます)")
    return e


class MeigenConsentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _set(self, interaction: discord.Interaction, value: Optional[str]):
        rec = user_prefs.rec(interaction.user.id)
        if value:
            rec["meigen"] = value
        else:
            rec.pop("meigen", None)
        user_prefs.save()
        await interaction.response.edit_message(embed=meigen_pref_embed(value), view=MeigenConsentView())

    @discord.ui.button(label="許可する", emoji="✅", style=discord.ButtonStyle.success, custom_id="azq:mg:allow")
    async def allow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set(interaction, "allow")

    @discord.ui.button(label="許可しない", emoji="🚫", style=discord.ButtonStyle.danger, custom_id="azq:mg:deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set(interaction, "deny")

    @discord.ui.button(label="未設定に戻す", style=discord.ButtonStyle.secondary, custom_id="azq:mg:reset")
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set(interaction, None)


async def meigen_gate(interaction: discord.Interaction, target: discord.abc.User) -> bool:
    """名言画像を作ってよいか判定する。作れない場合は応答まで済ませて False を返す。"""
    if interaction.guild and not store.get(interaction.guild.id)["meigen"]["enabled"]:
        await interaction.response.send_message("🚫 このサーバーでは、管理者により名言画像が無効になっています。", ephemeral=True)
        return False
    if target.id == interaction.user.id or target.bot:
        return True
    rec = user_prefs.rec(target.id)
    pref = rec.get("meigen")
    if pref == "allow":
        return True
    if pref == "deny":
        await interaction.response.send_message("🚫 このユーザーは、自分のアイコン・名前を名言画像に使うことを許可していません。", ephemeral=True)
        return False
    if time.time() - rec.get("asked", 0) < MEIGEN_ASK_COOLDOWN:
        await interaction.response.send_message("⏳ このユーザーにはすでにDMで確認しています。返答があるまでお待ちください。", ephemeral=True)
        return False
    rec["asked"] = time.time()
    user_prefs.save()
    await interaction.response.send_message("📨 このユーザーにDMで確認しています...", ephemeral=True)
    e = make_embed("🖼️ 名言画像への使用の確認", color=BLUE)
    where = f"サーバー「{interaction.guild.name}」で" if interaction.guild else ""
    e.description = (f"**{interaction.user}** さんが{where}、あなたのアイコン・名前を使った名言画像を作ろうとしました。\n\n"
                     "今後、他の人があなたのアイコン・名前を使って名言画像を作ることを許可しますか?\n"
                     "下のボタンで選んでください。選ぶまでは作成されません。")
    e.set_footer(text="あとから /meigenprivacy でも変更できます。心当たりがなければ「許可しない」を選んでください。")
    try:
        await target.send(embed=e, view=MeigenConsentView())
        await interaction.edit_original_response(content="📨 このユーザーにDMで確認しました。許可されたら、もう一度実行してください。")
    except discord.HTTPException:
        rec["asked"] = 0
        user_prefs.save()
        await interaction.edit_original_response(
            content="⚠️ DMを送れなかったため、本人の許可を確認できません。本人に `/meigenprivacy` で許可してもらってください。")
    return False


@bot.tree.command(name="meigenprivacy", description="他の人があなたのアイコン・名前で名言画像を作ってよいかを設定します")
async def meigen_privacy(interaction: discord.Interaction):
    await interaction.response.send_message(embed=meigen_pref_embed(user_prefs.rec(interaction.user.id).get("meigen")),
                                            view=MeigenConsentView(), ephemeral=True)


@bot.tree.command(name="meigen", description="名言画像を作ります")
@app_commands.describe(
    text="名言の内容(改行は \\n と入力)", user="発言者のアイコンを使うユーザー(省略すると自分。他の人は本人の許可が必要)",
    author="表示する名前(省略するとユーザー名)", style="背景の色", color="アイコンをカラーにする(OFFでモノクロ)",
)
@app_commands.choices(style=[
    app_commands.Choice(name="ブラック", value="black"),
    app_commands.Choice(name="ホワイト", value="white"),
])
@app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
async def meigen(interaction: discord.Interaction, text: app_commands.Range[str, 1, 200],
                 user: Optional[discord.User] = None, author: Optional[app_commands.Range[str, 1, 30]] = None,
                 style: Optional[app_commands.Choice[str]] = None, color: bool = True):
    target = user or interaction.user
    if not await meigen_gate(interaction, target):
        return
    await interaction.response.defer()
    try:
        file = await make_meigen_file(target, text.replace("\\n", "\n"), author,
                                      style.value if style else "black", color)
    except Exception:
        log.exception("名言画像の生成に失敗")
        return await interaction.followup.send("⚠️ 画像の生成に失敗しました。日本語フォントを取得できなかった可能性があります。")
    await interaction.followup.send(file=file)


@bot.tree.context_menu(name="名言画像にする")
async def meigen_ctx(interaction: discord.Interaction, message: discord.Message):
    text = message.clean_content.strip()
    if not text:
        return await interaction.response.send_message("❌ テキストのあるメッセージで使ってください。", ephemeral=True)
    if not await meigen_gate(interaction, message.author):
        return
    await interaction.response.defer()
    try:
        file = await make_meigen_file(message.author, text[:200], None, "black", True)
    except Exception:
        log.exception("名言画像の生成に失敗")
        return await interaction.followup.send("⚠️ 画像の生成に失敗しました。日本語フォントを取得できなかった可能性があります。")
    await interaction.followup.send(file=file)


async def is_public_host(host: str) -> bool:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


@bot.tree.command(name="ping", description="BOTの応答速度、またはWebサイトのpingを測定します")
@app_commands.describe(target="Webサイトのドメイン/URL(省略するとBOTの速度)")
async def ping(interaction: discord.Interaction, target: Optional[str] = None):
    if not target:
        start = time.perf_counter()
        await interaction.response.send_message("🏓 計測中...")
        api_ms = (time.perf_counter() - start) * 1000
        ws = bot.latency * 1000
        up = int(time.time() - bot.started_at)
        d, rem = divmod(up, 86400)
        h, rem = divmod(rem, 3600)
        m, s = divmod(rem, 60)
        e = make_embed("🏓 Pong!", color=GREEN if api_ms < 300 else YELLOW)
        e.add_field(name="WebSocket", value=f"{ws:.0f} ms")
        e.add_field(name="API応答", value=f"{api_ms:.0f} ms")
        e.add_field(name="稼働時間", value=f"{d}日 {h}時間 {m}分 {s}秒")
        e.add_field(name="サーバー数", value=str(len(bot.guilds)))
        await interaction.edit_original_response(content=None, embed=e)
        return

    await interaction.response.defer()
    url = target if re.match(r"^https?://", target, re.I) else f"https://{target}"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.port not in (None, 80, 443):
        return await interaction.followup.send("❌ 有効なURL/ドメインを指定してください。")
    if not await is_public_host(parsed.hostname):
        return await interaction.followup.send("❌ 名前解決できない、または内部アドレスのため測定できません。")
    start = time.perf_counter()
    try:
        async with bot.session.get(url, timeout=aiohttp.ClientTimeout(total=8), allow_redirects=False) as resp:
            ms = (time.perf_counter() - start) * 1000
            e = make_embed(f"🌐 ping: {parsed.hostname}", color=GREEN if resp.status < 400 else YELLOW)
            e.add_field(name="ステータス", value=f"{resp.status} {resp.reason}")
            e.add_field(name="応答時間", value=f"{ms:.0f} ms")
    except asyncio.TimeoutError:
        e = make_embed(f"🌐 ping: {parsed.hostname}", "⏱️ 8秒以内に応答がありませんでした。", RED)
    except aiohttp.ClientError as err:
        e = make_embed(f"🌐 ping: {parsed.hostname}", f"❌ 接続エラー: {type(err).__name__}", RED)
    await interaction.followup.send(embed=e)


# ═════════════════════════ サーバー運営(役職・申請・応募・ロール・ポイント) ═════════════════════════
# 役職(管理者〜一般スタッフ)ごとの権限管理 / 参加申請・スタッフ応募 / ロール管理 / ポイント・ランキング / 管理ログ。
# データは DATA_DIR/server_admin.json に保存される。/web のサーバー管理ページ(/web/manage)も、ここの処理を共通で使う。

NONE = discord.AllowedMentions.none()

RANK_NAMES = {5: "管理者", 4: "副管理者", 3: "幹部", 2: "モデレーター", 1: "一般スタッフ"}

# key: (既定の必要ランク, 説明)
PERMS = {
    "warn": (2, "警告を与える (/warn)"),
    "warnings": (1, "警告履歴を見る (/warnings)"),
    "unwarn": (3, "警告を1件取り消す (/unwarn)"),
    "clearwarns": (3, "警告を全消去 (/clearwarns)"),
    "timeout": (2, "タイムアウト (/timeout)"),
    "untimeout": (2, "タイムアウト解除 (/untimeout)"),
    "kick": (3, "キック (/kick)"),
    "ban": (4, "BAN (/ban)"),
    "unban": (4, "BAN解除 (/unban)"),
    "purge": (2, "メッセージ一括削除 (/purge)"),
    "slowmode": (2, "低速モード (/slowmode)"),
    "lock": (2, "チャンネルのロック・解除 (/lock /unlock)"),
    "role_add": (3, "ロール付与 (/role_add)"),
    "role_remove": (3, "ロール剥奪 (/role_remove)"),
    "role_grant": (3, "登録ロールの付与・剥奪 (/manage role_grant)"),
    "apply_review": (2, "参加申請の承認・却下"),
    "staff_review": (3, "スタッフ応募の審査(志望役職より上の役職が必要)"),
    "points_add": (2, "ポイント付与 (/points add)"),
    "points_remove": (3, "ポイント減算 (/points remove)"),
    "points_undo": (3, "ポイント履歴の取り消し (/points undo)"),
    "points_peek": (2, "他人のポイント履歴を見る"),
    "mvp": (4, "月間MVPの発表 (/points mvp)"),
    "audit_view": (3, "管理ログ・各種履歴の閲覧"),
    "rank_manage": (5, "役職・各種設定の変更(変更不可)"),
}
HEAVY = {"kick", "ban", "timeout", "purge"}
HEAVY_LIMIT, HEAVY_WINDOW = 5, 600

CAT_CHOICES = [app_commands.Choice(name=n, value=v) for v, n in (
    ("info", "情報共有"), ("article", "記事・投稿"), ("sns", "SNS運用"), ("ops", "運営活動"), ("other", "その他"))]
CAT_NAMES = {"info": "情報共有", "article": "記事・投稿", "sns": "SNS運用", "ops": "運営活動", "other": "その他",
             "auto": "自動", "undo": "取消"}

REGIONS = {
    "北海道": ["北海道"],
    "東北": ["青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"],
    "関東": ["茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県"],
    "中部": ["新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県", "愛知県"],
    "近畿": ["三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"],
    "中国": ["鳥取県", "島根県", "岡山県", "広島県", "山口県"],
    "四国": ["徳島県", "香川県", "愛媛県", "高知県"],
    "九州・沖縄": ["福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"],
}
PREF_TO_REGION = {p: r for r, ps in REGIONS.items() for p in ps}


def _norm_pref(s: str) -> str:
    s = re.sub(r"\s+", "", s or "")
    return s if s == "北海道" else (s[:-1] if s and s[-1] in "都府県" else s)


PREF_NORM = {_norm_pref(p): p for p in PREF_TO_REGION}


def match_pref(text: str) -> Optional[str]:
    """回答が都道府県名と完全に一致するときだけ返す(「京都」と「東京都」の部分一致を避ける)"""
    return PREF_NORM.get(_norm_pref((text or "").strip()))


LG_DEFAULTS = {
    "ranks": {"5": None, "4": None, "3": None, "2": None, "1": None},
    "perm": {},
    "slots": {},
    "temp_roles": [],
    "role_hist": [],
    "audit": [],
    "tickets": [],
    "apply": {
        "enabled": False, "panel_channel": None, "panel_message": None, "review_channel": None, "role": None,
        "title": "📝 参加申請",
        "text": "参加を希望される方は、下のボタンから申請してください。\n内容を確認し、スタッフが承認・却下します。結果はDMでお知らせします。",
        "questions": ["参加の動機を教えてください", "お住まいの都道府県(例: 福岡県)", "自己紹介・活動できる時間帯"],
        "cooldown_hours": 24, "counter": 0, "apps": {},
    },
    "staff": {
        "enabled": False, "panel_channel": None, "panel_message": None, "review_channel": None,
        "title": "🧑‍💼 運営スタッフ募集",
        "text": "一緒に運営してくれる仲間を募集しています。\n下のメニューから希望する役職を選んで応募してください。審査結果はDMでお知らせします。",
        "questions": ["志望動機", "これまでの経験・実績", "活動できる時間帯・頻度"],
        "cooldown_hours": 72, "counter": 0, "apps": {},
        "positions": {
            "info": {"label": "情報収集スタッフ", "rank": 1, "role": None, "enabled": True},
            "writer": {"label": "記事・投稿作成スタッフ", "rank": 1, "role": None, "enabled": True},
            "sns": {"label": "SNS運用スタッフ", "rank": 1, "role": None, "enabled": True},
            "discord": {"label": "Discord運営スタッフ", "rank": 1, "role": None, "enabled": True},
            "mod": {"label": "モデレーター", "rank": 2, "role": None, "enabled": True},
            "exec": {"label": "幹部", "rank": 3, "role": None, "enabled": True},
            "vice": {"label": "副管理者", "rank": 4, "role": None, "enabled": True},
        },
    },
    "points": {
        "balance": {}, "daily": {}, "log": [], "counter": 0,
        "max_award": 100, "staff_daily_budget": 300, "user_daily_cap": 200, "alert_threshold": 100,
        "auto_channels": [], "auto_points": 1, "auto_min_len": 30, "auto_cooldown": 120, "auto_daily_cap": 20,
        "min_member_days": 3,
        "used": {"date": "", "give": {}, "get": {}, "auto": {}},
        "mvp_channel": None, "mvp_role": None, "mvp_auto": True, "mvp_last": "", "mvp_hist": [],
    },
    "region": {"pref": {}, "region": {}, "panel_channel": None, "panel_message": None},
}

SEC = {"j": "apply", "s": "staff"}
LABEL = {"j": "参加申請", "s": "スタッフ応募"}


def _merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def cap(lst: list, n: int) -> None:
    if len(lst) > n:
        del lst[:len(lst) - n]


class SrvAdmStore:
    SAVE_DELAY = 5.0

    def __init__(self, directory: str):
        os.makedirs(directory, exist_ok=True)
        self.path = os.path.join(directory, "server_admin.json")
        self.data: dict = {}
        self._dirty = False
        self._task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    raw = json.load(f)
                for gid, cfg in raw.items():
                    self.data[gid] = _merge(copy.deepcopy(LG_DEFAULTS), cfg)
            except Exception:
                log.exception("server_admin.json を読み込めませんでした。壊れたファイルを server_admin.json.broken に退避して空で起動します。")
                try:
                    os.replace(self.path, self.path + ".broken")
                except OSError:
                    pass
                self.data = {}

    def get(self, gid: int) -> dict:
        k = str(gid)
        if k not in self.data:
            self.data[k] = copy.deepcopy(LG_DEFAULTS)
        return self.data[k]

    def save(self) -> None:
        self._dirty = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return self.flush()
        if self._task is None or self._task.done():
            self._task = loop.create_task(self._later())

    async def _later(self) -> None:
        while self._dirty:
            await asyncio.sleep(self.SAVE_DELAY)
            await self.flush_async()

    def _dump(self) -> str:
        return json.dumps(self.data, ensure_ascii=False, separators=(",", ":"))

    def _write(self, payload: str) -> None:
        with self._lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp, self.path)

    async def flush_async(self) -> None:
        if not self._dirty:
            return
        self._dirty = False
        try:
            payload = self._dump()
            await asyncio.get_running_loop().run_in_executor(None, self._write, payload)
        except Exception:
            self._dirty = True
            log.exception("server_admin.json の保存に失敗しました")

    def flush(self) -> None:
        if not self._dirty:
            return
        self._dirty = False
        try:
            self._write(self._dump())
        except Exception:
            self._dirty = True
            log.exception("server_admin.json の保存に失敗しました")


lg = SrvAdmStore(DATA_DIR)
atexit.register(lg.flush)


async def srvadm_flush() -> None:
    await lg.flush_async()


# ───────────────────────── 共通ヘルパー ─────────────────────────

async def eph(interaction: discord.Interaction, text: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True, allowed_mentions=NONE)
    else:
        await interaction.response.send_message(text, ephemeral=True, allowed_mentions=NONE)


def rname(r: int) -> str:
    return RANK_NAMES.get(r, "役職なし")


def can_post(ch, me: discord.Member) -> bool:
    p = ch.permissions_for(me)
    return p.view_channel and p.send_messages and p.embed_links


def dangerous(role: discord.Role) -> list:
    return [n for n in DANGEROUS_PERMS if getattr(role.permissions, n)]


def bot_can_grant(g: discord.Guild, role: Optional[discord.Role]) -> bool:
    me = g.me
    return bool(role and not role.is_default() and not role.managed and role < me.top_role
                and me.guild_permissions.manage_roles)


def jst(ts: float, fmt: str = "%m/%d %H:%M") -> str:
    return datetime.fromtimestamp(ts, JST).strftime(fmt)


# ───────────────────────── 共通の処理本体(スラッシュコマンドと /web の両方から使う) ─────────────────────────

class SrvAdmError(Exception):
    """利用者にそのまま見せるエラー(スラッシュコマンドとWebで共通)"""


def lg_guard(fn):
    """コマンドの中で起きた SrvAdmError を、本人にだけ見えるエラーメッセージとして返す"""
    @functools.wraps(fn)
    async def wrapper(interaction, *args, **kwargs):
        try:
            return await fn(interaction, *args, **kwargs)
        except SrvAdmError as e:
            await eph(interaction, f"❌ {e}")
    return wrapper


def need_rank(g: discord.Guild, m, key: str) -> None:
    r, n = rank_of(m), need(g.id, key)
    if r < n:
        raise SrvAdmError(f"この操作には「{rname(n)}」以上の役職が必要です。(あなた: {rname(r)})")


def _lgctx(g: discord.Guild, u):
    """role_problem() に渡すための、interaction の代わり"""
    return SimpleNamespace(guild=g, user=u)


def core_rank_set(g: discord.Guild, rank: int, role: Optional[discord.Role]) -> str:
    if rank not in RANK_NAMES:
        raise SrvAdmError("役職が正しくありません。")
    ranks = lg.get(g.id)["ranks"]
    if role:
        if role.is_default() or role.managed:
            raise SrvAdmError("@everyone やBOT管理のロールは指定できません。")
        for k, rid in ranks.items():
            if rid == role.id and int(k) != rank:
                raise SrvAdmError(f"そのロールはすでに「{rname(int(k))}」に設定されています。")
    ranks[str(rank)] = role.id if role else None
    lg.save()
    extra = "\n⚠️ このロールを持つ人は、BOTの全機能を操作できる管理者になります。ロールの付与権限は慎重に管理してください。" if role and rank == 5 else ""
    return f"✅ {rname(rank)}: {role.name if role else '解除'}{extra}"


async def core_perm_set(g: discord.Guild, actor, key: str, rank: Optional[int]) -> str:
    if key not in PERMS or key == "rank_manage":
        raise SrvAdmError("その機能は変更できません。候補から選んでください。")
    if rank is not None and rank not in RANK_NAMES:
        raise SrvAdmError("役職が正しくありません。")
    ov = lg.get(g.id)["perm"]
    if rank is not None:
        ov[key] = rank
    else:
        ov.pop(key, None)
    lg.save()
    await send_log(g, make_embed("🔑 権限の変更", f"`{key}` → {rname(need(g.id, key))}以上\n実行者: {actor}", YELLOW))
    return f"✅ `{key}` の必要役職: **{rname(need(g.id, key))}以上**"


def core_role_set(g: discord.Guild, user, name: str, role: discord.Role) -> str:
    name = (name or "").strip()
    if not 1 <= len(name) <= 20:
        raise SrvAdmError("登録名は1〜20文字で入力してください。")
    if p := role_problem(_lgctx(g, user), role, True):
        raise SrvAdmError(p)
    slots = lg.get(g.id)["slots"]
    if name not in slots and len(slots) >= 50:
        raise SrvAdmError("登録できるロールは50個までです。")
    slots[name] = role.id
    lg.save()
    return f"✅ 「{name}」= {role.name} を登録しました。`/manage role_grant` か、Webの「ロール」から付与できます。"


def core_role_unset(g: discord.Guild, name: str) -> str:
    if lg.get(g.id)["slots"].pop(name, None) is None:
        raise SrvAdmError("その登録名はありません。")
    lg.save()
    return f"✅ 「{name}」を登録から外しました。(Discord上のロールは消えません)"


async def core_role_grant(g: discord.Guild, actor, member: discord.Member, name: str, days: Optional[int]) -> str:
    c = lg.get(g.id)
    role = g.get_role(c["slots"].get(name) or 0)
    if not role:
        raise SrvAdmError("その登録名のロールがありません。登録ロールの一覧を確認してください。")
    if days is not None and not 1 <= days <= 365:
        raise SrvAdmError("日数は 1〜365 で指定してください。")
    if member.bot:
        raise SrvAdmError("BOTには付与できません。")
    if member.id == actor.id and rank_of(actor) < 5:
        raise SrvAdmError("自分自身には付与できません。")
    if err := role_grant_error(g, actor, role):
        raise SrvAdmError(err)
    try:
        await member.add_roles(role, reason=f"AZQ BOT ロール付与 by {actor}")
    except discord.HTTPException:
        raise SrvAdmError("付与に失敗しました。BOTの権限を確認してください。")
    c["temp_roles"] = [t for t in c["temp_roles"] if not (t["u"] == member.id and t["r"] == role.id)]
    if days:
        c["temp_roles"].append({"u": member.id, "r": role.id, "exp": time.time() + days * 86400, "by": actor.id})
        cap(c["temp_roles"], 5000)
    lg.save()
    await send_log(g, make_embed("🏷️ ロール付与", f"{member} (`{member.id}`) ← {role.name}\n実行者: {actor}"
                                 + (f"\n期限: {days}日後" if days else ""), GREEN))
    return f"✅ {member.display_name} に {role.name} を付与しました。" + (f"({days}日後に自動で外れます)" if days else "")


async def core_role_revoke(g: discord.Guild, actor, member: discord.Member, name: str) -> str:
    c = lg.get(g.id)
    role = g.get_role(c["slots"].get(name) or 0)
    if not role:
        raise SrvAdmError("その登録名のロールがありません。")
    if err := role_grant_error(g, actor, role):
        raise SrvAdmError(err)
    try:
        if role in member.roles:
            await member.remove_roles(role, reason=f"AZQ BOT ロール剥奪 by {actor}")
    except discord.HTTPException:
        raise SrvAdmError("剥奪に失敗しました。BOTの権限を確認してください。")
    c["temp_roles"] = [t for t in c["temp_roles"] if not (t["u"] == member.id and t["r"] == role.id)]
    lg.save()
    await send_log(g, make_embed("🏷️ ロール剥奪", f"{member} (`{member.id}`) ← {role.name}\n実行者: {actor}", YELLOW))
    return f"✅ {member.display_name} から {role.name} を外しました。"


def core_set_questions(g: discord.Guild, kind: str, questions) -> str:
    qs = [str(x).strip() for x in questions if str(x).strip()]
    if kind not in SEC or not 1 <= len(qs) <= 5 or any(len(x) > 45 for x in qs):
        raise SrvAdmError("質問は1〜5個、各45文字以内にしてください。")
    lg.get(g.id)[SEC[kind]]["questions"] = qs
    lg.save()
    return "✅ 質問を更新しました。(「都道府県」を含む質問の回答は、地域ロールの自動付与に使われます)"


async def core_apply_setup(g: discord.Guild, user, panel, review, role: discord.Role, cooldown: Optional[int]) -> str:
    if p := role_problem(_lgctx(g, user), role, True):
        raise SrvAdmError(f"承認ロール: {p}")
    if err := _setup_common(g, panel, review):
        raise SrvAdmError(err)
    if cooldown is not None and not 0 <= cooldown <= 720:
        raise SrvAdmError("再申請までの時間は 0〜720 時間で指定してください。")
    sec = lg.get(g.id)["apply"]
    sec.update(enabled=True, review_channel=review.id, role=role.id)
    if cooldown is not None:
        sec["cooldown_hours"] = cooldown
    try:
        await lg_post_panel(g, "j", panel)
    except discord.HTTPException:
        sec["enabled"] = False
        lg.save()
        raise SrvAdmError("パネルを送信できませんでした。BOTの権限を確認してください。")
    lg.save()
    return (f"✅ 参加申請を有効化しました。\nパネル: #{panel.name} / 審査: #{review.name} / 承認ロール: {role.name}\n"
            "質問の変更は `/apply questions` かWebから、履歴は `/apply history` です。" + _privacy_note(g, review))


async def core_apply_disable(g: discord.Guild) -> str:
    lg.get(g.id)["apply"]["enabled"] = False
    await lg_delete_panel(g, "j")
    lg.save()
    return "✅ 参加申請を無効化しました。(審査待ちの申請は、審査チャンネルやWebから処理できます)"


async def core_staff_setup(g: discord.Guild, panel, review, cooldown: Optional[int]) -> str:
    if err := _setup_common(g, panel, review):
        raise SrvAdmError(err)
    if cooldown is not None and not 0 <= cooldown <= 720:
        raise SrvAdmError("再応募までの時間は 0〜720 時間で指定してください。")
    c = lg.get(g.id)
    sec = c["staff"]
    sec.update(enabled=True, review_channel=review.id)
    if cooldown is not None:
        sec["cooldown_hours"] = cooldown
    try:
        await lg_post_panel(g, "s", panel)
    except discord.HTTPException:
        sec["enabled"] = False
        lg.save()
        raise SrvAdmError("パネルを送信できませんでした。BOTの権限を確認してください。")
    lg.save()
    noroles = [p["label"] for p in sec["positions"].values()
               if p["enabled"] and not p["role"] and not (p["rank"] >= 2 and c["ranks"].get(str(p["rank"])))]
    warn = ("\n⚠️ 次の役職は付与ロールが未設定です(合格にできません): " + " / ".join(noroles) + "\n`/staffapp position` かWebの「スタッフ応募」、`/manage rank_set` で設定してください。") if noroles else ""
    return (f"✅ スタッフ応募を有効化しました。\nパネル: #{panel.name} / 審査: #{review.name}\n"
            "審査できる役職: 一般職・モデレーターは幹部以上 / 幹部は副管理者以上 / 副管理者は管理者のみ" + warn + _privacy_note(g, review))


async def core_staff_disable(g: discord.Guild) -> str:
    lg.get(g.id)["staff"]["enabled"] = False
    await lg_delete_panel(g, "s")
    lg.save()
    return "✅ スタッフ応募を無効化しました。"


async def core_staff_position(g: discord.Guild, user, key: str, role: Optional[discord.Role], label: Optional[str],
                              enabled: Optional[bool], clear_role: bool) -> str:
    pos = lg.get(g.id)["staff"]["positions"].get(key)
    if not pos:
        raise SrvAdmError("その役職はありません。候補から選んでください。")
    if label is not None and not 1 <= len(label) <= 40:
        raise SrvAdmError("表示名は1〜40文字で入力してください。")
    warn = ""
    if role:
        if p := role_problem(_lgctx(g, user), role, False):
            raise SrvAdmError(p)
        pos["role"] = role.id
        if bad := dangerous(role):
            warn = "\n⚠️ このロールには強い権限が含まれています: " + ", ".join(bad)
    elif clear_role:
        pos["role"] = None
    if label:
        pos["label"] = label
    if enabled is not None:
        pos["enabled"] = enabled
    lg.save()
    await refresh_staff_panel(g)
    r = g.get_role(pos["role"]) if pos["role"] else None
    return f"✅ {pos['label']} (`{key}`): ロール {r.name if r else '未設定'} / 募集 {'ON' if pos['enabled'] else 'OFF'} / 役職ランク {rname(pos['rank'])}" + warn


async def core_region_create(g: discord.Guild, include_prefectures: bool) -> str:
    if not g.me.guild_permissions.manage_roles:
        raise SrvAdmError("BOTに「ロールの管理」権限がありません。")
    reg = lg.get(g.id)["region"]
    names = list(REGIONS) + (list(PREF_TO_REGION) if include_prefectures else [])
    existing = {r.name: r for r in g.roles if not r.managed and not r.is_default()}
    todo = [n for n in names if n not in existing]
    if len(g.roles) + len(todo) > 245:
        raise SrvAdmError(f"ロール数の上限(250)に近いため作成できません。(現在 {len(g.roles)} + 新規 {len(todo)})")
    created, skipped, failed = 0, [], 0
    for n in names:
        role = existing.get(n)
        if role is not None and dangerous(role):
            skipped.append(n)
            continue
        if role is None:
            try:
                role = await g.create_role(name=n, reason="AZQ BOT 地域ロール作成")
                created += 1
                await asyncio.sleep(0.5)
            except discord.HTTPException:
                failed += 1
                continue
        (reg["region"] if n in REGIONS else reg["pref"])[n] = role.id
    lg.save()
    return (f"✅ 作成 {created}件 / 登録済み {len(reg['region'])}地方・{len(reg['pref'])}都道府県"
            + (f"\n⚠️ 強い権限を持つ同名ロールは使いません: {', '.join(skipped)}" if skipped else "")
            + (f"\n⚠️ 作成に失敗: {failed}件" if failed else "")
            + "\n次に、選択パネルを設置してください。")


async def core_region_panel(g: discord.Guild, channel) -> str:
    if not can_post(channel, g.me):
        raise SrvAdmError(f"BOTが #{channel.name} に送信できません。")
    reg = lg.get(g.id)["region"]
    if not reg["pref"] and not reg["region"]:
        raise SrvAdmError("先に地域ロールを作成してください。")
    await lg_delete_panel(g, "r")
    e = make_embed("📍 地域ロール", "お住まいの地方 → 都道府県の順に選ぶと、地域ロールが付与されます。\n選び直すと自動で付け替わります。", BLUE)
    try:
        msg = await channel.send(embed=e, view=RegionPanelView())
    except discord.HTTPException:
        raise SrvAdmError("パネルを送信できませんでした。")
    reg["panel_channel"], reg["panel_message"] = channel.id, msg.id
    lg.save()
    return f"✅ #{channel.name} に設置しました。"


def core_region_set_role(g: discord.Guild, user, name: str, role: discord.Role) -> str:
    if name not in REGIONS and name not in PREF_TO_REGION:
        raise SrvAdmError("地方・都道府県の名前を候補から選んでください。")
    if p := role_problem(_lgctx(g, user), role, True):
        raise SrvAdmError(p)
    reg = lg.get(g.id)["region"]
    (reg["region"] if name in REGIONS else reg["pref"])[name] = role.id
    lg.save()
    return f"✅ {name} = {role.name}"


async def core_points_add(g: discord.Guild, actor, member: discord.Member, amount: int, reason: str, cat: str):
    if not 1 <= amount <= 100000:
        raise SrvAdmError("ポイントは 1〜100000 で指定してください。")
    reason = (reason or "").strip()
    if not 1 <= len(reason) <= 100:
        raise SrvAdmError("理由は1〜100文字で入力してください。")
    if cat not in CAT_NAMES or cat in ("auto", "undo"):
        cat = "other"
    if err := award_error(g, actor, member, amount, reason):
        raise SrvAdmError(err)
    ent = apply_points(g.id, member.id, amount, reason, actor.id, cat)
    p = lg.get(g.id)["points"]
    used = _used(p)
    used["give"][str(actor.id)] = used["give"].get(str(actor.id), 0) + amount
    used["get"][str(member.id)] = used["get"].get(str(member.id), 0) + amount
    lg.save()
    await send_log(g, make_embed("💰 ポイント付与" + (" (高額)" if amount >= p["alert_threshold"] else ""),
                                 f"{member} (`{member.id}`) +{amount}pt [#{ent['id']}]\n付与: {actor} (`{actor.id}`)\n理由: {reason}",
                                 YELLOW if amount >= p["alert_threshold"] else GREEN))
    return ent, p["balance"].get(str(member.id), 0)


async def core_points_remove(g: discord.Guild, actor, member: discord.Member, amount: int, reason: str):
    if not 1 <= amount <= 100000:
        raise SrvAdmError("ポイントは 1〜100000 で指定してください。")
    reason = (reason or "").strip()
    if not 1 <= len(reason) <= 100:
        raise SrvAdmError("理由は1〜100文字で入力してください。")
    if member.bot:
        raise SrvAdmError("BOTは対象にできません。")
    if err := rank_conflict(actor, member):
        raise SrvAdmError(err)
    ent = apply_points(g.id, member.id, -amount, reason, actor.id, "other")
    if not ent:
        raise SrvAdmError("そのメンバーのポイントは0です。")
    await send_log(g, make_embed("➖ ポイント減算", f"{member} (`{member.id}`) {ent['d']}pt [#{ent['id']}]\n実行者: {actor} (`{actor.id}`)\n理由: {reason}", YELLOW))
    return ent, lg.get(g.id)["points"]["balance"].get(str(member.id), 0)


async def core_points_undo(g: discord.Guild, actor, entry_id: int) -> str:
    p = lg.get(g.id)["points"]
    ent = next((e for e in reversed(p["log"]) if e["id"] == entry_id), None)
    if not ent:
        raise SrvAdmError("その履歴は見つかりません。(古い履歴は削除されます)")
    if ent.get("x") or ent["cat"] == "undo":
        raise SrvAdmError("すでに取り消し済み、または取り消しの履歴です。")
    target = g.get_member(ent["u"])
    if target and (err := rank_conflict(actor, target)):
        raise SrvAdmError(err)
    res = apply_points(g.id, ent["u"], -ent["d"], f"取消 #{entry_id}", actor.id, "undo")
    ent["x"] = True
    lg.save()
    await send_log(g, make_embed("↩️ ポイント取消", f"#{entry_id} <@{ent['u']}> {ent['d']:+d}pt\n実行者: {actor}", YELLOW))
    return f"↩️ #{entry_id} を取り消しました。" + ("" if res else "(残高が足りず、残高は変わりませんでした)")


POINT_RANGES = {"max_award": (1, 100000), "staff_daily_budget": (1, 1000000), "user_daily_cap": (1, 1000000),
                "alert_threshold": (1, 1000000), "auto_points": (0, 100), "auto_min_len": (1, 500), "auto_cooldown": (10, 86400),
                "auto_daily_cap": (1, 10000), "min_member_days": (0, 365)}


async def core_points_config(g: discord.Guild, user, vals: dict, mvp_channel=None, mvp_role=None,
                             ch_add=None, ch_remove=None) -> str:
    p = lg.get(g.id)["points"]
    changed = []
    if mvp_channel and not can_post(mvp_channel, g.me):
        raise SrvAdmError(f"BOTが #{mvp_channel.name} に送信できません。")
    if mvp_role and (pr := role_problem(_lgctx(g, user), mvp_role, True)):
        raise SrvAdmError(f"MVPロール: {pr}")
    for key, (lo, hi) in POINT_RANGES.items():
        v = vals.get(key)
        if v is None:
            continue
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            raise SrvAdmError(f"`{key}` は {lo}〜{hi} の数字で指定してください。")
        p[key] = v
        changed.append(f"`{key}` = `{v}`")
    if vals.get("mvp_auto") is not None:
        p["mvp_auto"] = bool(vals["mvp_auto"])
        changed.append(f"`mvp_auto` = `{p['mvp_auto']}`")
    if mvp_channel:
        p["mvp_channel"] = mvp_channel.id
        changed.append(f"`mvp_channel` = #{mvp_channel.name}")
    if mvp_role:
        p["mvp_role"] = mvp_role.id
        changed.append(f"`mvp_role` = {mvp_role.name}")
    if ch_add and ch_add.id not in p["auto_channels"]:
        if len(p["auto_channels"]) >= 50:
            raise SrvAdmError("自動付与のチャンネルは50個までです。")
        p["auto_channels"].append(ch_add.id)
        changed.append(f"自動付与に追加: #{ch_add.name}")
    if ch_remove and ch_remove.id in p["auto_channels"]:
        p["auto_channels"].remove(ch_remove.id)
        changed.append(f"自動付与から除外: #{ch_remove.name}")
    if not changed:
        autos = " ".join(f"#{c.name}" for c in (g.get_channel(i) for i in p["auto_channels"]) if c) or "なし"
        mch = g.get_channel(p["mvp_channel"]) if p["mvp_channel"] else None
        return (f"**現在の設定**\n付与上限 {p['max_award']}pt/回・スタッフ {p['staff_daily_budget']}pt/日・受取 {p['user_daily_cap']}pt/日\n"
                f"自動付与: {p['auto_points']}pt/回(最低{p['auto_min_len']}文字・{p['auto_cooldown']}秒間隔・上限{p['auto_daily_cap']}pt/日・参加{p['min_member_days']}日以上)\n対象: {autos}\n"
                f"MVP: {('#' + mch.name) if mch else '未設定'} / 自動発表 {'ON' if p['mvp_auto'] else 'OFF'}")
    lg.save()
    return "✅ 更新しました:\n" + "\n".join(changed)


async def core_mvp(g: discord.Guild, month: Optional[str], channel) -> str:
    first = datetime.now(JST).replace(day=1)
    ym = (month or (first - timedelta(days=1)).strftime("%Y-%m")).strip()
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", ym) or ym > first.strftime("%Y-%m"):
        raise SrvAdmError("月は `2026-09` の形式で、未来でない月を指定してください。")
    ok, msg = await announce_mvp(g, ym, channel)
    return ("✅ " if ok else "⚠️ ") + msg


# ───────────────────────── 役職(権限)管理 ─────────────────────────

class RankError(app_commands.CheckFailure):
    """役職が足りないときのエラー(メッセージをそのままユーザーに見せる)"""


def rank_of(member) -> int:
    """サーバーオーナーと Discord の管理者権限を持つ人は、常に管理者(5)として扱う(締め出し防止)"""
    if not isinstance(member, discord.Member):
        return 0
    g = member.guild
    if member.id == g.owner_id or member.guild_permissions.administrator:
        return 5
    ids = {r.id for r in member.roles}
    best = 0
    for k, rid in lg.get(g.id)["ranks"].items():
        if rid and rid in ids:
            best = max(best, int(k))
    return best


def need(gid: int, key: str) -> int:
    if key == "rank_manage":
        return 5
    try:
        return int(lg.get(gid)["perm"].get(key, PERMS[key][0]))
    except (KeyError, ValueError):
        return 5


def rank_conflict(actor, target) -> Optional[str]:
    """自分と同位以上の役職の人には、処罰やポイント減算ができない"""
    if not isinstance(actor, discord.Member) or not isinstance(target, discord.Member):
        return None
    if actor.id == actor.guild.owner_id:
        return None
    tr = rank_of(target)
    if tr > 0 and tr >= rank_of(actor):
        return f"あなたと同位以上の役職({rname(tr)})のメンバーには実行できません。"
    return None


_heavy: dict = defaultdict(deque)


def perm_check(key: str):
    async def pred(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        r, n = rank_of(interaction.user), need(interaction.guild.id, key)
        if r < n:
            raise RankError(f"❌ この操作には「{rname(n)}」以上の役職が必要です。(あなた: {rname(r)})")
        if key in HEAVY and r < 5:
            now, k = time.time(), (interaction.guild.id, interaction.user.id)
            dq = _heavy[k]
            while dq and now - dq[0] > HEAVY_WINDOW:
                dq.popleft()
            if len(dq) >= HEAVY_LIMIT:
                e = make_embed("🚨 処罰コマンドの連続実行", f"{interaction.user.mention} (`{interaction.user.id}`) が "
                                 f"{HEAVY_WINDOW // 60}分以内に {HEAVY_LIMIT}回以上 `/{key}` 系を実行しようとしたため制限しました。", RED)
                asyncio.create_task(send_log(interaction.guild, e))
                raise RankError("⏳ 短時間に処罰コマンドを実行しすぎです。しばらく待ってください。(誤操作・乗っ取り対策)")
            dq.append(now)
        return True
    return app_commands.check(pred)


# ───────────────────────── 管理ログ(永続) ─────────────────────────

SKIP_TITLES = ("🗑️ メッセージ削除", "✏️ メッセージ編集")
SKIP_FIELDS = {"内容", "編集前", "編集後"}


def record_log(gid: int, embed: discord.Embed) -> None:
    """send_log に流れた管理ログを、再起動後も見られるよう保存する(メッセージ本文は保存しない)"""
    if lg is None:
        return
    title = embed.title or ""
    if title.startswith(SKIP_TITLES):
        return
    parts = [embed.description] if embed.description else []
    parts += [f"{f.name}: {f.value}" for f in embed.fields if f.name not in SKIP_FIELDS]
    a = lg.get(gid)["audit"]
    a.append({"t": int(time.time()), "title": title[:60], "text": " | ".join(parts).replace("\n", " / ")[:400]})
    cap(a, 2000)
    lg.save()


def record_ticket_close(gid: int, info: dict, closer, reason: Optional[str]) -> None:
    if lg is None:
        return
    h = lg.get(gid)["tickets"]
    h.append({"n": info.get("number"), "owner": info.get("owner"), "subject": info.get("subject", ""),
              "claimed": info.get("claimed_by"), "created": info.get("created"), "closed": int(time.time()),
              "by": closer.id if closer else None, "why": (reason or "")[:200]})
    cap(h, 3000)
    lg.save()


# ───────────────────────── コマンド群の定義 ─────────────────────────

srvadm_group = app_commands.Group(name="manage", description="役職・ロール・履歴の管理(サーバー運営)", guild_only=True)
apply_group = app_commands.Group(name="apply", description="参加申請の設定・履歴", guild_only=True)
staff_group = app_commands.Group(name="staffapp", description="スタッフ応募の設定・履歴", guild_only=True)
points_group = app_commands.Group(name="points", description="ポイントの付与・確認・設定", guild_only=True)
region_group = app_commands.Group(name="region", description="地域(都道府県)ロールの設定", guild_only=True)


# ── 役職 ──

@srvadm_group.command(name="rank_set", description="役職に対応するDiscordロールを設定(roleを省略すると解除)")
@app_commands.describe(rank="役職", role="その役職として扱うロール")
@app_commands.choices(rank=[app_commands.Choice(name=n, value=k) for k, n in RANK_NAMES.items()])
@perm_check("rank_manage")
@lg_guard
async def lg_rank_set(interaction: discord.Interaction, rank: app_commands.Choice[int], role: Optional[discord.Role] = None):
    await eph(interaction, core_rank_set(interaction.guild, rank.value, role))


@srvadm_group.command(name="rank_show", description="役職とロールの対応・あなたの役職を表示")
@perm_check("audit_view")
async def lg_rank_show(interaction: discord.Interaction):
    g = interaction.guild
    ranks = lg.get(g.id)["ranks"]
    e = make_embed("🎖️ 役職一覧", color=BLUE)
    for k in ("5", "4", "3", "2", "1"):
        role = g.get_role(ranks[k]) if ranks[k] else None
        e.add_field(name=rname(int(k)), value=f"{role.mention} ({len(role.members)}人)" if role else "未設定")
    e.add_field(name="あなたの役職", value=rname(rank_of(interaction.user)), inline=False)
    e.set_footer(text="サーバーオーナーとDiscordの管理者権限を持つ人は、常に管理者として扱われます")
    await interaction.response.send_message(embed=e, ephemeral=True, allowed_mentions=NONE)


@srvadm_group.command(name="perm_list", description="機能ごとの必要役職を表示")
@perm_check("audit_view")
async def lg_perm_list(interaction: discord.Interaction):
    ov = lg.get(interaction.guild.id)["perm"]
    lines = [f"`{k}` {desc} → **{rname(need(interaction.guild.id, k))}以上**" + (" *(変更済み)*" if k in ov else "")
             for k, (_, desc) in PERMS.items()]
    e = make_embed("🔑 機能ごとの権限", color=BLUE)
    e.add_field(name="運用", value="\n".join(lines[:12]), inline=False)
    e.add_field(name="運用(続き)", value="\n".join(lines[12:]), inline=False)
    e.set_footer(text="変更は /manage perm_set (管理者のみ)")
    await interaction.response.send_message(embed=e, ephemeral=True)


@srvadm_group.command(name="perm_set", description="機能ごとの必要役職を変更(rankを省略すると既定に戻す)")
@app_commands.describe(key="機能", rank="必要な役職")
@app_commands.choices(rank=[app_commands.Choice(name=f"{n}以上", value=k) for k, n in RANK_NAMES.items()])
@perm_check("rank_manage")
@lg_guard
async def lg_perm_set(interaction: discord.Interaction, key: str, rank: Optional[app_commands.Choice[int]] = None):
    await eph(interaction, await core_perm_set(interaction.guild, interaction.user, key, rank.value if rank else None))


@lg_perm_set.autocomplete("key")
async def _perm_key_ac(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=f"{k} - {d}"[:100], value=k) for k, (_, d) in PERMS.items()
            if k != "rank_manage" and (current.lower() in k or current in d)][:25]


# ── 登録ロール(メンバー・情報提供者・スタッフ など) ──

async def _slot_ac(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=n, value=n) for n in lg.get(interaction.guild.id)["slots"] if current.lower() in n.lower()][:25]


@srvadm_group.command(name="role_set", description="管理するロールに名前を付けて登録(例: メンバー / 情報提供者)")
@app_commands.describe(name="登録名(20文字まで)", role="Discordのロール")
@perm_check("rank_manage")
@lg_guard
async def lg_role_set(interaction: discord.Interaction, name: app_commands.Range[str, 1, 20], role: discord.Role):
    await eph(interaction, core_role_set(interaction.guild, interaction.user, name, role))


@srvadm_group.command(name="role_unset", description="登録したロールを登録から外す(Discord上のロールは消えません)")
@perm_check("rank_manage")
@lg_guard
async def lg_role_unset(interaction: discord.Interaction, name: str):
    await eph(interaction, core_role_unset(interaction.guild, name))


@srvadm_group.command(name="role_list", description="登録ロールと期限つき付与の一覧")
@perm_check("audit_view")
async def lg_role_list(interaction: discord.Interaction):
    g = interaction.guild
    c = lg.get(g.id)
    lines = [f"・**{n}** = " + (g.get_role(r).mention if g.get_role(r) else "(削除済み)") for n, r in c["slots"].items()]
    e = make_embed("🏷️ 登録ロール", "\n".join(lines) or "未登録です。`/manage role_set` で登録してください。", BLUE)
    if c["temp_roles"]:
        now = time.time()
        e.add_field(name=f"期限つき付与 ({len(c['temp_roles'])}件)", value="\n".join(
            f"<@{t['u']}> <@&{t['r']}> <t:{int(t['exp'])}:R>" for t in sorted(c["temp_roles"], key=lambda t: t["exp"])[:15]), inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True, allowed_mentions=NONE)


def role_grant_error(g: discord.Guild, u, role: discord.Role) -> Optional[str]:
    if role.is_default() or role.managed:
        return "そのロールは操作できません。"
    if not bot_can_grant(g, role):
        return "BOTがそのロールを操作できません。(「ロールの管理」権限・ロールの順位を確認してください)"
    if u.id != g.owner_id and role >= u.top_role:
        return "あなたと同位以上のロールは操作できません。"
    if dangerous(role):
        return "危険な権限を含むロールは、この機能では操作できません。"
    ur = rank_of(u)
    for k, rid in lg.get(g.id)["ranks"].items():
        if rid == role.id and int(k) >= ur and u.id != g.owner_id:
            return "自分と同位以上の役職ロールは、付与も剥奪もできません。"
    return None


@srvadm_group.command(name="role_grant", description="登録ロールをメンバーに付与します(期限も指定できます)")
@app_commands.describe(member="対象メンバー", name="登録名", days="この日数が過ぎたら自動で外す(省略=外さない)")
@perm_check("role_grant")
@lg_guard
async def lg_role_grant(interaction: discord.Interaction, member: discord.Member, name: str,
                        days: Optional[app_commands.Range[int, 1, 365]] = None):
    await interaction.response.defer(ephemeral=True)
    msg = await core_role_grant(interaction.guild, interaction.user, member, name, days)
    await interaction.followup.send(msg, ephemeral=True, allowed_mentions=NONE)


@srvadm_group.command(name="role_revoke", description="登録ロールをメンバーから外します")
@perm_check("role_grant")
@lg_guard
async def lg_role_revoke(interaction: discord.Interaction, member: discord.Member, name: str):
    await interaction.response.defer(ephemeral=True)
    msg = await core_role_revoke(interaction.guild, interaction.user, member, name)
    await interaction.followup.send(msg, ephemeral=True, allowed_mentions=NONE)


lg_role_unset.autocomplete("name")(_slot_ac)
lg_role_grant.autocomplete("name")(_slot_ac)
lg_role_revoke.autocomplete("name")(_slot_ac)


# ── 履歴の閲覧 ──

def _lines_embed(title: str, lines: list, color: int = BLUE) -> discord.Embed:
    out, size = [], 0
    for ln in lines:
        if size + len(ln) + 1 > 3900:
            out.append("…(以降省略)")
            break
        out.append(ln)
        size += len(ln) + 1
    return make_embed(title, "\n".join(out) or "記録はありません。", color)


@srvadm_group.command(name="role_history", description="ロール変更の履歴を表示します")
@app_commands.describe(member="このメンバーのみ", count="表示件数(1〜30)")
@perm_check("audit_view")
async def lg_role_history(interaction: discord.Interaction, member: Optional[discord.User] = None,
                          count: app_commands.Range[int, 1, 30] = 15):
    h = [x for x in lg.get(interaction.guild.id)["role_hist"] if not member or x["u"] == member.id]
    lines = []
    for x in reversed(h[-count:]):
        ch = " ".join([f"➕<@&{r}>" for r in x["add"]] + [f"➖<@&{r}>" for r in x["rem"]])
        by = f"<@{x['by']}>" if x.get("by") else "不明"
        lines.append(f"<t:{x['t']}:f> <@{x['u']}> {ch}\n　実行: {by}" + (f" / {x['why'][:60]}" if x.get("why") else ""))
    await interaction.response.send_message(embed=_lines_embed("🏷️ ロール変更履歴", lines), ephemeral=True, allowed_mentions=NONE)


@srvadm_group.command(name="ticket_history", description="チケットの対応履歴を表示します")
@app_commands.describe(member="このメンバーが作成したチケットのみ", count="表示件数(1〜30)")
@perm_check("audit_view")
async def lg_ticket_history(interaction: discord.Interaction, member: Optional[discord.User] = None,
                            count: app_commands.Range[int, 1, 30] = 15):
    h = [x for x in lg.get(interaction.guild.id)["tickets"] if not member or x["owner"] == member.id]
    lines = []
    for x in reversed(h[-count:]):
        claim = f" 担当<@{x['claimed']}>" if x.get("claimed") else ""
        by = f"<@{x['by']}>" if x.get("by") else "自動"
        lines.append(f"**#{(x.get('n') or 0):04d}** <@{x['owner']}>{claim} / {x.get('subject', '')[:40]}\n　<t:{x['closed']}:f> クローズ {by}"
                     + (f" / {x['why'][:50]}" if x.get("why") else ""))
    await interaction.response.send_message(embed=_lines_embed("🎫 チケット対応履歴", lines), ephemeral=True, allowed_mentions=NONE)


@srvadm_group.command(name="log", description="保存されている管理ログ(処罰・認証・参加退出など)を表示します")
@app_commands.describe(count="表示件数(1〜30)", keyword="この文字を含むものだけ(例: Ban / Timeout / 参加)", export="全件(最大2000件)をテキストで出力")
@perm_check("audit_view")
async def lg_log(interaction: discord.Interaction, count: app_commands.Range[int, 1, 30] = 15,
                 keyword: Optional[str] = None, export: bool = False):
    h = lg.get(interaction.guild.id)["audit"]
    if keyword:
        k = keyword.lower()
        h = [x for x in h if k in x["title"].lower() or k in x["text"].lower()]
    if export:
        txt = "\n".join(f"[{jst(x['t'], '%Y-%m-%d %H:%M:%S')} JST] {x['title']} {x['text']}" for x in h) or "(記録なし)"
        return await interaction.response.send_message(file=discord.File(io.BytesIO(txt.encode("utf-8")), filename="admin_log.txt"),
                                                       ephemeral=True)
    lines = [f"<t:{x['t']}:f> **{x['title']}** {x['text'][:160]}" for x in reversed(h[-count:])]
    await interaction.response.send_message(embed=_lines_embed("📜 管理ログ", lines, GRAY), ephemeral=True, allowed_mentions=NONE)


# ───────────────────────── 申請・応募(共通) ─────────────────────────

def _find_pending(sec: dict, uid: int) -> bool:
    return any(a["u"] == uid and a["st"] in ("pending", "processing") for a in sec["apps"].values())


def _cooldown_left(sec: dict, uid: int) -> float:
    last = max((a.get("rt") or 0 for a in sec["apps"].values() if a["u"] == uid and a["st"] == "rejected"), default=0)
    return last + sec["cooldown_hours"] * 3600 - time.time() if last else 0


def _trim_apps(sec: dict) -> None:
    apps = sec["apps"]
    if len(apps) > 5000:
        for k in list(apps)[:len(apps) - 5000]:
            if apps[k]["st"] not in ("pending", "processing"):
                apps.pop(k, None)


def review_need(gid: int, kind: str, rec: dict) -> int:
    base = need(gid, "apply_review" if kind == "j" else "staff_review")
    if kind == "s":
        pos = lg.get(gid)["staff"]["positions"].get(rec.get("pos") or "")
        base = max(base, min(5, (pos["rank"] if pos else 1) + 1))
    return base


def review_embed(g: discord.Guild, kind: str, rec: dict) -> discord.Embed:
    st = rec["st"]
    color = {"pending": BLUE, "processing": YELLOW, "approved": GREEN, "rejected": RED}.get(st, GRAY)
    e = make_embed(f"📝 {LABEL[kind]} #{rec['id']:04d}", color=color)
    e.add_field(name="申請者", value=f"<@{rec['u']}> (`{rec['u']}`)")
    if kind == "s":
        pos = lg.get(g.id)["staff"]["positions"].get(rec.get("pos") or "")
        e.add_field(name="志望役職", value=pos["label"] if pos else str(rec.get("pos")))
    mem = g.get_member(rec["u"])
    if mem:
        e.add_field(name="アカウント作成", value=discord.utils.format_dt(mem.created_at, "R"))
        if mem.joined_at:
            e.add_field(name="サーバー参加", value=discord.utils.format_dt(mem.joined_at, "R"))
    for q, a in rec["ans"]:
        e.add_field(name=q[:250], value=(a or "(未入力)")[:700], inline=False)
    if st == "approved":
        s = f"✅ 承認 by <@{rec['by']}> <t:{rec['rt']}:R>"
    elif st == "rejected":
        s = f"❌ 却下 by <@{rec['by']}> <t:{rec['rt']}:R>\n理由: {rec.get('why') or 'なし'}"
    elif st == "processing":
        s = "⌛ 処理中…"
    else:
        s = f"⏳ 審査待ち(審査できる役職: {rname(review_need(g.id, kind, rec))}以上)"
    e.add_field(name="状態", value=s, inline=False)
    return e


class ReviewButton(discord.ui.DynamicItem[discord.ui.Button],
                   template=r"azq:lg:rv:(?P<kind>[js]):(?P<act>ok|ng):(?P<id>[0-9]+)"):
    def __init__(self, kind: str, act: str, aid: int):
        super().__init__(discord.ui.Button(
            label="承認" if act == "ok" else "却下", emoji="✅" if act == "ok" else "❌",
            style=discord.ButtonStyle.success if act == "ok" else discord.ButtonStyle.danger,
            custom_id=f"azq:lg:rv:{kind}:{act}:{aid}"))
        self.kind, self.act, self.aid = kind, act, aid

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match, /):
        return cls(match["kind"], match["act"], int(match["id"]))

    async def callback(self, interaction: discord.Interaction):
        await review_click(interaction, self.kind, self.act, self.aid)


def review_view(kind: str, aid: int) -> discord.ui.View:
    v = discord.ui.View(timeout=None)
    v.add_item(ReviewButton(kind, "ok", aid))
    v.add_item(ReviewButton(kind, "ng", aid))
    return v


def review_perm_error(g: discord.Guild, kind: str, rec: dict, m) -> Optional[str]:
    n = review_need(g.id, kind, rec)
    if rank_of(m) < n:
        return f"この審査には「{rname(n)}」以上の役職が必要です。(あなた: {rname(rank_of(m))})"
    if rec["u"] == m.id:
        return "自分自身の申請は審査できません。"
    return None


async def review_click(interaction: discord.Interaction, kind: str, act: str, aid: int) -> None:
    g, m = interaction.guild, interaction.user
    if g is None or not isinstance(m, discord.Member):
        return await eph(interaction, "❌ サーバー内で使ってください。")
    rec = lg.get(g.id)[SEC[kind]]["apps"].get(str(aid))
    if not rec:
        return await eph(interaction, "❌ 申請の記録が見つかりません。")
    if rec["st"] != "pending":
        return await eph(interaction, "⚠️ この申請はすでに処理されています。")
    if err := review_perm_error(g, kind, rec, m):
        return await eph(interaction, f"❌ {err}")
    if act == "ng":
        return await interaction.response.send_modal(RejectModal(kind, aid))
    await finish_app(interaction, kind, aid, True, "")


class RejectModal(discord.ui.Modal, title="却下の理由"):
    def __init__(self, kind: str, aid: int):
        super().__init__(timeout=600)
        self.kind, self.aid = kind, aid
        self.reason = discord.ui.TextInput(label="理由(申請者にDMで伝わります・空でも可)", style=discord.TextStyle.paragraph,
                                           required=False, max_length=300)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await finish_app(interaction, self.kind, self.aid, False, self.reason.value.strip())

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.exception("却下モーダルでエラー", exc_info=error)
        await eph(interaction, "⚠️ エラーが発生しました。もう一度お試しください。")


def roles_for(g: discord.Guild, kind: str, rec: dict) -> tuple:
    """承認時に付与するロールの一覧 (roles, エラー文)"""
    c = lg.get(g.id)
    if kind == "j":
        r = g.get_role(c["apply"]["role"]) if c["apply"]["role"] else None
        return ([r], None) if r else ([], "承認時に付与するロールが見つかりません。`/apply setup` で設定してください。")
    pos = c["staff"]["positions"].get(rec.get("pos") or "")
    if not pos:
        return [], "その役職は存在しません。"
    roles = []
    for rid in (pos["role"], c["ranks"].get(str(pos["rank"]))):
        r = g.get_role(rid) if rid else None
        if r and r not in roles:
            roles.append(r)
    return (roles, None) if roles else ([], "この役職に付与するロールが未設定です。`/staffapp position` か `/manage rank_set` で設定してください。")


async def process_app(g: discord.Guild, m: discord.Member, kind: str, aid: int, approve: bool, reason: str) -> str:
    """申請・応募を承認/却下する(ボタンとWebの共通処理)。失敗したら SrvAdmError"""
    sec = lg.get(g.id)[SEC[kind]]
    rec = sec["apps"].get(str(aid))
    if not rec:
        raise SrvAdmError("申請の記録が見つかりません。")
    if rec["st"] != "pending":
        raise SrvAdmError("この申請はすでに処理されています。")
    if err := review_perm_error(g, kind, rec, m):
        raise SrvAdmError(err)
    member = g.get_member(rec["u"])
    roles: list = []
    if approve:
        if member is None:
            raise SrvAdmError("申請者がサーバーにいません。却下して整理してください。")
        roles, err = roles_for(g, kind, rec)
        if err:
            raise SrvAdmError(err)
        bad = [r.name for r in roles if not bot_can_grant(g, r)]
        if bad:
            raise SrvAdmError("BOTが次のロールを付与できません(ロール順位・「ロールの管理」権限を確認): " + ", ".join(bad))
    rec["st"] = "processing"
    note = ""
    if approve:
        try:
            await member.add_roles(*roles, reason=f"AZQ BOT {LABEL[kind]}承認 #{aid} by {m}")
        except discord.HTTPException:
            rec["st"] = "pending"
            log.warning("申請承認のロール付与に失敗 guild=%s app=%s", g.id, aid, exc_info=True)
            raise SrvAdmError("ロールの付与に失敗しました。BOTの権限を確認してください。")
        if kind == "j":
            try:
                for q, a in rec["ans"]:
                    pref = match_pref(a) if "都道府県" in q else None
                    if pref and await assign_region(g, member, pref):
                        note = f"\n📍 地域ロール({pref})も付与しました。"
                        break
            except Exception:
                log.exception("地域ロールの自動付与で想定外のエラー guild=%s app=%s", g.id, aid)
    rec.update(st="approved" if approve else "rejected", by=m.id, rt=int(time.time()), why=reason)
    lg.save()
    ch = g.get_channel(rec.get("ch") or 0)
    if ch and rec.get("msg"):
        try:
            await ch.get_partial_message(rec["msg"]).edit(embed=review_embed(g, kind, rec), view=None)
        except discord.HTTPException:
            pass
    pos = lg.get(g.id)["staff"]["positions"].get(rec.get("pos") or "") if kind == "s" else None
    what = f"{LABEL[kind]}" + (f"({pos['label']})" if pos else "")
    if member:
        if approve:
            await try_dm(member, f"🎉 **{g.name}** への{what}が **承認** されました。\n付与されたロール: " + " / ".join(r.name for r in roles))
        else:
            await try_dm(member, f"**{g.name}** への{what}は、残念ながら **却下** となりました。\n理由: {reason or '特になし'}\n"
                         + (f"{sec['cooldown_hours']}時間後に再度申請できます。" if sec["cooldown_hours"] else ""))
    await send_log(g, make_embed(f"{'✅' if approve else '❌'} {what} {'承認' if approve else '却下'} #{aid:04d}",
                                 f"申請者: <@{rec['u']}> (`{rec['u']}`)\n審査: {m} (`{m.id}`)"
                                 + (f"\n付与: {' / '.join(r.name for r in roles)}" if approve else f"\n理由: {reason or 'なし'}"),
                                 GREEN if approve else RED))
    return f"{'✅ 承認' if approve else '❌ 却下'}しました。{note}"


async def finish_app(interaction: discord.Interaction, kind: str, aid: int, approve: bool, reason: str) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    try:
        msg = await process_app(interaction.guild, interaction.user, kind, aid, approve, reason)
    except SrvAdmError as e:
        return await interaction.followup.send(f"❌ {e}", ephemeral=True)
    await interaction.followup.send(msg, ephemeral=True)


class ApplyModal(discord.ui.Modal):
    def __init__(self, kind: str, questions: list, pos: Optional[str] = None, title: str = "参加申請"):
        super().__init__(title=title[:45], timeout=900)
        self.kind, self.pos, self.questions, self.inputs = kind, pos, questions[:5], []
        for q in self.questions:
            short = "都道府県" in q
            ti = discord.ui.TextInput(label=q[:45], style=discord.TextStyle.short if short else discord.TextStyle.paragraph,
                                      max_length=20 if short else 500, required=True)
            self.add_item(ti)
            self.inputs.append(ti)

    async def on_submit(self, interaction: discord.Interaction):
        await submit_app(interaction, self.kind, self.pos, [(q, i.value.strip()) for q, i in zip(self.questions, self.inputs)])

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.exception("申請モーダルでエラー", exc_info=error)
        await eph(interaction, "⚠️ エラーが発生しました。もう一度お試しください。")


async def submit_app(interaction: discord.Interaction, kind: str, pos: Optional[str], answers: list) -> None:
    await interaction.response.defer(ephemeral=True)
    g, m = interaction.guild, interaction.user
    sec = lg.get(g.id)[SEC[kind]]
    rch = g.get_channel(sec["review_channel"]) if sec["review_channel"] else None
    if not sec["enabled"] or rch is None:
        return await interaction.followup.send("⚠️ 現在は受け付けていません。", ephemeral=True)
    if _find_pending(sec, m.id):
        return await interaction.followup.send("❌ すでに審査待ちの申請があります。結果をお待ちください。", ephemeral=True)
    sec["counter"] += 1
    aid = sec["counter"]
    rec = {"id": aid, "u": m.id, "ans": answers, "st": "pending", "t": int(time.time()), "by": None, "rt": None,
           "why": "", "msg": None, "ch": rch.id, "pos": pos}
    sec["apps"][str(aid)] = rec
    try:
        msg = await rch.send(embed=review_embed(g, kind, rec), view=review_view(kind, aid), allowed_mentions=NONE)
    except discord.HTTPException:
        sec["apps"].pop(str(aid), None)
        log.warning("審査チャンネルへの送信に失敗 guild=%s", g.id, exc_info=True)
        return await interaction.followup.send("⚠️ 申請を送信できませんでした。管理者に連絡してください。", ephemeral=True)
    rec["msg"] = msg.id
    _trim_apps(sec)
    lg.save()
    await send_log(g, make_embed(f"📝 {LABEL[kind]}を受付 #{aid:04d}", f"{m.mention} (`{m.id}`)", BLUE))
    await interaction.followup.send("✅ 送信しました。結果はDMでお知らせします。(DMを受け取れる設定にしてください)", ephemeral=True)


def _verify_pending(g: discord.Guild, uid: int) -> bool:
    cfg = store.get(g.id)
    return bool(cfg["verify"]["enabled"] and cfg["verify"]["role"] and str(uid) in cfg["verify"]["pending"])


def _gate(interaction: discord.Interaction, kind: str) -> Optional[str]:
    """申請ボタンを押せる状態か。押せないなら理由を返す"""
    g, m = interaction.guild, interaction.user
    if g is None or not isinstance(m, discord.Member):
        return "❌ サーバー内で使ってください。"
    sec = lg.get(g.id)[SEC[kind]]
    if not sec["enabled"] or not sec["review_channel"] or not g.get_channel(sec["review_channel"]):
        return "⚠️ 現在は受け付けていません。"
    if _verify_pending(g, m.id):
        return "🔐 先にメンバー認証を完了してください。"
    if _find_pending(sec, m.id):
        return "❌ すでに審査待ちの申請があります。結果をお待ちください。"
    left = _cooldown_left(sec, m.id)
    if left > 0:
        return f"⏳ 却下後の再申請は <t:{int(time.time() + left)}:R> 以降にできます。"
    return None


class ApplyPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="参加を申請する", emoji="📝", style=discord.ButtonStyle.primary, custom_id="azq:lg:apply")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if err := _gate(interaction, "j"):
            return await eph(interaction, err)
        sec = lg.get(interaction.guild.id)["apply"]
        role = interaction.guild.get_role(sec["role"]) if sec["role"] else None
        if role and role in interaction.user.roles:
            return await eph(interaction, "✅ すでに参加が承認されています。")
        await interaction.response.send_modal(ApplyModal("j", sec["questions"], title="参加申請"))


def staff_panel_view(g: Optional[discord.Guild] = None) -> discord.ui.View:
    pos = lg.get(g.id)["staff"]["positions"] if g else {}
    opts = [discord.SelectOption(label=p["label"][:100], value=k, description=f"審査: {rname(min(5, max(3, p['rank'] + 1)))}以上"[:100])
            for k, p in pos.items() if p["enabled"]]
    return StaffPanelView(opts or [discord.SelectOption(label="募集中の役職はありません", value="_none")])


class StaffPanelView(discord.ui.View):
    def __init__(self, options: Optional[list] = None):
        super().__init__(timeout=None)
        sel = discord.ui.Select(custom_id="azq:lg:staff", placeholder="応募する役職を選んでください",
                                options=options or [discord.SelectOption(label="役職", value="_none")])
        sel.callback = self._cb
        self.add_item(sel)

    async def _cb(self, interaction: discord.Interaction):
        await staff_click(interaction, interaction.data["values"][0])


async def staff_click(interaction: discord.Interaction, key: str) -> None:
    if err := _gate(interaction, "s"):
        return await eph(interaction, err)
    g, m = interaction.guild, interaction.user
    c = lg.get(g.id)
    pos = c["staff"]["positions"].get(key)
    if not pos or not pos["enabled"]:
        return await eph(interaction, "⚠️ その役職は現在募集していません。")
    held = {pos["role"], c["ranks"].get(str(pos["rank"])) if pos["rank"] >= 2 else None} - {None}
    if held & {r.id for r in m.roles}:
        return await eph(interaction, "✅ すでにその役職(または同等のロール)を持っています。")
    if rank_of(m) > pos["rank"]:
        return await eph(interaction, "✅ すでにそれ以上の役職です。")
    await interaction.response.send_modal(ApplyModal("s", c["staff"]["questions"], key, title=f"応募: {pos['label']}"))


# ── パネル設置 ──

async def lg_delete_panel(g: discord.Guild, kind: str) -> None:
    sec = lg.get(g.id)[SEC[kind]] if kind in SEC else lg.get(g.id)["region"]
    ch = g.get_channel(sec["panel_channel"]) if sec["panel_channel"] else None
    if ch and sec["panel_message"]:
        try:
            await ch.get_partial_message(sec["panel_message"]).delete()
        except discord.HTTPException:
            pass
    sec["panel_channel"] = sec["panel_message"] = None


async def lg_post_panel(g: discord.Guild, kind: str, channel: discord.TextChannel) -> None:
    await lg_delete_panel(g, kind)
    sec = lg.get(g.id)[SEC[kind]]
    e = make_embed(sec["title"], sec["text"], BLUE if kind == "j" else GREEN)
    msg = await channel.send(embed=e, view=ApplyPanelView() if kind == "j" else staff_panel_view(g))
    sec["panel_channel"], sec["panel_message"] = channel.id, msg.id
    lg.save()


async def refresh_staff_panel(g: discord.Guild) -> None:
    sec = lg.get(g.id)["staff"]
    ch = g.get_channel(sec["panel_channel"]) if sec["panel_channel"] else None
    if ch and sec["panel_message"]:
        try:
            await ch.get_partial_message(sec["panel_message"]).edit(view=staff_panel_view(g))
        except discord.HTTPException:
            pass


def _setup_common(g: discord.Guild, panel: discord.TextChannel, review: discord.TextChannel) -> Optional[str]:
    me = g.me
    if not can_post(panel, me):
        return f"BOTが #{panel.name} に送信できません。"
    if not can_post(review, me):
        return f"BOTが #{review.name} に送信できません。"
    return None


def _privacy_note(g: discord.Guild, review: discord.TextChannel) -> str:
    return (f"\n⚠️ {review.mention} は @everyone から見えます。申請内容が全員に見えてしまうため、スタッフ専用にしてください。"
            if review.permissions_for(g.default_role).view_channel else "")


@apply_group.command(name="setup", description="参加申請パネルを設置して有効化します")
@app_commands.describe(panel_channel="申請ボタンを置くチャンネル", review_channel="申請が届く審査チャンネル(スタッフ専用に)",
                       role="承認時に付与するロール", cooldown_hours="却下後に再申請できるまでの時間(0〜720)")
@perm_check("rank_manage")
@lg_guard
async def ap_setup(interaction: discord.Interaction, panel_channel: discord.TextChannel, review_channel: discord.TextChannel,
                   role: discord.Role, cooldown_hours: Optional[app_commands.Range[int, 0, 720]] = None):
    await interaction.response.defer(ephemeral=True)
    msg = await core_apply_setup(interaction.guild, interaction.user, panel_channel, review_channel, role, cooldown_hours)
    await interaction.followup.send(msg, ephemeral=True, allowed_mentions=NONE)


@apply_group.command(name="disable", description="参加申請を無効化し、パネルを削除します")
@perm_check("rank_manage")
@lg_guard
async def ap_disable(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(await core_apply_disable(interaction.guild), ephemeral=True)


class QuestionsModal(discord.ui.Modal, title="質問の編集"):
    def __init__(self, kind: str, current: list):
        super().__init__(timeout=600)
        self.kind = kind
        self.t = discord.ui.TextInput(label="質問(1行に1つ・最大5つ・各45文字まで)", style=discord.TextStyle.paragraph,
                                      default="\n".join(current)[:1000], max_length=1000)
        self.add_item(self.t)

    async def on_submit(self, interaction: discord.Interaction):
        qs = [x.strip() for x in self.t.value.splitlines() if x.strip()]
        if not 1 <= len(qs) <= 5 or any(len(x) > 45 for x in qs):
            return await interaction.response.send_message("❌ 質問は1〜5個、各45文字以内にしてください。", ephemeral=True)
        lg.get(interaction.guild.id)[SEC[self.kind]]["questions"] = qs
        lg.save()
        await interaction.response.send_message("✅ 質問を更新しました。(「都道府県」を含む質問の回答は、地域ロールの自動付与に使われます)", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.exception("質問編集でエラー", exc_info=error)
        await eph(interaction, "⚠️ エラーが発生しました。")


@apply_group.command(name="questions", description="申請フォームの質問を編集します")
@perm_check("rank_manage")
async def ap_questions(interaction: discord.Interaction):
    await interaction.response.send_modal(QuestionsModal("j", lg.get(interaction.guild.id)["apply"]["questions"]))


def history_embed(g: discord.Guild, kind: str, member, status: Optional[str], count: int) -> discord.Embed:
    apps = [a for a in lg.get(g.id)[SEC[kind]]["apps"].values()
            if (not member or a["u"] == member.id) and (not status or a["st"] == status)]
    icon = {"pending": "⏳", "processing": "⌛", "approved": "✅", "rejected": "❌"}
    pos = lg.get(g.id)["staff"]["positions"]
    lines = []
    for a in reversed(apps[-count:]):
        extra = f" [{pos.get(a.get('pos'), {}).get('label', a.get('pos'))}]" if kind == "s" else ""
        who = f" by <@{a['by']}>" if a.get("by") else ""
        why = f" 理由: {a['why'][:40]}" if a.get("why") else ""
        lines.append(f"{icon.get(a['st'], '・')} **#{a['id']:04d}** <@{a['u']}>{extra}{who} <t:{a['t']}:d>{why}")
    return _lines_embed(f"📚 {LABEL[kind]}の履歴", lines)


STATUS_CHOICES = [app_commands.Choice(name=n, value=v) for v, n in (("pending", "審査待ち"), ("approved", "承認"), ("rejected", "却下"))]


@apply_group.command(name="history", description="参加申請の履歴を表示します")
@app_commands.describe(member="このメンバーのみ", status="状態で絞り込み", count="表示件数(1〜30)")
@app_commands.choices(status=STATUS_CHOICES)
@perm_check("audit_view")
async def ap_history(interaction: discord.Interaction, member: Optional[discord.User] = None,
                     status: Optional[app_commands.Choice[str]] = None, count: app_commands.Range[int, 1, 30] = 15):
    await interaction.response.send_message(embed=history_embed(interaction.guild, "j", member, status.value if status else None, count),
                                            ephemeral=True, allowed_mentions=NONE)


@staff_group.command(name="setup", description="スタッフ応募パネルを設置して有効化します")
@app_commands.describe(panel_channel="応募メニューを置くチャンネル", review_channel="応募が届く審査チャンネル(幹部以上専用に)",
                       cooldown_hours="不合格後に再応募できるまでの時間(0〜720)")
@perm_check("rank_manage")
@lg_guard
async def sf_setup(interaction: discord.Interaction, panel_channel: discord.TextChannel, review_channel: discord.TextChannel,
                   cooldown_hours: Optional[app_commands.Range[int, 0, 720]] = None):
    await interaction.response.defer(ephemeral=True)
    msg = await core_staff_setup(interaction.guild, panel_channel, review_channel, cooldown_hours)
    await interaction.followup.send(msg, ephemeral=True, allowed_mentions=NONE)


@staff_group.command(name="position", description="応募できる役職のロール・表示名・受付を設定します")
@app_commands.describe(key="役職", role="合格時に付与するロール", label="表示名(40文字まで)", enabled="この役職の募集を受け付ける",
                       clear_role="付与ロールの設定を解除する")
@perm_check("rank_manage")
@lg_guard
async def sf_position(interaction: discord.Interaction, key: str, role: Optional[discord.Role] = None,
                      label: Optional[app_commands.Range[str, 1, 40]] = None, enabled: Optional[bool] = None, clear_role: bool = False):
    await eph(interaction, await core_staff_position(interaction.guild, interaction.user, key, role, label, enabled, clear_role))


@sf_position.autocomplete("key")
async def _pos_ac(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=f"{p['label']} ({k})"[:100], value=k)
            for k, p in lg.get(interaction.guild.id)["staff"]["positions"].items() if current.lower() in k or current in p["label"]][:25]


@staff_group.command(name="questions", description="応募フォームの質問を編集します")
@perm_check("rank_manage")
async def sf_questions(interaction: discord.Interaction):
    await interaction.response.send_modal(QuestionsModal("s", lg.get(interaction.guild.id)["staff"]["questions"]))


@staff_group.command(name="history", description="スタッフ応募の履歴を表示します")
@app_commands.describe(member="このメンバーのみ", status="状態で絞り込み", count="表示件数(1〜30)")
@app_commands.choices(status=STATUS_CHOICES)
@perm_check("audit_view")
async def sf_history(interaction: discord.Interaction, member: Optional[discord.User] = None,
                     status: Optional[app_commands.Choice[str]] = None, count: app_commands.Range[int, 1, 30] = 15):
    await interaction.response.send_message(embed=history_embed(interaction.guild, "s", member, status.value if status else None, count),
                                            ephemeral=True, allowed_mentions=NONE)


@staff_group.command(name="disable", description="スタッフ応募を無効化し、パネルを削除します")
@perm_check("rank_manage")
@lg_guard
async def sf_disable(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(await core_staff_disable(interaction.guild), ephemeral=True)


# ───────────────────────── 地域(都道府県)ロール ─────────────────────────

async def assign_region(g: discord.Guild, member: discord.Member, pref: str) -> bool:
    reg = lg.get(g.id)["region"]
    role = g.get_role(reg["pref"].get(pref) or 0)
    rrole = g.get_role(reg["region"].get(PREF_TO_REGION.get(pref, "")) or 0)
    want = [r for r in (role, rrole) if r and bot_can_grant(g, r)]
    if not want:
        return False
    mapped = {g.get_role(i) for i in list(reg["pref"].values()) + list(reg["region"].values())} - {None}
    remove = [r for r in member.roles if r in mapped and r not in want and bot_can_grant(g, r)]
    add = [r for r in want if r not in member.roles]
    try:
        if remove:
            await member.remove_roles(*remove, reason="AZQ BOT 地域ロールの変更")
        if add:
            await member.add_roles(*add, reason="AZQ BOT 地域ロール")
    except discord.HTTPException:
        log.warning("地域ロールの付与に失敗 guild=%s", g.id, exc_info=True)
        return False
    return True


_region_last: dict = {}


async def region_pick(interaction: discord.Interaction, value: str) -> None:
    g, m = interaction.guild, interaction.user
    if g is None or not isinstance(m, discord.Member):
        return
    await interaction.response.defer()
    now = time.time()
    if now - _region_last.get((g.id, m.id), 0) < 5:
        return await interaction.edit_original_response(content="⏳ 少し待ってからもう一度選んでください。", view=None)
    _region_last[(g.id, m.id)] = now
    reg = lg.get(g.id)["region"]
    if value == "__clear":
        mapped = {g.get_role(i) for i in list(reg["pref"].values()) + list(reg["region"].values())} - {None}
        rm = [r for r in m.roles if r in mapped and bot_can_grant(g, r)]
        try:
            if rm:
                await m.remove_roles(*rm, reason="AZQ BOT 地域ロールの解除")
        except discord.HTTPException:
            return await interaction.edit_original_response(content="⚠️ 解除に失敗しました。", view=None)
        return await interaction.edit_original_response(content="✅ 地域ロールを外しました。", view=None)
    ok = value in PREF_TO_REGION and await assign_region(g, m, value)
    await interaction.edit_original_response(
        content=f"✅ **{value}** に設定しました。" if ok else "⚠️ ロールを付与できませんでした。管理者に連絡してください。", view=None)


class PrefPickView(discord.ui.View):
    def __init__(self, region: str):
        super().__init__(timeout=120)
        opts = [discord.SelectOption(label=p, value=p) for p in REGIONS[region]]
        opts.append(discord.SelectOption(label="地域ロールを外す", value="__clear", emoji="🧹"))
        sel = discord.ui.Select(placeholder="都道府県を選んでください", options=opts)
        sel.callback = lambda i: region_pick(i, i.data["values"][0])
        self.add_item(sel)


class RegionPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        sel = discord.ui.Select(custom_id="azq:lg:region", placeholder="お住まいの地方を選んでください",
                                options=[discord.SelectOption(label=n, value=n) for n in REGIONS])
        sel.callback = self._cb
        self.add_item(sel)

    async def _cb(self, interaction: discord.Interaction):
        name = interaction.data["values"][0]
        if name not in REGIONS:
            return
        await interaction.response.send_message(f"**{name}** の都道府県を選んでください。", view=PrefPickView(name), ephemeral=True)


@region_group.command(name="create", description="地方・都道府県のロールを作成(同名の既存ロールは再利用)して登録します")
@app_commands.describe(include_prefectures="Falseにすると地方(8個)だけ作成")
@perm_check("rank_manage")
@lg_guard
async def rg_create(interaction: discord.Interaction, include_prefectures: bool = True):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(await core_region_create(interaction.guild, include_prefectures), ephemeral=True)


@region_group.command(name="panel", description="地域ロールの選択パネルを設置します")
@perm_check("rank_manage")
@lg_guard
async def rg_panel(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(await core_region_panel(interaction.guild, channel), ephemeral=True)


@region_group.command(name="set_role", description="既存のロールを地方・都道府県として登録します")
@app_commands.describe(name="地方または都道府県の名前", role="登録するロール")
@perm_check("rank_manage")
@lg_guard
async def rg_set_role(interaction: discord.Interaction, name: str, role: discord.Role):
    await eph(interaction, core_region_set_role(interaction.guild, interaction.user, name, role))


@rg_set_role.autocomplete("name")
async def _region_ac(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=n, value=n) for n in list(REGIONS) + list(PREF_TO_REGION) if current in n][:25]


@region_group.command(name="status", description="地域ロールの登録状況を表示します")
@perm_check("audit_view")
async def rg_status(interaction: discord.Interaction):
    reg = lg.get(interaction.guild.id)["region"]
    miss = [p for p in PREF_TO_REGION if p not in reg["pref"]]
    await interaction.response.send_message(
        f"地方ロール {len(reg['region'])}/8 / 都道府県ロール {len(reg['pref'])}/47\nパネル: "
        + (f"<#{reg['panel_channel']}>" if reg["panel_channel"] else "未設置")
        + (f"\n未登録: {', '.join(miss[:47])}" if miss and reg["pref"] else ""), ephemeral=True)


# ───────────────────────── ポイント・ランキング ─────────────────────────

def _today() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


def _used(p: dict) -> dict:
    d = _today()
    if p["used"].get("date") != d:
        p["used"] = {"date": d, "give": {}, "get": {}, "auto": {}}
    return p["used"]


def apply_points(gid: int, uid: int, delta: int, why: str, by: int, cat: str) -> Optional[dict]:
    """残高を増減して履歴に残す。残高は0未満にならない。実際に変わった量が0なら None"""
    p = lg.get(gid)["points"]
    k = str(uid)
    cur = p["balance"].get(k, 0)
    new = max(0, cur + delta)
    applied = new - cur
    if applied == 0:
        return None
    p["balance"][k] = new
    day = p["daily"].setdefault(_today(), {})
    day[k] = day.get(k, 0) + applied
    if len(p["daily"]) > 400:
        for old in sorted(p["daily"])[:len(p["daily"]) - 400]:
            p["daily"].pop(old, None)
    p["counter"] += 1
    ent = {"id": p["counter"], "t": int(time.time()), "u": uid, "d": applied, "why": why[:100], "by": by, "cat": cat}
    p["log"].append(ent)
    cap(p["log"], 5000)
    lg.save()
    return ent


def award_error(g: discord.Guild, actor: discord.Member, target: discord.Member, amount: int, reason: str) -> Optional[str]:
    p = lg.get(g.id)["points"]
    ar = rank_of(actor)
    if target.bot:
        return "BOTにはポイントを付与できません。"
    if target.id == actor.id:
        return "自分自身にはポイントを付与できません。"
    used, now, k = _used(p), time.time(), str(actor.id)
    if ar < 5:
        if amount > p["max_award"]:
            return f"1回に付与できるのは {p['max_award']}pt までです。"
        left = p["staff_daily_budget"] - used["give"].get(k, 0)
        if amount > left:
            return f"あなたの本日の付与上限に達しています。(残り {max(0, left)}pt)"
        room = p["user_daily_cap"] - used["get"].get(str(target.id), 0)
        if amount > room:
            return f"このメンバーが本日スタッフから受け取れる上限に達しています。(残り {max(0, room)}pt)"
    for e in reversed(p["log"][-200:]):
        if e.get("x") or e["d"] <= 0 or e["cat"] in ("auto", "undo"):
            continue
        if now - e["t"] < 600 and e["by"] == actor.id and e["u"] == target.id and e["why"] == reason[:100]:
            return "同じ内容の付与を短時間に繰り返せません。(二重付与の防止)"
        if now - e["t"] < 86400 and e["by"] == target.id and e["u"] == actor.id:
            asyncio.create_task(send_log(g, make_embed(
                "🚨 ポイントの相互付与を拒否", f"{actor.mention} ⇄ {target.mention}\n24時間以内にお互いへ付与しようとしました。(不正の疑い)", RED)))
            return "24時間以内に、そのメンバーから付与を受けているため付与できません。(相互付与の防止)"
    return None


@points_group.command(name="add", description="メンバーにポイントを付与します")
@app_commands.describe(member="付与するメンバー", amount="ポイント数", reason="理由(必須)", category="カテゴリ")
@app_commands.choices(category=CAT_CHOICES)
@perm_check("points_add")
@app_commands.checks.cooldown(1, 3, key=lambda i: i.user.id)
@lg_guard
async def pt_add(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 100000],
                 reason: app_commands.Range[str, 1, 100], category: Optional[app_commands.Choice[str]] = None):
    ent, bal = await core_points_add(interaction.guild, interaction.user, member, amount, reason, category.value if category else "other")
    await interaction.response.send_message(f"💰 {member.mention} に **+{amount}pt** を付与しました。(合計 {bal:,}pt)\n理由: {reason}",
                                            allowed_mentions=NONE)


@points_group.command(name="remove", description="メンバーのポイントを減らします")
@app_commands.describe(member="対象メンバー", amount="減らすポイント数", reason="理由(必須)")
@perm_check("points_remove")
@app_commands.checks.cooldown(1, 3, key=lambda i: i.user.id)
@lg_guard
async def pt_remove(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 100000],
                    reason: app_commands.Range[str, 1, 100]):
    ent, bal = await core_points_remove(interaction.guild, interaction.user, member, amount, reason)
    await interaction.response.send_message(f"➖ {member.mention} から **{-ent['d']}pt** を減らしました。(合計 {bal:,}pt)\n理由: {reason}",
                                            allowed_mentions=NONE)


@points_group.command(name="undo", description="ポイント履歴を1件取り消します(履歴番号は /points history で確認)")
@app_commands.describe(entry_id="履歴番号")
@perm_check("points_undo")
@lg_guard
async def pt_undo(interaction: discord.Interaction, entry_id: app_commands.Range[int, 1, 10_000_000]):
    await eph(interaction, await core_points_undo(interaction.guild, interaction.user, entry_id))


def _period_start(period: str) -> str:
    now = datetime.now(JST)
    return (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d") if period == "week" else now.strftime("%Y-%m-01")


def period_totals(gid: int, period: str) -> dict:
    p = lg.get(gid)["points"]
    if period == "total":
        return dict(p["balance"])
    start, out = _period_start(period), {}
    for d, m in p["daily"].items():
        if d >= start:
            for u, n in m.items():
                out[u] = out.get(u, 0) + n
    return out


def month_totals(gid: int, ym: str) -> dict:
    out = {}
    for d, m in lg.get(gid)["points"]["daily"].items():
        if d.startswith(ym):
            for u, n in m.items():
                out[u] = out.get(u, 0) + n
    return out


def ranked(g: discord.Guild, totals: dict) -> list:
    rows = sorted(((int(u), n) for u, n in totals.items() if n > 0), key=lambda x: (-x[1], x[0]))
    out = []
    for u, n in rows:
        m = g.get_member(u)
        if m and not m.bot:
            out.append((m, n))
    return out


MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


@app_commands.command(name="ranking", description="ポイントランキングを表示します")
@app_commands.describe(period="期間")
@app_commands.choices(period=[app_commands.Choice(name="週間(月曜〜)", value="week"), app_commands.Choice(name="月間", value="month"),
                              app_commands.Choice(name="累計(貢献度)", value="total")])
@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
async def ranking_cmd(interaction: discord.Interaction, period: Optional[app_commands.Choice[str]] = None):
    g, per = interaction.guild, (period.value if period else "week")
    rows = ranked(g, period_totals(g.id, per))
    name = {"week": "週間", "month": "月間", "total": "累計(貢献度)"}[per]
    lines = [f"{MEDALS.get(i, f'`{i}.`')} {m.mention} — **{n:,}** pt" for i, (m, n) in enumerate(rows[:10], 1)]
    e = make_embed(f"🏆 {name}ランキング", "\n".join(lines) or "まだポイントがありません。", BLUE)
    mine = next(((i, n) for i, (m, n) in enumerate(rows, 1) if m.id == interaction.user.id), None)
    if mine:
        e.set_footer(text=f"あなたの順位: {mine[0]}位 ({mine[1]:,}pt)")
    await interaction.response.send_message(embed=e, allowed_mentions=NONE)


@points_group.command(name="show", description="ポイントと順位を表示します")
async def pt_show(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    g, m = interaction.guild, member or interaction.user
    e = make_embed(f"💰 {m.display_name} のポイント", color=BLUE)
    for key, name in (("total", "累計"), ("month", "今月"), ("week", "今週")):
        tot = period_totals(g.id, key)
        rows = ranked(g, tot)
        pos = next((i for i, (x, _) in enumerate(rows, 1) if x.id == m.id), None)
        e.add_field(name=name, value=f"**{tot.get(str(m.id), 0):,}** pt" + (f" ({pos}位)" if pos else ""))
    await interaction.response.send_message(embed=e, ephemeral=True)


@points_group.command(name="history", description="ポイントの履歴を表示します(他人の履歴はスタッフのみ)")
@app_commands.describe(member="省略すると自分", count="表示件数(1〜20)")
async def pt_history(interaction: discord.Interaction, member: Optional[discord.Member] = None, count: app_commands.Range[int, 1, 20] = 10):
    g, m = interaction.guild, member or interaction.user
    if m.id != interaction.user.id and rank_of(interaction.user) < need(g.id, "points_peek"):
        return await eph(interaction, f"❌ 他の人の履歴は「{rname(need(g.id, 'points_peek'))}」以上のみ見られます。")
    ents = [e for e in lg.get(g.id)["points"]["log"] if e["u"] == m.id][-count:]
    lines = [f"`#{e['id']}` <t:{e['t']}:d> **{e['d']:+d}pt** [{CAT_NAMES.get(e['cat'], e['cat'])}] {e['why']}"
             + (f" (by <@{e['by']}>)" if e["by"] else "") + (" ~~取消済~~" if e.get("x") else "") for e in reversed(ents)]
    await interaction.response.send_message(embed=_lines_embed(f"📜 {m.display_name} のポイント履歴", lines), ephemeral=True, allowed_mentions=NONE)


@points_group.command(name="config", description="ポイントの上限・自動付与・MVPの設定(指定した項目のみ変更)")
@app_commands.describe(
    max_award="スタッフ1回あたりの付与上限", staff_daily_budget="スタッフ1人の1日の付与上限", user_daily_cap="1人が1日にスタッフから受け取れる上限",
    alert_threshold="この値以上の付与はログで警告", auto_channel_add="自動付与の対象に追加するチャンネル", auto_channel_remove="自動付与の対象から外すチャンネル",
    auto_points="自動付与:1回あたり(0で停止)", auto_min_len="自動付与:最低文字数", auto_cooldown="自動付与:同じ人の間隔(秒)",
    auto_daily_cap="自動付与:1人の1日の上限", min_member_days="自動付与:参加から何日以上の人だけ",
    mvp_channel="MVP発表のチャンネル", mvp_role="MVPに付与するロール", mvp_auto="毎月1日に自動発表する")
@perm_check("rank_manage")
@lg_guard
async def pt_config(interaction: discord.Interaction,
                    max_award: Optional[app_commands.Range[int, 1, 100000]] = None, staff_daily_budget: Optional[app_commands.Range[int, 1, 1000000]] = None,
                    user_daily_cap: Optional[app_commands.Range[int, 1, 1000000]] = None, alert_threshold: Optional[app_commands.Range[int, 1, 1000000]] = None,
                    auto_channel_add: Optional[discord.TextChannel] = None, auto_channel_remove: Optional[discord.TextChannel] = None,
                    auto_points: Optional[app_commands.Range[int, 0, 100]] = None, auto_min_len: Optional[app_commands.Range[int, 1, 500]] = None,
                    auto_cooldown: Optional[app_commands.Range[int, 10, 86400]] = None, auto_daily_cap: Optional[app_commands.Range[int, 1, 10000]] = None,
                    min_member_days: Optional[app_commands.Range[int, 0, 365]] = None, mvp_channel: Optional[discord.TextChannel] = None,
                    mvp_role: Optional[discord.Role] = None, mvp_auto: Optional[bool] = None):
    vals = dict(max_award=max_award, staff_daily_budget=staff_daily_budget, user_daily_cap=user_daily_cap, alert_threshold=alert_threshold,
                auto_points=auto_points, auto_min_len=auto_min_len, auto_cooldown=auto_cooldown, auto_daily_cap=auto_daily_cap,
                min_member_days=min_member_days, mvp_auto=mvp_auto)
    await eph(interaction, await core_points_config(interaction.guild, interaction.user, vals, mvp_channel, mvp_role,
                                                    auto_channel_add, auto_channel_remove))


async def announce_mvp(g: discord.Guild, ym: str, channel=None) -> tuple:
    p = lg.get(g.id)["points"]
    ch = channel or (g.get_channel(p["mvp_channel"]) if p["mvp_channel"] else None)
    if not ch or not can_post(ch, g.me):
        return False, "発表先チャンネルが未設定、またはBOTが送信できません。(`/points config mvp_channel`)"
    p["mvp_last"] = ym
    lg.save()
    rows = ranked(g, month_totals(g.id, ym))
    label = f"{ym[:4]}年{int(ym[5:])}月"
    if not rows:
        return False, f"{label}のポイントがありません。"
    win, pts = rows[0]
    e = make_embed(f"👑 {label} 月間MVP", f"{win.mention} さんが **{pts:,}pt** で月間MVPです!おめでとうございます🎉", YELLOW)
    e.set_thumbnail(url=win.display_avatar.url)
    e.add_field(name="トップ5", value="\n".join(f"{MEDALS.get(i, f'{i}.')} {m.mention} — {n:,}pt" for i, (m, n) in enumerate(rows[:5], 1)), inline=False)
    try:
        await ch.send(embed=e, allowed_mentions=discord.AllowedMentions(users=[win]))
    except discord.HTTPException:
        return False, "発表の送信に失敗しました。"
    note = ""
    role = g.get_role(p["mvp_role"]) if p["mvp_role"] else None
    if role and bot_can_grant(g, role):
        try:
            for m in list(role.members):
                if m.id != win.id:
                    await m.remove_roles(role, reason="AZQ BOT MVP交代")
            if role not in win.roles:
                await win.add_roles(role, reason=f"AZQ BOT {label} MVP")
            note = f" MVPロール({role.name})を付与しました。"
        except discord.HTTPException:
            note = " ⚠️ MVPロールの付与に失敗しました。"
    p["mvp_hist"].append({"ym": ym, "u": win.id, "pts": pts, "t": int(time.time())})
    cap(p["mvp_hist"], 120)
    lg.save()
    await send_log(g, make_embed("👑 月間MVP発表", f"{label}: {win} (`{win.id}`) {pts:,}pt", GREEN))
    return True, f"{label}のMVP: {win.mention} ({pts:,}pt)を発表しました。" + note


@points_group.command(name="mvp", description="月間MVPを発表します(省略すると先月分)")
@app_commands.describe(month="対象月(例: 2026-09)", channel="発表先(省略すると設定済みのチャンネル)")
@perm_check("mvp")
@lg_guard
async def pt_mvp(interaction: discord.Interaction, month: Optional[str] = None, channel: Optional[discord.TextChannel] = None):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(await core_mvp(interaction.guild, month, channel), ephemeral=True, allowed_mentions=NONE)


# ───────────────────────── イベント・定期処理 ─────────────────────────

_auto_last: dict = {}


async def on_message_points(message: discord.Message) -> None:
    g, m = message.guild, message.author
    if g is None or m.bot or not isinstance(m, discord.Member) or lg is None:
        return
    cfg = lg.data.get(str(g.id))
    if not cfg or message.channel.id not in cfg["points"]["auto_channels"]:
        return
    p = cfg["points"]
    text = message.content.strip()
    if p["auto_points"] <= 0 or len(text) < p["auto_min_len"]:
        return
    if m.joined_at and (discord.utils.utcnow() - m.joined_at).days < p["min_member_days"]:
        return
    key, now, h = (g.id, m.id), time.time(), hash(text)
    last = _auto_last.get(key)
    if last and (now - last[0] < p["auto_cooldown"] or last[1] == h):
        return
    used = _used(p)
    got = used["auto"].get(str(m.id), 0)
    if got + p["auto_points"] > p["auto_daily_cap"]:
        return
    _auto_last[key] = (now, h)
    used["auto"][str(m.id)] = got + p["auto_points"]
    apply_points(g.id, m.id, p["auto_points"], "情報共有(自動)", 0, "auto")


async def on_member_update_roles(before: discord.Member, after: discord.Member) -> None:
    if lg is None or before.roles == after.roles:
        return
    b, a = {r.id for r in before.roles}, {r.id for r in after.roles}
    add, rem = a - b, b - a
    if not add and not rem:
        return
    g = after.guild
    by, why = None, ""
    await asyncio.sleep(1.5)
    try:
        if g.me.guild_permissions.view_audit_log:
            async for en in g.audit_logs(limit=8, action=discord.AuditLogAction.member_role_update):
                if en.target and en.target.id == after.id and (discord.utils.utcnow() - en.created_at).total_seconds() < 20:
                    by, why = en.user.id if en.user else None, en.reason or ""
                    break
    except discord.HTTPException:
        pass
    c = lg.get(g.id)
    c["role_hist"].append({"t": int(time.time()), "u": after.id, "add": sorted(add), "rem": sorted(rem), "by": by, "why": why[:100]})
    cap(c["role_hist"], 3000)
    lg.save()
    # 役職ロールが、権限のない人によって付与された(BOTを通さずに直接付けられた)ときは警告する
    if by and by != g.me.id and add:
        actor = g.get_member(by)
        for k, rid in c["ranks"].items():
            if rid in add and actor and actor.id != g.owner_id and rank_of(actor) <= int(k):
                await send_log(g, make_embed("🚨 役職ロールの不審な付与",
                                                 f"{after.mention} に「{rname(int(k))}」のロールが、**{rname(rank_of(actor))}** の {actor.mention} によって直接付与されました。\n"
                                                 "BOTの審査を通っていない可能性があります。確認してください。", RED))
                break


async def on_raw_delete(payload: discord.RawMessageDeleteEvent) -> None:
    if lg is None or not payload.guild_id:
        return
    cfg = lg.data.get(str(payload.guild_id))
    if not cfg:
        return
    changed = False
    for sec in (cfg["apply"], cfg["staff"], cfg["region"]):
        if sec["panel_message"] == payload.message_id:
            sec["panel_message"] = None
            changed = True
    if changed:
        lg.save()


@tasks.loop(minutes=1)
async def temp_role_watch():
    now = time.time()
    for g in list(bot.guilds):
        c = lg.data.get(str(g.id))
        if not c or not c["temp_roles"]:
            continue
        keep, changed = [], False
        for t in c["temp_roles"]:
            if t["exp"] > now:
                keep.append(t)
                continue
            changed = True
            m, role = g.get_member(t["u"]), g.get_role(t["r"])
            if m and role and role in m.roles:
                try:
                    await m.remove_roles(role, reason="AZQ BOT 期限切れ")
                except discord.HTTPException:
                    log.warning("期限切れロールの剥奪に失敗 guild=%s", g.id)
        if changed:
            c["temp_roles"] = keep
            lg.save()
    for k in [k for k, (t, _) in _auto_last.items() if now - t > 3600]:
        _auto_last.pop(k, None)
    for k in [k for k, dq in _heavy.items() if not dq or now - dq[-1] > HEAVY_WINDOW]:
        _heavy.pop(k, None)


@tasks.loop(minutes=30)
async def mvp_watch():
    first = datetime.now(JST).replace(day=1)
    ym = (first - timedelta(days=1)).strftime("%Y-%m")
    for g in list(bot.guilds):
        c = lg.data.get(str(g.id))
        if not c:
            continue
        p = c["points"]
        if not p["mvp_auto"] or not p["mvp_channel"] or p["mvp_last"] == ym:
            continue
        try:
            await announce_mvp(g, ym)
        except Exception:
            log.exception("月間MVPの自動発表に失敗 guild=%s", g.id)


@temp_role_watch.before_loop
async def _b1():
    await bot.wait_until_ready()


@mvp_watch.before_loop
async def _b2():
    await bot.wait_until_ready()
    await asyncio.sleep(90)


def srvadm_install() -> None:
    for cmd in (srvadm_group, apply_group, staff_group, points_group, region_group, ranking_cmd):
        bot.tree.add_command(cmd)
    bot.add_view(ApplyPanelView())
    bot.add_view(StaffPanelView())
    bot.add_view(RegionPanelView())
    bot.add_dynamic_items(ReviewButton)
    bot.add_listener(on_message_points, "on_message")
    bot.add_listener(on_member_update_roles, "on_member_update")
    bot.add_listener(on_raw_delete, "on_raw_message_delete")
    temp_role_watch.start()
    mvp_watch.start()


@bot.tree.command(name="kick", description="メンバーをキックします")
@perm_check("kick")
@app_commands.checks.bot_has_permissions(kick_members=True)
@app_commands.guild_only()
async def kick(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
    if err := hierarchy_error(interaction, member):
        return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
    await try_dm(member, f"**{interaction.guild.name}** からキックされました。\n理由: {reason or 'なし'}")
    await member.kick(reason=f"{interaction.user}: {reason}")
    await interaction.response.send_message(f"👢 {member} をキックしました。")
    await send_log(interaction.guild, make_embed("👢 Kick", f"{member} (`{member.id}`)\n実行者: {interaction.user}\n理由: {reason or 'なし'}", YELLOW))


@bot.tree.command(name="ban", description="メンバーをBANします")
@perm_check("ban")
@app_commands.describe(delete_days="過去何日分のメッセージを削除するか(0〜7)")
@app_commands.checks.bot_has_permissions(ban_members=True)
@app_commands.guild_only()
async def ban(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None,
              delete_days: app_commands.Range[int, 0, 7] = 0):
    if err := hierarchy_error(interaction, member):
        return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
    await try_dm(member, f"**{interaction.guild.name}** からBANされました。\n理由: {reason or 'なし'}")
    await member.ban(reason=f"{interaction.user}: {reason}", delete_message_seconds=delete_days * 86400)
    await interaction.response.send_message(f"🔨 {member} をBANしました。")
    await send_log(interaction.guild, make_embed("🔨 Ban", f"{member} (`{member.id}`)\n実行者: {interaction.user}\n理由: {reason or 'なし'}", RED))


@bot.tree.command(name="unban", description="ユーザーIDでBANを解除します")
@perm_check("unban")
@app_commands.checks.bot_has_permissions(ban_members=True)
@app_commands.guild_only()
async def unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user, reason=f"{interaction.user}")
    except (ValueError, discord.NotFound):
        return await interaction.response.send_message("❌ そのユーザーはBANされていません(IDを確認してください)。", ephemeral=True)
    await interaction.response.send_message(f"✅ {user} のBANを解除しました。")
    await send_log(interaction.guild, make_embed("✅ Unban", f"{user} (`{user.id}`)\n実行者: {interaction.user}", GREEN))


@bot.tree.command(name="timeout", description="メンバーをタイムアウト(発言禁止)します")
@perm_check("timeout")
@app_commands.describe(minutes="分(1〜40320 = 28日)")
@app_commands.checks.bot_has_permissions(moderate_members=True)
@app_commands.guild_only()
async def timeout_cmd(interaction: discord.Interaction, member: discord.Member,
                      minutes: app_commands.Range[int, 1, 40320], reason: Optional[str] = None):
    if err := hierarchy_error(interaction, member):
        return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
    await member.timeout(timedelta(minutes=minutes), reason=f"{interaction.user}: {reason}")
    await interaction.response.send_message(f"🔇 {member.mention} を {minutes}分 タイムアウトしました。")
    await send_log(interaction.guild, make_embed("🔇 Timeout", f"{member} (`{member.id}`) {minutes}分\n実行者: {interaction.user}\n理由: {reason or 'なし'}", YELLOW))


@bot.tree.command(name="untimeout", description="タイムアウトを解除します")
@perm_check("untimeout")
@app_commands.checks.bot_has_permissions(moderate_members=True)
@app_commands.guild_only()
async def untimeout(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None, reason=f"{interaction.user}")
    await interaction.response.send_message(f"🔊 {member.mention} のタイムアウトを解除しました。")


@bot.tree.command(name="warn", description="メンバーに警告を与えます(規定回数で自動タイムアウト)")
@perm_check("warn")
@app_commands.guild_only()
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    if err := hierarchy_error(interaction, member):
        return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
    cfg = store.get(interaction.guild.id)
    lst = cfg["warns"].setdefault(str(member.id), [])
    lst.append({"reason": reason, "mod": interaction.user.id, "time": int(time.time())})
    store.save()
    msg = f"⚠️ {member.mention} に警告を与えました ({len(lst)}/{cfg['warn_limit']})\n理由: {reason}"
    if len(lst) >= cfg["warn_limit"]:
        try:
            await member.timeout(timedelta(minutes=cfg["warn_timeout_minutes"]), reason="警告上限到達")
            msg += f"\n🔇 警告が上限に達したため {cfg['warn_timeout_minutes']}分 タイムアウトしました。"
        except discord.HTTPException:
            msg += "\n(自動タイムアウトに失敗しました。BOTの権限を確認してください)"
    await try_dm(member, f"**{interaction.guild.name}** で警告を受けました。\n理由: {reason}")
    await interaction.response.send_message(msg)
    await send_log(interaction.guild, make_embed("⚠️ Warn", f"{member} (`{member.id}`)\n実行者: {interaction.user}\n理由: {reason}", YELLOW))


@bot.tree.command(name="warnings", description="メンバーの警告履歴を表示します")
@perm_check("warnings")
@app_commands.guild_only()
async def warnings(interaction: discord.Interaction, member: discord.Member):
    lst = store.get(interaction.guild.id)["warns"].get(str(member.id), [])
    if not lst:
        return await interaction.response.send_message(f"{member} に警告はありません。", ephemeral=True)
    start = max(0, len(lst) - 15)
    lines = [f"`{i}.` <t:{w['time']}:d> {w['reason']} (by <@{w['mod']}>)" for i, w in enumerate(lst[start:], start + 1)]
    await interaction.response.send_message(embed=make_embed(f"⚠️ {member} の警告 ({len(lst)}件)", "\n".join(lines), YELLOW), ephemeral=True)


@bot.tree.command(name="clearwarns", description="メンバーの警告をすべて消去します")
@perm_check("clearwarns")
@app_commands.guild_only()
async def clearwarns(interaction: discord.Interaction, member: discord.Member):
    store.get(interaction.guild.id)["warns"].pop(str(member.id), None)
    store.save()
    await interaction.response.send_message(f"🧹 {member} の警告を消去しました。")


@bot.tree.command(name="unwarn", description="警告を1件取り消します(番号は /warnings で確認)")
@perm_check("unwarn")
@app_commands.guild_only()
async def unwarn(interaction: discord.Interaction, member: discord.Member, number: app_commands.Range[int, 1, 10000]):
    lst = store.get(interaction.guild.id)["warns"].get(str(member.id), [])
    if number > len(lst):
        return await interaction.response.send_message("❌ その番号の警告はありません。`/warnings` で確認してください。", ephemeral=True)
    removed = lst.pop(number - 1)
    if not lst:
        store.get(interaction.guild.id)["warns"].pop(str(member.id), None)
    store.save()
    await interaction.response.send_message(f"✅ {member.mention} の警告 #{number} を取り消しました。(残り {len(lst)}件)",
                                            allowed_mentions=discord.AllowedMentions.none())
    await send_log(interaction.guild, make_embed("↩️ Unwarn", f"{member} (`{member.id}`)\n実行者: {interaction.user}\n取消した警告: {removed['reason']}", GREEN))


@bot.tree.command(name="purge", description="メッセージを一括削除します")
@perm_check("purge")
@app_commands.describe(amount="削除件数(1〜100)", member="このメンバーのメッセージのみ削除")
@app_commands.checks.bot_has_permissions(manage_messages=True, read_message_history=True)
@app_commands.guild_only()
async def purge(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100], member: Optional[discord.Member] = None):
    await interaction.response.defer(ephemeral=True)
    check = (lambda m: m.author.id == member.id) if member else None
    deleted = await interaction.channel.purge(limit=amount, check=check)
    await interaction.followup.send(f"🧹 {len(deleted)}件削除しました。", ephemeral=True)
    await send_log(interaction.guild, make_embed("🧹 Purge", f"{interaction.channel.mention} で {len(deleted)}件削除\n実行者: {interaction.user}", GRAY))


@bot.tree.command(name="slowmode", description="チャンネルの低速モードを設定します(0で解除)")
@perm_check("slowmode")
@app_commands.checks.bot_has_permissions(manage_channels=True)
@app_commands.guild_only()
async def slowmode(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message("🐢 低速モードを解除しました。" if seconds == 0 else f"🐢 低速モードを {seconds}秒 に設定しました。")


@bot.tree.command(name="lock", description="このチャンネルを@everyoneの発言禁止にします")
@perm_check("lock")
@app_commands.checks.bot_has_permissions(manage_roles=True, manage_channels=True)
@app_commands.guild_only()
async def lock(interaction: discord.Interaction):
    ch, role = interaction.channel, interaction.guild.default_role
    ow = ch.overwrites_for(role)
    ow.send_messages = False
    await ch.set_permissions(role, overwrite=ow, reason=f"lock by {interaction.user}")
    await interaction.response.send_message("🔒 チャンネルをロックしました。")


@bot.tree.command(name="unlock", description="チャンネルのロックを解除します")
@perm_check("lock")
@app_commands.checks.bot_has_permissions(manage_roles=True, manage_channels=True)
@app_commands.guild_only()
async def unlock(interaction: discord.Interaction):
    ch, role = interaction.channel, interaction.guild.default_role
    ow = ch.overwrites_for(role)
    ow.send_messages = None
    await ch.set_permissions(role, overwrite=ow, reason=f"unlock by {interaction.user}")
    await interaction.response.send_message("🔓 ロックを解除しました。")


async def _role_change(interaction: discord.Interaction, member: discord.Member, role: discord.Role, add: bool):
    g = interaction.guild
    if role >= g.me.top_role or role.managed or role.is_default():
        return await interaction.response.send_message("❌ BOTがそのロールを操作できません(ロール順位を確認してください)。", ephemeral=True)
    if interaction.user.id != g.owner_id and role >= interaction.user.top_role:
        return await interaction.response.send_message("❌ あなたと同位以上のロールは操作できません。", ephemeral=True)
    if add:
        await member.add_roles(role, reason=f"{interaction.user}")
    else:
        await member.remove_roles(role, reason=f"{interaction.user}")
    await interaction.response.send_message(f"{'➕' if add else '➖'} {member.mention} に {role.mention} を{'付与' if add else '剥奪'}しました。",
                                            allowed_mentions=discord.AllowedMentions.none())


@bot.tree.command(name="role_add", description="メンバーにロールを付与します")
@perm_check("role_add")
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.guild_only()
async def role_add(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await _role_change(interaction, member, role, True)


@bot.tree.command(name="role_remove", description="メンバーからロールを剥奪します")
@perm_check("role_remove")
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.guild_only()
async def role_remove(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await _role_change(interaction, member, role, False)


@bot.tree.command(name="userinfo", description="ユーザー情報を表示します")
@app_commands.guild_only()
async def userinfo(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    m = member or interaction.user
    e = make_embed(f"👤 {m}", color=m.color.value or BLUE)
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="ID", value=str(m.id))
    e.add_field(name="アカウント作成", value=discord.utils.format_dt(m.created_at, "R"))
    e.add_field(name="サーバー参加", value=discord.utils.format_dt(m.joined_at, "R") if m.joined_at else "不明")
    roles = [r.mention for r in reversed(m.roles) if not r.is_default()]
    e.add_field(name=f"ロール ({len(roles)})", value=" ".join(roles[:15]) or "なし", inline=False)
    e.add_field(name="警告回数", value=str(len(store.get(interaction.guild.id)["warns"].get(str(m.id), []))))
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="serverinfo", description="サーバー情報を表示します")
@app_commands.guild_only()
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    humans = sum(1 for m in g.members if not m.bot)
    e = make_embed(f"🏠 {g.name}")
    if g.icon:
        e.set_thumbnail(url=g.icon.url)
    e.add_field(name="オーナー", value=f"<@{g.owner_id}>")
    e.add_field(name="メンバー", value=f"{g.member_count:,} (人間 {humans:,} / BOT {g.member_count - humans:,})")
    e.add_field(name="作成日", value=discord.utils.format_dt(g.created_at, "D"))
    e.add_field(name="チャンネル", value=f"テキスト {len(g.text_channels)} / ボイス {len(g.voice_channels)}")
    e.add_field(name="ロール数", value=str(len(g.roles)))
    e.add_field(name="ブースト", value=f"Lv{g.premium_tier} ({g.premium_subscription_count}件)")
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="bot_users", description="BOT全体の利用ユーザー数を集計します（指定ユーザー専用）")
async def bot_users(interaction: discord.Interaction):
    if interaction.user.id != 1453953586626166899:
        await interaction.response.send_message(
            "❌ このコマンドを利用できるのは指定されたユーザーのみです。",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    unique_users = set()
    total_memberships = 0
    incomplete_guilds = 0

    for guild in bot.guilds:
        try:
            members = guild.members if guild.chunked else await guild.chunk(cache=True)
        except Exception:
            log.warning("利用ユーザー数の集計でメンバー取得に失敗 guild=%s (%s)", guild.id, guild.name, exc_info=True)
            members = guild.members
            incomplete_guilds += 1

        humans = [member for member in members if not member.bot]
        total_memberships += len(humans)
        unique_users.update(member.id for member in humans)

    e = make_embed("📊 AZQ BOT 利用ユーザー数", color=BLUE)
    e.add_field(name="利用ユーザー数（重複除外）", value=f"**{len(unique_users):,} 人**", inline=False)
    e.add_field(name="サーバー内の人間メンバー合計（重複あり）", value=f"{total_memberships:,} 人分", inline=False)
    e.add_field(name="導入サーバー数", value=f"{len(bot.guilds):,} サーバー", inline=False)
    e.set_footer(text="BOTアカウントは除外しています。")
    if incomplete_guilds:
        e.description = (
            f"⚠️ {incomplete_guilds} サーバーでメンバー一覧を完全取得できなかったため、\n"
            "利用ユーザー数はキャッシュ済みメンバーのみの集計を含みます。"
        )
    await interaction.followup.send(embed=e, ephemeral=True)


@bot.tree.command(name="avatar", description="アイコン画像を表示します")
async def avatar(interaction: discord.Interaction, user: Optional[discord.User] = None):
    u = user or interaction.user
    e = make_embed(f"🖼️ {u} のアイコン")
    e.set_image(url=u.display_avatar.replace(size=1024).url)
    await interaction.response.send_message(embed=e)


KING_MIN, KING_MAX = 3, 20
KING_LOBBY_SEC = 900
KING_GAMES: dict = {}
_king_rng = random.SystemRandom()


class KingGame:
    def __init__(self, channel_id: int, host_id: int, max_players: int):
        self.channel_id = channel_id
        self.host_id = host_id
        self.max_players = max_players
        self.players: list = [host_id]
        self.started = False
        self.message_id: Optional[int] = None


def _king_is_host(interaction: discord.Interaction, game: KingGame) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    return interaction.user.id == game.host_id or bool(perms and perms.manage_guild)


def _king_release(game: KingGame) -> None:
    if KING_GAMES.get(game.channel_id) is game:
        del KING_GAMES[game.channel_id]


def king_lobby_embed(game: KingGame) -> discord.Embed:
    e = make_embed("👑 王様ゲーム 参加者募集中",
                   f"ホスト: <@{game.host_id}>\n「参加する」を押して参加してください。\n"
                   f"{KING_MIN}人以上({game.max_players}人まで)集まったら、ホストが「開始」を押します。", YELLOW)
    e.add_field(name=f"参加者 ({len(game.players)}/{game.max_players})",
                value="\n".join(f"{i}. <@{u}>" for i, u in enumerate(game.players, 1)), inline=False)
    e.set_footer(text="開始すると王様と番号が自動で決まり、番号はDMで届きます(DMを受け取れる設定にしてください)")
    return e


class KingLobbyView(discord.ui.View):
    def __init__(self, game: KingGame):
        super().__init__(timeout=KING_LOBBY_SEC)
        self.game = game

    @discord.ui.button(label="参加する", emoji="🙋", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = self.game
        if interaction.user.id in g.players:
            return await interaction.response.send_message("すでに参加しています。", ephemeral=True)
        if len(g.players) >= g.max_players:
            return await interaction.response.send_message("❌ 満員です。", ephemeral=True)
        g.players.append(interaction.user.id)
        await interaction.response.edit_message(embed=king_lobby_embed(g))

    @discord.ui.button(label="退出", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = self.game
        if interaction.user.id not in g.players:
            return await interaction.response.send_message("参加していません。", ephemeral=True)
        if interaction.user.id == g.host_id:
            return await interaction.response.send_message("ホストは退出できません。やめる場合は「中止」を押してください。", ephemeral=True)
        g.players.remove(interaction.user.id)
        await interaction.response.edit_message(embed=king_lobby_embed(g))

    @discord.ui.button(label="開始", emoji="▶️", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = self.game
        if not _king_is_host(interaction, g):
            return await interaction.response.send_message("❌ 開始できるのはホストだけです。", ephemeral=True)
        if len(g.players) < KING_MIN:
            return await interaction.response.send_message(f"❌ {KING_MIN}人以上必要です(現在 {len(g.players)}人)。", ephemeral=True)
        g.started = True
        _king_release(g)
        self.stop()

        order = g.players[:]
        _king_rng.shuffle(order)
        king = order[0]
        numbers = {uid: i for i, uid in enumerate(order[1:], start=1)}

        e = make_embed("👑 王様ゲーム スタート!",
                       f"王様は <@{king}> さんです!\n"
                       "各自の番号はDMで送りました。王様の命令を待ちましょう。\n"
                       "(命令は自由に、チャンネルで「○番が△番に…」のように出してください)", YELLOW)
        e.add_field(name=f"参加者 ({len(g.players)}人)", value=" ".join(f"<@{u}>" for u in g.players), inline=False)
        e.add_field(name="番号", value=f"1〜{len(g.players) - 1}番", inline=True)
        await interaction.response.edit_message(
            embed=e, view=None, allowed_mentions=discord.AllowedMentions.none())

        failed = []
        for uid in g.players:
            if uid == king:
                de = make_embed("👑 あなたは王様です!", f"**{interaction.guild.name}** の王様ゲームで王様に選ばれました。\n"
                                "チャンネルで好きな命令を出してください。(番号は 1〜%d番)" % (len(g.players) - 1), YELLOW)
            else:
                de = make_embed(f"🔢 あなたは {numbers[uid]}番 です", f"**{interaction.guild.name}** の王様ゲームの番号です。\n"
                                "王様の命令を待ちましょう。(他の人に見せないでね)", BLUE)
            try:
                user = interaction.guild.get_member(uid) or await bot.fetch_user(uid)
                await user.send(embed=de)
            except (discord.Forbidden, discord.HTTPException):
                failed.append(uid)
        if failed:
            await interaction.followup.send(
                "⚠️ " + " ".join(f"<@{u}>" for u in failed)
                + " にDMを送れませんでした。DMを許可してから、もう一度 `/ousama` でやり直してください。",
                allowed_mentions=discord.AllowedMentions(users=[discord.Object(id=u) for u in failed]))

    @discord.ui.button(label="中止", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = self.game
        if not _king_is_host(interaction, g):
            return await interaction.response.send_message("❌ 中止できるのはホストだけです。", ephemeral=True)
        _king_release(g)
        self.stop()
        await interaction.response.edit_message(embed=make_embed("👑 王様ゲーム", "募集を中止しました。", GRAY), view=None)

    async def on_timeout(self):
        g = self.game
        if g.started:
            return
        _king_release(g)
        ch = bot.get_channel(g.channel_id)
        if ch and g.message_id:
            try:
                await ch.get_partial_message(g.message_id).edit(
                    embed=make_embed("👑 王様ゲーム", "募集がタイムアウトしました。", GRAY), view=None)
            except discord.HTTPException:
                pass


@bot.tree.command(name="ousama", description="王様ゲームを始めます(王様と番号を自動で決めてDMで通知)")
@app_commands.describe(max_players=f"最大参加人数({KING_MIN}〜{KING_MAX}、既定10)")
@app_commands.guild_only()
async def ousama(interaction: discord.Interaction, max_players: app_commands.Range[int, KING_MIN, KING_MAX] = 10):
    if interaction.channel_id in KING_GAMES:
        return await interaction.response.send_message("❌ このチャンネルでは、すでに王様ゲームを募集中です。", ephemeral=True)
    game = KingGame(interaction.channel_id, interaction.user.id, max_players)
    KING_GAMES[interaction.channel_id] = game
    await interaction.response.send_message(embed=king_lobby_embed(game), view=KingLobbyView(game))
    try:
        game.message_id = (await interaction.original_response()).id
    except discord.HTTPException:
        pass


VERIFY_MODES = {"button": "ボタン認証", "math": "計算認証", "image": "画像認証(CAPTCHA)", "web": "Web認証(ブラウザで確認)"}
VIOLATION_MODES = {"deny": "拒否のみ(一時ロック)", "kick": "キック"}
CAPTCHA_CHARS = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CHALLENGE_TTL = 180
RAID_VERIFY_SECONDS = 600
RAID_MIN_ACCOUNT_DAYS = 7
DANGEROUS_PERMS = (
    "administrator", "manage_guild", "manage_roles", "manage_channels", "manage_messages",
    "manage_webhooks", "kick_members", "ban_members", "moderate_members", "mention_everyone",
    "manage_nicknames", "view_audit_log",
)
MODE_CHOICES = [app_commands.Choice(name=n, value=k) for k, n in VERIFY_MODES.items()]
VIOLATION_CHOICES = [app_commands.Choice(name=n, value=k) for k, n in VIOLATION_MODES.items()]

verify_challenges: dict = {}
verify_fails: dict = {}
verify_lock: dict = {}
verify_last: dict = {}
raid_until: dict = {}
verify_issued: dict = {}
recent_joins: dict = defaultdict(lambda: deque(maxlen=50))
suspect_notified: set = set()
SOLVE_MIN_SECONDS = {"math": 2.0, "image": 3.0}
SUSPECT_CHOICES = [app_commands.Choice(name="管理者の承認待ちにする(/verify approve で承認)", value="hold"),
                   app_commands.Choice(name="キックする", value="kick")]


class IPRanges:
    """IPv4のCIDR一覧を、結合・ソートして保持する(array なので省メモリ)。判定は二分探索。"""

    def __init__(self):
        self.starts, self.ends = array("L"), array("L")

    def load(self, lines) -> int:
        spans = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                net = ipaddress.ip_network(line, strict=False)
            except ValueError:
                continue
            if net.version == 4:
                spans.append((int(net.network_address), int(net.broadcast_address)))
        spans.sort()
        merged = []
        for a, b in spans:
            if merged and a <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        self.starts, self.ends = array("L", (a for a, _ in merged)), array("L", (b for _, b in merged))
        return len(merged)

    def contains(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if addr.version != 4:
            return False
        n = int(addr)
        i = bisect.bisect_right(self.starts, n) - 1
        return i >= 0 and n <= self.ends[i]


vpn_ranges = IPRanges()
VPN_LIST_FILE = os.path.join(DATA_DIR, "vpn_ranges.txt")


def _load_vpn_file() -> int:
    if not os.path.exists(VPN_LIST_FILE):
        return 0
    with open(VPN_LIST_FILE, encoding="utf-8", errors="replace") as f:
        return vpn_ranges.load(f)


async def vpn_list_loop() -> None:
    """VPN/データセンターのIPレンジを読み込み、24時間ごとに更新する"""
    await bot.wait_until_ready()
    loop = asyncio.get_running_loop()
    while True:
        try:
            old = os.path.exists(VPN_LIST_FILE) and (time.time() - os.path.getmtime(VPN_LIST_FILE)) < 86400
            if VPN_LIST_AUTO and not old:
                parts = []
                for url in VPN_LIST_URLS:
                    async with bot.session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as r:
                        if r.status == 200:
                            parts.append(await r.text())
                        else:
                            log.warning("VPNリストの取得に失敗 HTTP %s: %s", r.status, url)
                text = "\n".join(parts)
                if text.count("\n") > 1000:
                    tmp = VPN_LIST_FILE + ".part"
                    with open(tmp, "w", encoding="utf-8") as f:
                        f.write(text)
                    os.replace(tmp, VPN_LIST_FILE)
            n = await loop.run_in_executor(None, _load_vpn_file)
            log.info("VPN・データセンターのIPレンジ: %s件を読み込みました", n) if n else log.warning(
                "VPNリストがありません。VPN判定(block_vpn)は動作しません。(%s)", VPN_LIST_FILE)
        except Exception:
            log.exception("VPNリストの更新に失敗しました")
        await asyncio.sleep(6 * 3600)


def _ip_salt() -> bytes:
    path = os.path.join(DATA_DIR, "ip_salt.key")
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(secrets.token_bytes(32))
        os.chmod(path, 0o600)
    with open(path, "rb") as f:
        return f.read()


def ip_hash(ip: str) -> str:
    """サブ垢検出用に、IPを一方向のハッシュにして保存する(IPv6は同じ家庭を同一視するため /64 でまとめる)"""
    addr = ipaddress.ip_address(ip)
    key = str(ipaddress.ip_network(f"{ip}/64", strict=False)) if addr.version == 6 else ip
    return hmac.new(_ip_salt(), key.encode(), hashlib.sha256).hexdigest()[:20]


WEB_TTL = 600
web_nonces: dict = {}
web_rate: dict = defaultdict(deque)


def make_web_link(guild_id: int, user_id: int, interaction: Optional[discord.Interaction] = None) -> str:
    now = time.time()
    for k in [k for k, r in web_nonces.items() if r["exp"] < now]:
        web_nonces.pop(k, None)
    n = secrets.token_urlsafe(18)
    web_nonces[n] = {"g": guild_id, "u": user_id, "cookie": secrets.token_urlsafe(16), "exp": now + WEB_TTL,
                     "i": interaction}
    return f"{WEB_URL}/v?t={n}"


async def notify_web_verified(interaction: Optional[discord.Interaction], member: discord.Member,
                              text: str = "✅ 認証が完了しました!ようこそ!") -> None:
    """Web認証の結果をDiscord側に知らせる。元の(自分だけに見える)メッセージを書き換え、できなければDMで送る"""
    if interaction is not None:
        try:
            await interaction.edit_original_response(content=text, view=None)
            return
        except discord.HTTPException:
            pass
    await try_dm(member, text)


def client_ip(request) -> str:
    return request.remote or ""


def _rate_ok(ip: str) -> bool:
    now, q = time.time(), web_rate[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(web_rate) > 5000:
        for k in [k for k, d in web_rate.items() if not d]:
            web_rate.pop(k, None)
    q.append(now)
    return len(q) <= 20


def _esc(x) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def web_page(body: str, status: int = 200) -> web.Response:
    html = ("<!DOCTYPE html><html lang=\"ja\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<meta name=\"robots\" content=\"noindex\"><title>認証</title><style>:root{--bg:#f6f7fb;--card:#fff;--text:#1f2430;--sub:#667085;--line:#e4e7ec;--pri:#5865f2}"
            "@media(prefers-color-scheme:dark){:root{--bg:#14161c;--card:#1d2028;--text:#e8eaf0;--sub:#9aa3b2;--line:#2c313c}}"
            "body{margin:0;font:15px/1.7 system-ui,'Hiragino Sans','Noto Sans JP',sans-serif;background:var(--bg);color:var(--text);display:grid;place-items:center;min-height:100vh;padding:16px;box-sizing:border-box}"
            ".card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px;max-width:480px;width:100%}h1{font-size:18px;margin:0 0 12px}.sub{color:var(--sub);font-size:13px}"
            ".g-recaptcha{margin:14px 0 4px;min-height:78px}.err{color:#d92d20;font-size:14px;margin:8px 0}button:disabled{background:#98a2b3;color:#f2f4f7;cursor:not-allowed;opacity:.75}button{background:var(--pri);color:#fff;border:0;border-radius:10px;padding:11px 22px;font:inherit;cursor:pointer;margin-top:8px}</style></head>"
            f"<body><div class=\"card\">{body}</div></body></html>")
    return web.Response(text=html, status=status, content_type="text/html",
                        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex", "Referrer-Policy": "no-referrer"})


def _web_expired() -> web.Response:
    return web_page("<h1>リンクが無効です</h1><p>有効期限が切れたか、すでに使用されています。Discordの認証パネルから、もう一度ボタンを押してください。</p>", 400)


def web_disclosure(v: dict) -> str:
    html = _web_disclosure_base(v)
    if RECAPTCHA_READY:
        html += "<p class=\"sub\">・ロボットでないことの確認に Google reCAPTCHA を使います(Googleの<a href=\"https://policies.google.com/privacy\" target=\"_blank\" rel=\"noopener\">プライバシーポリシー</a>・<a href=\"https://policies.google.com/terms\" target=\"_blank\" rel=\"noopener\">利用規約</a>が適用されます)。</p>"
    return html


def _web_disclosure_base(v: dict) -> str:
    items = []
    if v["block_vpn"]:
        items.append("VPN・プロキシ・データセンターの回線でないかの確認(公開されているIPの一覧と照合するだけで、IPは外部に送りません)")
    if v["block_alt_ip"]:
        items.append("同じ回線から別のアカウントが認証していないかの確認(IPアドレスはそのまま保存せず、元に戻せない値(ハッシュ)にして保存します)")
    if not items:
        return "<p class=\"sub\">・ロボットでないことの確認だけを行います。IPアドレスは保存しません。</p>"
    return "<p class=\"sub\">このサーバーでは、次の確認のために接続元のIPアドレスを一時的に使います。<br>" + "<br>".join("・" + i for i in items) + "<br>・生のIPアドレスは保存しません。</p>"


def web_verify_form(guild: discord.Guild, v: dict, t: str, notice: str = "", status: int = 200) -> web.Response:
    """認証ページ(「認証する」ボタン + reCAPTCHA)を作る。notice があればエラー表示を付ける"""
    widget, btn_attr, hint = "", "", ""
    if RECAPTCHA_READY:
        widget = ("<script>function azqBtn(on){var b=document.getElementById('azqBtn');if(b)b.disabled=!on;}</script>"
                  f'<div class="g-recaptcha" data-sitekey="{_esc(RECAPTCHA_SITE_KEY)}" data-callback="azqOk" '
                  'data-expired-callback="azqNg" data-error-callback="azqNg"></div>'
                  "<script>function azqOk(){azqBtn(true);}function azqNg(){azqBtn(false);}</script>"
                  '<script src="https://www.google.com/recaptcha/api.js" async defer></script>')
        btn_attr = " disabled"
        hint = '<p class="sub" id="azqHint">「私はロボットではありません」にチェックを入れると、ボタンが押せるようになります。</p>'
    err = f'<p class="err">⚠️ {_esc(notice)}</p>' if notice else ""
    lead = "下のチェックを入れてボタンを押すと、認証が完了します。" if RECAPTCHA_READY else "下のボタンを押すと、認証が完了します。"
    return web_page(f"<h1>🔐 {_esc(guild.name)} の認証</h1><p>{lead}</p>{web_disclosure(v)}{err}"
                    f'<form method="POST" action="/v"><input type="hidden" name="t" value="{_esc(t)}">{widget}'
                    f'<button type="submit" id="azqBtn"{btn_attr}>認証する</button>{hint}</form>', status)


async def verify_recaptcha(token: str) -> tuple:
    """reCAPTCHAのトークンをGoogleのサーバーで検証する。戻り値: (成功したか, 失敗時にユーザーへ見せる文)"""
    if not token:
        return False, "「私はロボットではありません」にチェックを入れてください。"
    try:
        async with bot.session.post(RECAPTCHA_VERIFY_URL, data={"secret": RECAPTCHA_SECRET_KEY, "response": token},
                                    timeout=aiohttp.ClientTimeout(total=10)) as r:
            j = await r.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
        log.warning("reCAPTCHAの検証サーバーに接続できませんでした: %s", e)
        return False, "reCAPTCHAの確認サーバーに接続できませんでした。少し待ってからもう一度お試しください。"
    if not isinstance(j, dict) or not j.get("success"):
        codes = (j.get("error-codes") if isinstance(j, dict) else None) or []
        if "missing-input-secret" in codes or "invalid-input-secret" in codes:
            log.error("reCAPTCHAのシークレットキーが正しくありません(RECAPTCHA_SECRET_KEY を確認してください): %s", codes)
            return False, "設定エラーです。サーバー管理者に連絡してください。"
        log.info("reCAPTCHA検証に失敗: %s", codes)
        return False, "確認に失敗しました(期限切れの可能性があります)。もう一度チェックを入れてください。"
    host, got = (urlparse(WEB_URL).hostname or "").lower(), str(j.get("hostname") or "").lower()
    if host and got and got != host:
        log.warning("reCAPTCHAのホスト名が一致しません: %s != %s", got, host)
        return False, "確認に失敗しました。もう一度お試しください。"
    return True, ""


async def web_verify_get(request):
    if not _rate_ok(client_ip(request)):
        return web_page("<h1>アクセスが多すぎます</h1><p>しばらく待ってからやり直してください。</p>", 429)
    t = request.query.get("t", "")
    rec = web_nonces.get(t)
    if not rec or rec["exp"] < time.time():
        return _web_expired()
    guild = bot.get_guild(rec["g"])
    if not guild:
        return _web_expired()
    v = store.get(guild.id)["verify"]
    resp = web_verify_form(guild, v, t)
    resp.set_cookie("azq_v", rec["cookie"], max_age=WEB_TTL, httponly=True, samesite="Lax",
                    secure=WEB_URL.startswith("https"))
    return resp


async def web_verify_post(request):
    ip_s = client_ip(request)
    if not _rate_ok(ip_s):
        return web_page("<h1>アクセスが多すぎます</h1><p>しばらく待ってからやり直してください。</p>", 429)
    form = await request.post()
    t = str(form.get("t", ""))
    rec = web_nonces.get(t)
    if not rec or rec["exp"] < time.time() or request.cookies.get("azq_v") != rec["cookie"]:
        web_nonces.pop(t, None)
        return _web_expired()
    if RECAPTCHA_READY:
        ok, why = await verify_recaptcha(str(form.get("g-recaptcha-response", "")))
        if not ok:
            rec["tries"] = rec.get("tries", 0) + 1
            g = bot.get_guild(rec["g"])
            if rec["tries"] >= 5 or not g:
                web_nonces.pop(t, None)
                return _web_expired()
            return web_verify_form(g, store.get(g.id)["verify"], t, why, 400)
    rec = web_nonces.pop(t, None)
    if not rec:
        return _web_expired()
    guild = bot.get_guild(rec["g"])
    member = guild.get_member(rec["u"]) if guild else None
    if not guild or not member:
        return web_page("<h1>確認できません</h1><p>サーバーに参加しているか確認してください。</p>", 400)
    cfg = store.get(guild.id)
    v = cfg["verify"]
    if not verify_active(cfg):
        return web_page("<h1>認証は現在利用できません</h1>", 400)
    vrole = guild.get_role(v["role"]) if v["role"] else None
    if vrole and vrole in member.roles:
        return web_page("<h1>✅ すでに認証済みです</h1><p>Discordに戻ってください。</p>")

    if v["block_vpn"] or v["block_alt_ip"]:
        try:
            ip = ipaddress.ip_address(ip_s)
        except ValueError:
            ip = None
        if ip is None or ip.is_private or ip.is_loopback or ip.is_link_local:
            log.warning("Web認証: 接続元IPを確認できません(%s)。リバースプロキシ等を挟んでいないか確認してください", ip_s)
            return web_page("<h1>設定エラー</h1><p>接続元を確認できませんでした。管理者に連絡してください。</p>", 500)
        if v["block_vpn"] and vpn_ranges.contains(ip_s):
            v["stats"]["denied"] += 1
            store.save()
            await send_log(guild, make_embed("🛡️ VPN・プロキシの可能性(Web認証を拒否)", f"{member.mention} (`{member.id}`)\n問題なければ `/verify approve` で承認できます。", YELLOW))
            return web_page("<h1>⚠️ 認証できませんでした</h1><p>VPN・プロキシ・データセンターの回線の可能性があります。<br>VPNなどを切ってから、Discordの認証ボタンでやり直してください。</p>", 403)
        if v["block_alt_ip"]:
            h, uid = ip_hash(ip_s), str(member.id)
            users = v["ip_hashes"].get(h, [])
            others = [u for u in users if u != uid]
            log.info("Web認証(同一回線チェック): guild=%s user=%s 同じ回線の別アカウント=%d件 / 記録済みの回線=%d件",
                     guild.id, uid, len(others), len(v["ip_hashes"]))
            if others:
                reason = "同じ回線から別のアカウントが認証済み(サブ垢の疑い)"
                v["stats"]["denied"] += 1
                store.save()
                kick = v["suspect_action"] == "kick"
                await send_log(guild, make_embed("🛡️ " + ("サブ垢の疑いでキック" if kick else "サブ垢の疑い(認証を拒否)"),
                                                 f"{member.mention} (`{member.id}`)\n同じ回線で認証済み: " + " ".join(f"<@{u}>" for u in others[:5])
                                                 + ("" if kick else "\n家族・学校など同じ回線の別人の場合は `/verify approve` で承認できます。"), YELLOW))
                if kick:
                    await kick_for_verify(member, reason)
                    return web_page("<h1>認証できませんでした</h1>", 403)
                await notify_web_verified(rec.get("i"), member,
                                          "🚫 認証を拒否しました。同じ回線から別のアカウントがすでに認証しています。")
                return web_page("<h1>🚫 認証を拒否しました</h1><p>同じ回線から別のアカウントがすでに認証しているため、認証できません。<br>"
                                "心当たりがない場合は、サーバー管理者に連絡してください。</p>", 403)
            if uid not in users:
                v["ip_hashes"].setdefault(h, []).append(uid)
            _cap(v["ip_hashes"], 5000)
            store.save()

    err = await grant_verification(guild, member, "Web認証")
    if err:
        return web_page(f"<h1>認証できませんでした</h1><p>{_esc(err)}</p>", 500)
    await notify_web_verified(rec.get("i"), member)
    return web_page("<h1>✅ 認証が完了しました</h1><p>Discordに戻ってください。</p>")


def is_default_avatar(member: discord.abc.User) -> bool:
    return "/embed/avatars/" in member.display_avatar.url


def _cap(d: dict, n: int) -> None:
    while len(d) > n:
        d.pop(next(iter(d)))


def flag_member(v: dict, user_id: int) -> None:
    v["flagged"][str(user_id)] = int(time.time())
    _cap(v["flagged"], 1000)


def suspect_reasons(member: discord.Member, v: dict) -> list:
    """認証ボタンを押した時点の、疑わしい理由(参加時に記録した理由 + デフォルトアイコン)"""
    reasons = []
    if v["block_default_avatar"] and is_default_avatar(member):
        reasons.append("デフォルトアイコンのまま")
    if r := v["suspects"].get(str(member.id)):
        reasons.append(r)
    return reasons


def detect_join_suspects(member: discord.Member, v: dict) -> list:
    """参加時の判定: 再参加 / 作成時刻が近いアカウントの集団参加。疑わしければ理由を記録して返す。"""
    now, created, uid = time.time(), member.created_at.timestamp(), str(member.id)
    reasons = []
    if v["block_rejoin"] and uid in v["flagged"]:
        reasons.append("認証失敗・未認証でキックされた後の再参加")
    rj = recent_joins[member.guild.id]
    if v["block_cluster"]:
        near = [u for (u, c, j) in rj if now - j < 3600 and abs(c - created) < 600 and u != member.id]
        if len(near) >= 2:
            reasons.append(f"作成時刻が近いアカウントが1時間以内に{len(near) + 1}件参加(サブ垢の疑い)")
            for u in near:
                v["suspects"].setdefault(str(u), "作成時刻が近いアカウントの集団参加(サブ垢の疑い)")
    rj.append((member.id, created, now))
    if reasons:
        v["suspects"][uid] = " / ".join(reasons)
        _cap(v["suspects"], 500)
    return reasons

verify_group = app_commands.Group(
    name="verify", description="メンバー認証の設定・管理",
    default_permissions=discord.Permissions(administrator=True), guild_only=True,
)


def verify_active(cfg: dict) -> bool:
    v = cfg["verify"]
    return bool(v["enabled"] and v["role"])


def verify_effective(guild_id: int):
    v = store.get(guild_id)["verify"]
    raid = raid_until.get(guild_id, 0) > time.time()
    if raid:
        return ("web" if v["mode"] == "web" else "image"), max(v["min_account_days"], RAID_MIN_ACCOUNT_DAYS), True
    return v["mode"], v["min_account_days"], False


def role_problem(interaction: discord.Interaction, role: discord.Role, check_dangerous: bool = False) -> Optional[str]:
    g = interaction.guild
    if role.is_default():
        return "@everyone は指定できません。"
    if role.managed:
        return "BOT/連携が管理しているロールは指定できません。"
    if role >= g.me.top_role:
        return "BOTのロールより上位(または同位)のロールです。サーバー設定でBOTのロールを上に移動してください。"
    if interaction.user.id != g.owner_id and role >= interaction.user.top_role:
        return "あなたと同位以上のロールは指定できません。"
    if check_dangerous:
        bad = [n for n in DANGEROUS_PERMS if getattr(role.permissions, n)]
        if bad:
            return "認証ロールに危険な権限が含まれています(誰でも認証すれば取得できるため): " + ", ".join(bad)
    return None


async def _eph(interaction: discord.Interaction, text: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


def gen_math():
    op = secrets.choice(("+", "-", "×"))
    if op == "×":
        a, b = secrets.randbelow(8) + 2, secrets.randbelow(8) + 2
        return f"{a} × {b} = ?", str(a * b)
    a, b = secrets.randbelow(40) + 10, secrets.randbelow(9) + 1
    if op == "-":
        return f"{a} - {b} = ?", str(a - b)
    return f"{a} + {b} = ?", str(a + b)


def render_captcha(code: str, font_path: Optional[str]) -> io.BytesIO:
    rnd = random.SystemRandom()
    W, H = 340, 120
    img = Image.new("RGB", (W, H), (rnd.randint(215, 245), rnd.randint(215, 245), rnd.randint(215, 245)))
    try:
        font = ImageFont.truetype(font_path, 64) if font_path else ImageFont.load_default(size=64)
    except Exception:
        font = ImageFont.load_default()

    def noise_lines(n: int):
        d = ImageDraw.Draw(img)
        for _ in range(n):
            d.line([(rnd.randint(0, W), rnd.randint(0, H)), (rnd.randint(0, W), rnd.randint(0, H))],
                   fill=(rnd.randint(60, 190), rnd.randint(60, 190), rnd.randint(60, 190)), width=rnd.randint(1, 3))

    noise_lines(5)
    step = (W - 40) / len(code)
    for i, ch in enumerate(code):
        layer = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        color = (rnd.randint(0, 110), rnd.randint(0, 110), rnd.randint(0, 110), 255)
        try:
            d.text((48, 48), ch, font=font, fill=color, anchor="mm")
        except ValueError:
            d.text((24, 24), ch, font=font, fill=color)
        layer = layer.rotate(rnd.uniform(-30, 30), resample=Image.Resampling.BICUBIC)
        x = int(20 + step * i + step / 2 - 48 + rnd.randint(-4, 4))
        y = int(H / 2 - 48 + rnd.randint(-8, 8))
        img.paste(layer, (x, y), layer)
    noise_lines(4)
    d = ImageDraw.Draw(img)
    for _ in range(260):
        d.point((rnd.randint(0, W - 1), rnd.randint(0, H - 1)), fill=(rnd.randint(0, 160),) * 3)
    img = img.filter(ImageFilter.SMOOTH)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


def register_fail(key) -> int:
    now = time.time()
    rec = verify_fails.get(key)
    if not rec or now - rec[1] > 900:
        rec = [0, now]
    rec[0] += 1
    verify_fails[key] = rec
    return rec[0]


async def kick_for_verify(member: discord.Member, reason: str) -> bool:
    if member.guild_permissions.administrator:
        return False
    await try_dm(member, f"**{member.guild.name}** の認証に失敗したためキックされました。\n理由: {reason}\n再参加後にもう一度お試しください。")
    try:
        await member.kick(reason=f"[AZQ BOT 認証] {reason}")
    except discord.HTTPException:
        return False
    store.get(member.guild.id)["verify"]["stats"]["kicked"] += 1
    store.get(member.guild.id)["verify"]["pending"].pop(str(member.id), None)
    flag_member(store.get(member.guild.id)["verify"], member.id)
    store.save()
    return True


async def grant_verification(guild: discord.Guild, member: discord.Member, method: str) -> Optional[str]:
    v = store.get(guild.id)["verify"]
    role = guild.get_role(v["role"]) if v["role"] else None
    if not role:
        return "⚠️ 認証ロールが見つかりません。管理者に連絡してください。"
    try:
        await member.add_roles(role, reason=f"AZQ BOT 認証({method})")
        ur = guild.get_role(v["unverified_role"]) if v["unverified_role"] else None
        if ur and ur in member.roles:
            await member.remove_roles(ur, reason="AZQ BOT 認証完了")
    except discord.HTTPException:
        log.warning("認証ロールの付与に失敗 guild=%s member=%s", guild.id, member.id, exc_info=True)
        return "⚠️ ロールの付与に失敗しました。BOTの権限・ロール順位の確認を管理者に依頼してください。"
    key = (guild.id, member.id)
    verify_fails.pop(key, None)
    verify_lock.pop(key, None)
    verify_challenges.pop(key, None)
    verify_issued.pop(key, None)
    suspect_notified.discard(key)
    v["suspects"].pop(str(member.id), None)
    v["pending"].pop(str(member.id), None)
    v["stats"]["verified"] += 1
    store.save()
    await apply_autorole(member)
    await send_log(guild, make_embed("✅ 認証完了", f"{member.mention} (`{member.id}`)\n方式: {method}", GREEN))
    return None


async def check_answer(interaction: discord.Interaction, given: str) -> None:
    await interaction.response.defer(ephemeral=True)
    guild, member = interaction.guild, interaction.user
    if guild is None or not isinstance(member, discord.Member):
        return
    v = store.get(guild.id)["verify"]
    role = guild.get_role(v["role"]) if v["role"] else None
    if not v["enabled"] or not role:
        return await interaction.followup.send("⚠️ 認証は現在無効です。", ephemeral=True)
    if role in member.roles:
        return await interaction.followup.send("✅ すでに認証済みです。", ephemeral=True)
    key, now = (guild.id, member.id), time.time()
    if verify_lock.get(key, 0) > now:
        return await interaction.followup.send(f"🚫 制限中です。<t:{int(verify_lock[key])}:R> に再試行できます。", ephemeral=True)
    chall = verify_challenges.pop(key, None)
    if not chall or chall[1] < now:
        return await interaction.followup.send("⌛ 問題の有効期限が切れました。パネルのボタンをもう一度押してください。", ephemeral=True)
    answer = re.sub(r"\s+", "", given).upper()
    issued = verify_issued.pop(key, None)
    too_fast = bool(v["bot_check"] and issued is not None
                    and now - issued < SOLVE_MIN_SECONDS["math" if chall[0].isdigit() else "image"])
    if too_fast:
        log.info("認証の回答が早すぎるため失敗扱い guild=%s member=%s (%.1f秒)", guild.id, member.id, now - issued)
    if not too_fast and secrets.compare_digest(answer.encode(), chall[0].encode()):
        err = await grant_verification(guild, member, "計算" if chall[0].isdigit() else "CAPTCHA")
        return await interaction.followup.send(err or "✅ 認証が完了しました!ようこそ!", ephemeral=True)

    count = register_fail(key)
    left = v["max_attempts"] - count
    v["stats"]["failed"] += 1
    if left > 0:
        store.save()
        return await interaction.followup.send(f"❌ 答えが違います。(あと {left} 回)\nパネルのボタンを押すと新しい問題が出ます。", ephemeral=True)
    verify_fails.pop(key, None)
    verify_lock[key] = now + v["lockout_minutes"] * 60
    store.save()
    await send_log(guild, make_embed("🚫 認証失敗(上限到達)",
                                     f"{member.mention} (`{member.id}`)\n{v['max_attempts']}回失敗 → {v['lockout_minutes']}分ロック"
                                     + ("+キック" if v["violation"] == "kick" else ""), RED))
    if v["violation"] == "kick":
        await interaction.followup.send("🚫 失敗が上限に達したためキックします。", ephemeral=True)
        await kick_for_verify(member, f"認証に{v['max_attempts']}回失敗")
    else:
        await interaction.followup.send(f"🚫 失敗が上限に達しました。{v['lockout_minutes']}分後に再試行できます。", ephemeral=True)


class AnswerModal(discord.ui.Modal):
    def __init__(self, label: str):
        super().__init__(title="メンバー認証", timeout=CHALLENGE_TTL)
        self.answer = discord.ui.TextInput(label=label[:45], placeholder="答えを入力", min_length=1, max_length=12)
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        await check_answer(interaction, self.answer.value)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.exception("認証モーダルでエラー", exc_info=error)
        await _eph(interaction, "⚠️ エラーが発生しました。もう一度お試しください。")


class CaptchaEntryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=CHALLENGE_TTL)

    @discord.ui.button(label="コードを入力", emoji="⌨️", style=discord.ButtonStyle.primary)
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AnswerModal("画像の文字を入力"))


async def verify_click(interaction: discord.Interaction) -> None:
    guild, member = interaction.guild, interaction.user
    if guild is None or not isinstance(member, discord.Member):
        return await _eph(interaction, "❌ サーバー内で使ってください。")
    v = store.get(guild.id)["verify"]
    role = guild.get_role(v["role"]) if v["role"] else None
    if not v["enabled"] or not role:
        return await _eph(interaction, "⚠️ 認証は現在無効です。管理者に連絡してください。")
    if role in member.roles:
        return await _eph(interaction, "✅ すでに認証済みです。")
    key, now = (guild.id, member.id), time.time()
    if verify_lock.get(key, 0) > now:
        return await _eph(interaction, f"🚫 失敗が続いたため制限中です。<t:{int(verify_lock[key])}:R> に再試行できます。")
    if now - verify_last.get(key, 0) < 3:
        return await _eph(interaction, "⏳ 少し待ってからもう一度押してください。")
    verify_last[key] = now

    mode, min_days, raid = verify_effective(guild.id)
    age_days = (discord.utils.utcnow() - member.created_at).total_seconds() / 86400
    if age_days < min_days:
        v["stats"]["denied"] += 1
        store.save()
        await _eph(interaction, f"🚫 アカウント作成から **{min_days}日以上** 経過していないと認証できません。(現在 {age_days:.1f}日)"
                   + ("\n※レイド警戒中のため一時的に強化されています。" if raid else ""))
        await send_log(guild, make_embed("🚫 認証拒否(新規アカウント)",
                                         f"{member.mention} (`{member.id}`)\nアカウント作成から {age_days:.1f}日 (必要: {min_days}日)", YELLOW))
        if v["violation"] == "kick":
            await kick_for_verify(member, f"アカウント作成から{min_days}日未満")
        return

    reasons = suspect_reasons(member, v)
    if reasons:
        v["stats"]["denied"] += 1
        store.save()
        txt, kick = " / ".join(reasons), v["suspect_action"] == "kick"
        if key not in suspect_notified:
            suspect_notified.add(key)
            await send_log(guild, make_embed("🛡️ 疑わしいアカウントをキック" if kick else "🛡️ 疑わしいアカウントの認証を保留",
                                             f"{member.mention} (`{member.id}`)\n理由: {txt}"
                                             + ("" if kick else "\n問題なければ `/verify approve` で承認できます。"), YELLOW))
        if kick:
            await _eph(interaction, "🚫 このアカウントは疑わしいと判断されたため、認証できません。")
            await kick_for_verify(member, f"疑わしいアカウント: {txt}")
        else:
            await _eph(interaction, "🛡️ アカウントの確認が必要なため、サーバー管理者の承認待ちです。しばらくお待ちください。")
        return

    if mode == "web":
        if not WEB_READY:
            return await _eph(interaction, "⚠️ Web認証の準備ができていません。管理者に連絡してください。")
        try:
            view = discord.ui.View(timeout=WEB_TTL)
            view.add_item(discord.ui.Button(label="Webで認証する", emoji="🌐", style=discord.ButtonStyle.link,
                                            url=make_web_link(guild.id, member.id, interaction)))
            return await interaction.response.send_message(
                "🌐 下のボタンを開いて、ページの指示に従ってください。\n(10分間有効・あなた専用のリンクです。他の人に共有しないでください)",
                view=view, ephemeral=True)
        except discord.HTTPException:
            log.exception("Web認証リンクの送信に失敗しました (WEB_URL=%s)", WEB_URL)
            return await _eph(interaction, "⚠️ 認証リンクを作れませんでした。管理者に連絡してください。")

    note = ""
    if v["bot_check"] and mode != "image":
        if age_days < 7 or is_default_avatar(member):
            mode, note = "image", "\n🛡️ アカウントの確認のため、画像認証になりました。"
        elif mode == "button":
            mode = "math"

    if mode == "button":
        await interaction.response.defer(ephemeral=True)
        err = await grant_verification(guild, member, "ボタン")
        return await interaction.followup.send(err or "✅ 認証が完了しました!ようこそ!", ephemeral=True)
    if mode == "math":
        question, answer = gen_math()
        verify_challenges[key] = (answer, now + CHALLENGE_TTL)
        verify_issued[key] = now
        return await interaction.response.send_modal(AnswerModal(question))

    await interaction.response.defer(ephemeral=True)
    code = "".join(secrets.choice(CAPTCHA_CHARS) for _ in range(5))
    try:
        font_path = await ensure_font()
    except Exception:
        font_path = None
    buf = await run_heavy(render_captcha, code, font_path, pool=CAPTCHA_POOL)
    verify_challenges[key] = (code, now + CHALLENGE_TTL)
    verify_issued[key] = now
    await interaction.followup.send(
        "🔐 画像の文字を入力してください。(大文字小文字は区別しません / 3分以内)" + ("\n⚠️ レイド警戒中のため画像認証です。" if raid else "") + note,
        file=discord.File(buf, filename="captcha.png"), view=CaptchaEntryView(), ephemeral=True)


class VerifyPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="認証する", emoji="✅", style=discord.ButtonStyle.success, custom_id="azq:verify:start")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await verify_click(interaction)


def panel_embed(v: dict) -> discord.Embed:
    e = make_embed(v["panel_title"], v["panel_text"], GREEN)
    e.set_footer(text=f"認証方式: {VERIFY_MODES.get(v['mode'], v['mode'])}")
    return e


async def delete_panel(guild: discord.Guild) -> None:
    v = store.get(guild.id)["verify"]
    ch = guild.get_channel(v["panel_channel"]) if v["panel_channel"] else None
    if ch and v["panel_message"]:
        try:
            await (await ch.fetch_message(v["panel_message"])).delete()
        except discord.HTTPException:
            pass
    v["panel_channel"] = v["panel_message"] = None


def verify_view(v: dict) -> "VerifyPanelView":
    view = VerifyPanelView()
    view.start.label = (v.get("panel_button") or "認証する")[:80]
    return view


async def post_panel(guild: discord.Guild, channel: discord.TextChannel) -> discord.Message:
    await delete_panel(guild)
    v = store.get(guild.id)["verify"]
    msg = await channel.send(embed=panel_embed(v), view=verify_view(v))
    v["panel_channel"], v["panel_message"] = channel.id, msg.id
    store.save()
    return msg


async def refresh_panel(guild: discord.Guild) -> bool:
    """設置済みの認証パネルを現在の設定で更新する。更新できたら True"""
    v = store.get(guild.id)["verify"]
    ch = guild.get_channel(v["panel_channel"]) if v["panel_channel"] else None
    if ch and v["panel_message"]:
        try:
            await (await ch.fetch_message(v["panel_message"])).edit(embed=panel_embed(v), view=verify_view(v))
            return True
        except discord.HTTPException:
            pass
    return False


class VerifyTextModal(discord.ui.Modal, title="認証パネルの文面を編集"):
    def __init__(self, v: dict):
        super().__init__()
        self.t = discord.ui.TextInput(label="タイトル", default=v["panel_title"][:100], max_length=100)
        self.d = discord.ui.TextInput(label="説明文", style=discord.TextStyle.paragraph, default=v["panel_text"][:1500], max_length=1500)
        self.b = discord.ui.TextInput(label="ボタンの名前", default=(v.get("panel_button") or "認証する")[:30], max_length=30)
        for item in (self.t, self.d, self.b):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        v = store.get(interaction.guild.id)["verify"]
        v["panel_title"], v["panel_text"], v["panel_button"] = self.t.value.strip(), self.d.value.strip(), self.b.value.strip()
        store.save()
        await interaction.response.defer(ephemeral=True)
        ok = await refresh_panel(interaction.guild)
        await interaction.followup.send("✅ 認証パネルの文面を更新しました。" if ok else
                                        "✅ 保存しました。パネルを設置する(`/verify setup` / `/verify panel`)と反映されます。", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.exception("認証パネルの文面編集でエラー", exc_info=error)
        await _eph(interaction, "⚠️ 更新に失敗しました。もう一度お試しください。")


@tasks.loop(minutes=1)
async def verify_watch():
    now = time.time()
    for k in [k for k, t in verify_issued.items() if now - t > CHALLENGE_TTL * 2]:
        verify_issued.pop(k, None)
    for guild in list(bot.guilds):
        if guild.unavailable:
            continue
        v = store.get(guild.id)["verify"]
        if not v["pending"]:
            continue
        role = guild.get_role(v["role"]) if v["role"] else None
        changed = False
        for uid, ts in list(v["pending"].items()):
            member = guild.get_member(int(uid))
            if member is None or not v["enabled"] or (role and role in member.roles):
                v["pending"].pop(uid, None)
                changed = True
                continue
            if v["kick_minutes"] and now - ts >= v["kick_minutes"] * 60:
                v["pending"].pop(uid, None)
                changed = True
                if member.guild_permissions.administrator:
                    continue
                await try_dm(member, f"**{guild.name}** で {v['kick_minutes']}分以内に認証が完了しなかったためキックされました。\n再参加後、認証パネルから認証してください。")
                try:
                    await member.kick(reason=f"[AZQ BOT 認証] {v['kick_minutes']}分以内に未認証")
                    v["stats"]["kicked"] += 1
                    flag_member(v, member.id)
                    await send_log(guild, make_embed("⏰ 未認証キック", f"{member} (`{member.id}`)\n{v['kick_minutes']}分以内に認証されませんでした。", YELLOW))
                except discord.HTTPException:
                    log.warning("未認証キックに失敗 guild=%s member=%s", guild.id, uid)
        if changed:
            store.save()


@verify_watch.before_loop
async def _before_verify_watch():
    await bot.wait_until_ready()
    await asyncio.sleep(20)


@verify_group.command(name="setup", description="認証パネルを設置して認証機能を有効化します")
@app_commands.describe(
    channel="認証パネルを置くチャンネル", role="認証後に付与するロール",
    mode="認証方式(省略時は現在の設定 / 初期はボタン)",
    unverified_role="参加直後に付与し、認証後に外すロール(任意)",
    min_account_days="アカウント作成からの最低日数(0=制限なし)",
)
@app_commands.choices(mode=MODE_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def verify_setup(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role,
                       mode: Optional[app_commands.Choice[str]] = None, unverified_role: Optional[discord.Role] = None,
                       min_account_days: Optional[app_commands.Range[int, 0, 365]] = None):
    if p := role_problem(interaction, role, check_dangerous=True):
        return await interaction.response.send_message(f"❌ 認証ロール: {p}", ephemeral=True)
    if unverified_role:
        if unverified_role.id == role.id:
            return await interaction.response.send_message("❌ 認証ロールと未認証ロールは別のロールにしてください。", ephemeral=True)
        if p := role_problem(interaction, unverified_role):
            return await interaction.response.send_message(f"❌ 未認証ロール: {p}", ephemeral=True)
    perms = channel.permissions_for(interaction.guild.me)
    if not (perms.view_channel and perms.send_messages and perms.embed_links):
        return await interaction.response.send_message(f"❌ BOTが {channel.mention} で「チャンネルを見る・メッセージを送信・埋め込みリンク」を行えません。", ephemeral=True)
    if mode and mode.value == "web" and not WEB_READY:
        return await interaction.response.send_message("❌ Web認証は、まだ準備ができていません。BOTの環境変数 `WEB_URL` を設定してください。(手順は README を参照)", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    v = store.get(interaction.guild.id)["verify"]
    v.update(enabled=True, role=role.id, unverified_role=unverified_role.id if unverified_role else None)
    if mode:
        v["mode"] = mode.value
    if min_account_days is not None:
        v["min_account_days"] = min_account_days
    try:
        await post_panel(interaction.guild, channel)
    except discord.HTTPException:
        v["enabled"] = False
        store.save()
        return await interaction.followup.send("❌ パネルを送信できませんでした。BOTの権限を確認してください。", ephemeral=True)
    store.save()
    me = interaction.guild.me.guild_permissions
    notes = []
    if not me.manage_roles:
        notes.append("⚠️ BOTに「ロールの管理」権限がありません。このままでは認証ロールを付与できません。")
    if v["kick_minutes"] and not me.kick_members:
        notes.append("⚠️ BOTに「メンバーをキック」権限がありません。未認証キックは動作しません。")
    await interaction.followup.send(
        f"✅ 認証を有効化しました。\n方式: **{VERIFY_MODES[v['mode']]}** / 認証ロール: {role.mention}"
        f"{' / 未認証ロール: ' + unverified_role.mention if unverified_role else ''} / 最低アカウント年齢: {v['min_account_days']}日\n\n"
        "**最後にチャンネル権限を設定してください:**\n"
        f"1. `@everyone` は {channel.mention} 以外を「チャンネルを見る」不可にする\n"
        f"2. {role.mention} に通常チャンネルの閲覧・発言権限を付ける\n"
        "3. 既存メンバーを認証済みにするには `/verify bulk_approve` を使います\n"
        + ("\n".join(notes)),
        ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


@verify_group.command(name="set", description="認証の詳細設定を変更します(指定した項目のみ変更)")
@app_commands.describe(
    mode="認証方式", min_account_days="アカウント作成からの最低日数(0=制限なし)",
    kick_minutes="この分数以内に認証しないとキック(0=キックしない)",
    max_attempts="連続で間違えてよい回数", lockout_minutes="上限到達後のロック時間(分)",
    violation="新規アカウント/失敗上限に達した人への処置",
    bot_check="ロボット確認を強化(早すぎる回答は失敗/ボタン方式は計算に/疑わしい新規アカウントは画像認証に)",
    block_default_avatar="デフォルトアイコンのままのアカウントを自動では通さない",
    block_rejoin="認証失敗・未認証でキックされた人の再参加を自動では通さない",
    block_cluster="作成時刻が近いアカウントが短時間に複数参加(サブ垢の疑い)したら自動では通さない",
    suspect_action="疑わしいアカウントへの処置",
    block_vpn="Web認証で、VPN・プロキシ・データセンターの回線から認証させない",
    block_alt_ip="Web認証で、同じ回線から別アカウントが認証済みなら承認待ちにする(サブ垢対策)",
)
@app_commands.choices(mode=MODE_CHOICES, violation=VIOLATION_CHOICES, suspect_action=SUSPECT_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def verify_set(interaction: discord.Interaction, mode: Optional[app_commands.Choice[str]] = None,
                     min_account_days: Optional[app_commands.Range[int, 0, 365]] = None,
                     kick_minutes: Optional[app_commands.Range[int, 0, 1440]] = None,
                     max_attempts: Optional[app_commands.Range[int, 1, 10]] = None,
                     lockout_minutes: Optional[app_commands.Range[int, 1, 1440]] = None,
                     violation: Optional[app_commands.Choice[str]] = None, bot_check: Optional[bool] = None,
                     block_default_avatar: Optional[bool] = None, block_rejoin: Optional[bool] = None,
                     block_cluster: Optional[bool] = None, suspect_action: Optional[app_commands.Choice[str]] = None,
                     block_vpn: Optional[bool] = None, block_alt_ip: Optional[bool] = None):
    v = store.get(interaction.guild.id)["verify"]
    changed = []
    if not WEB_READY and ((mode and mode.value == "web") or block_vpn or block_alt_ip):
        return await interaction.response.send_message("❌ Web認証は、まだ準備ができていません。BOTの環境変数 `WEB_URL` を設定してください。(手順は README を参照)", ephemeral=True)
    for key, val in (("mode", mode.value if mode else None), ("min_account_days", min_account_days),
                     ("kick_minutes", kick_minutes), ("max_attempts", max_attempts),
                     ("lockout_minutes", lockout_minutes), ("violation", violation.value if violation else None),
                     ("bot_check", bot_check), ("block_default_avatar", block_default_avatar), ("block_rejoin", block_rejoin),
                     ("block_cluster", block_cluster), ("suspect_action", suspect_action.value if suspect_action else None),
                     ("block_vpn", block_vpn), ("block_alt_ip", block_alt_ip)):
        if val is not None:
            v[key] = val
            changed.append(f"`{key}` = `{val}`")
    if not changed:
        return await interaction.response.send_message("変更する項目を指定してください。", ephemeral=True)
    store.save()
    note = "\n⚠️ VPN・同一回線の判定は、認証方式が「Web認証」のときに働きます。(`mode:Web認証`)" if (block_vpn or block_alt_ip) and v["mode"] != "web" else ""
    await interaction.response.send_message("✅ 更新しました:\n" + "\n".join(changed) + note, ephemeral=True)
    if mode:
        await refresh_panel(interaction.guild)


@verify_group.command(name="clearips", description="サブ垢検出のために保存している、IPのハッシュをすべて削除します")
@app_commands.checks.has_permissions(administrator=True)
async def verify_clearips(interaction: discord.Interaction):
    v = store.get(interaction.guild.id)["verify"]
    n = len(v["ip_hashes"])
    v["ip_hashes"] = {}
    store.save()
    await interaction.response.send_message(f"✅ 保存していたIPのハッシュ({n}件)を削除しました。", ephemeral=True)


@verify_group.command(name="panel", description="認証パネルを再設置/文面を変更します")
@app_commands.describe(channel="省略すると現在のパネルのチャンネル", title="パネルのタイトル", text="パネルの説明文(改行は \\n)")
@app_commands.checks.has_permissions(administrator=True)
async def verify_panel(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None,
                       title: Optional[app_commands.Range[str, 1, 100]] = None, text: Optional[app_commands.Range[str, 1, 1500]] = None):
    v = store.get(interaction.guild.id)["verify"]
    target = channel or (interaction.guild.get_channel(v["panel_channel"]) if v["panel_channel"] else None)
    if not target:
        return await interaction.response.send_message("❌ channel を指定してください(まず /verify setup を実行してください)。", ephemeral=True)
    perms = target.permissions_for(interaction.guild.me)
    if not (perms.view_channel and perms.send_messages and perms.embed_links):
        return await interaction.response.send_message("❌ BOTがそのチャンネルに送信できません。", ephemeral=True)
    if title:
        v["panel_title"] = title
    if text:
        v["panel_text"] = text.replace("\\n", "\n")
    await interaction.response.defer(ephemeral=True)
    try:
        await post_panel(interaction.guild, target)
    except discord.HTTPException:
        return await interaction.followup.send("❌ パネルを送信できませんでした。", ephemeral=True)
    await interaction.followup.send(f"✅ {target.mention} にパネルを設置しました。", ephemeral=True)


@verify_group.command(name="text", description="認証パネルの文面(タイトル・説明・ボタン名)を入力フォームで編集します")
@app_commands.checks.has_permissions(administrator=True)
async def verify_text(interaction: discord.Interaction):
    await interaction.response.send_modal(VerifyTextModal(store.get(interaction.guild.id)["verify"]))


@verify_group.command(name="status", description="認証機能の状態を表示します")
@app_commands.checks.has_permissions(administrator=True)
async def verify_status(interaction: discord.Interaction):
    g = interaction.guild
    v = store.get(g.id)["verify"]
    mode, days, raid = verify_effective(g.id)
    e = make_embed("🔐 認証の状態", color=GREEN if verify_active(store.get(g.id)) else GRAY)
    e.add_field(name="状態", value="ON" if v["enabled"] else "OFF")
    e.add_field(name="方式", value=VERIFY_MODES[v["mode"]])
    e.add_field(name="認証ロール", value=f"<@&{v['role']}>" if v["role"] else "未設定")
    e.add_field(name="未認証ロール", value=f"<@&{v['unverified_role']}>" if v["unverified_role"] else "なし")
    e.add_field(name="最低アカウント年齢", value=f"{v['min_account_days']}日")
    e.add_field(name="未認証キック", value=f"{v['kick_minutes']}分" if v["kick_minutes"] else "なし")
    e.add_field(name="失敗上限", value=f"{v['max_attempts']}回 → {v['lockout_minutes']}分ロック / {VIOLATION_MODES[v['violation']]}")
    onoff = lambda b: "ON" if b else "OFF"
    e.add_field(name="Web認証", value=("準備OK" if WEB_READY else "未設定(WEB_URL)") + f" / reCAPTCHA {'ON' if RECAPTCHA_READY else 'OFF(RECAPTCHA_SITE_KEY / RECAPTCHA_SECRET_KEY 未設定)'} / VPN判定 {onoff(v['block_vpn'])}(リスト{len(vpn_ranges.starts)}件) / 同一回線の判定 {onoff(v['block_alt_ip'])}", inline=False)
    e.add_field(name="ロボット確認の強化", value=onoff(v["bot_check"]))
    e.add_field(name="疑わしいアカウント対策", value=(f"デフォルトアイコン {onoff(v['block_default_avatar'])} / 再参加 {onoff(v['block_rejoin'])} / 集団参加 {onoff(v['block_cluster'])}\n"
                                                      f"処置: {'キック' if v['suspect_action'] == 'kick' else '管理者の承認待ち'}"), inline=False)
    e.add_field(name="レイド警戒", value=f"🚨 発動中 (<t:{int(raid_until[g.id])}:R> まで: {VERIFY_MODES[mode]}/{days}日以上)" if raid else "なし")
    s = v["stats"]
    e.add_field(name="累計", value=f"認証 {s['verified']} / 失敗 {s['failed']} / 拒否 {s['denied']} / キック {s['kicked']}", inline=False)
    if v["pending"]:
        now = time.time()
        lines = [f"<@{uid}> ({int((now - ts) // 60)}分前)" for uid, ts in sorted(v["pending"].items(), key=lambda kv: kv[1])[:15]]
        e.add_field(name=f"認証待ち ({len(v['pending'])}人)", value="\n".join(lines), inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


@verify_group.command(name="approve", description="メンバーを手動で認証済みにします")
@app_commands.checks.has_permissions(administrator=True)
async def verify_approve(interaction: discord.Interaction, member: discord.Member):
    v = store.get(interaction.guild.id)["verify"]
    if not v["role"]:
        return await interaction.response.send_message("❌ 認証が未設定です(/verify setup)。", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    err = await grant_verification(interaction.guild, member, f"手動承認 by {interaction.user}")
    await interaction.followup.send(err or f"✅ {member.mention} を認証済みにしました。", ephemeral=True,
                                    allowed_mentions=discord.AllowedMentions.none())


@verify_group.command(name="revoke", description="メンバーの認証を取り消して未認証に戻します")
@app_commands.checks.has_permissions(administrator=True)
async def verify_revoke(interaction: discord.Interaction, member: discord.Member):
    if err := hierarchy_error(interaction, member):
        return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
    g = interaction.guild
    v = store.get(g.id)["verify"]
    role = g.get_role(v["role"]) if v["role"] else None
    if not role:
        return await interaction.response.send_message("❌ 認証が未設定です。", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    try:
        if role in member.roles:
            await member.remove_roles(role, reason=f"認証取り消し by {interaction.user}")
        ur = g.get_role(v["unverified_role"]) if v["unverified_role"] else None
        if ur:
            await member.add_roles(ur, reason="認証取り消し")
    except discord.HTTPException:
        return await interaction.followup.send("❌ ロールの操作に失敗しました。BOTの権限/ロール順位を確認してください。", ephemeral=True)
    verify_fails.pop((g.id, member.id), None)
    verify_lock.pop((g.id, member.id), None)
    v["pending"][str(member.id)] = int(time.time())
    store.save()
    await send_log(g, make_embed("↩️ 認証取り消し", f"{member} (`{member.id}`)\n実行者: {interaction.user}", YELLOW))
    await interaction.followup.send(f"↩️ {member.mention} の認証を取り消しました。", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


@verify_group.command(name="bulk_approve", description="既存メンバー全員(認証待ちの人を除く)を認証済みにします")
@app_commands.describe(confirm="実行する場合は True")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.cooldown(1, 300, key=lambda i: i.guild_id)
async def verify_bulk(interaction: discord.Interaction, confirm: bool):
    g = interaction.guild
    v = store.get(g.id)["verify"]
    role = g.get_role(v["role"]) if v["role"] else None
    if not role:
        return await interaction.response.send_message("❌ 認証が未設定です(/verify setup)。", ephemeral=True)
    if not confirm:
        return await interaction.response.send_message("⚠️ 認証待ち以外の全メンバーに認証ロールを付与します。実行するなら `confirm: True` にしてください。", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    targets = [m for m in g.members if not m.bot and role not in m.roles
               and str(m.id) not in v["pending"] and not (v["unverified_role"] and any(r.id == v["unverified_role"] for r in m.roles))]
    cap, done, failed = 1500, 0, 0
    for m in targets[:cap]:
        try:
            await m.add_roles(role, reason=f"AZQ BOT 一括認証 by {interaction.user}")
            done += 1
        except discord.HTTPException:
            failed += 1
    await send_log(g, make_embed("✅ 一括認証", f"{done}人に付与 / 失敗 {failed}人\n実行者: {interaction.user}", GREEN))
    await interaction.followup.send(f"✅ {done}人に {role.mention} を付与しました(失敗 {failed}人)。"
                                    + (f"\n対象が多いため先頭{cap}人までです。もう一度実行してください。" if len(targets) > cap else ""),
                                    ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


@verify_group.command(name="raid", description="レイド警戒モード(画像認証+アカウント年齢制限)を手動で切り替えます")
@app_commands.describe(enabled="ON/OFF", minutes="ONの場合の持続時間(分)")
@app_commands.checks.has_permissions(administrator=True)
async def verify_raid(interaction: discord.Interaction, enabled: bool, minutes: app_commands.Range[int, 1, 1440] = 30):
    if enabled:
        raid_until[interaction.guild.id] = time.time() + minutes * 60
        msg = f"🚨 レイド警戒モードを {minutes}分間 ON にしました。(画像認証 + アカウント作成{RAID_MIN_ACCOUNT_DAYS}日以上)"
    else:
        raid_until.pop(interaction.guild.id, None)
        msg = "✅ レイド警戒モードを OFF にしました。"
    await interaction.response.send_message(msg, ephemeral=True)
    await send_log(interaction.guild, make_embed("🚨 レイド警戒モード", f"{'ON' if enabled else 'OFF'} / 実行者: {interaction.user}", YELLOW if enabled else GREEN))


@verify_group.command(name="disable", description="認証機能を無効化し、パネルを削除します")
@app_commands.checks.has_permissions(administrator=True)
async def verify_disable(interaction: discord.Interaction):
    g = interaction.guild
    v = store.get(g.id)["verify"]
    await interaction.response.defer(ephemeral=True)
    v["enabled"] = False
    v["pending"] = {}
    await delete_panel(g)
    store.save()
    await interaction.followup.send("✅ 認証を無効化しました。\n※未認証ロールを使っていた場合、付与済みの人のロールは手動で外してください。", ephemeral=True)


JST = timezone(timedelta(hours=9))
TICKET_COOLDOWN = 30
ticket_last: dict = {}

ticket_group = app_commands.Group(
    name="ticket", description="チケットの操作(チケットチャンネル内で使います)", guild_only=True,
)
ticketconfig_group = app_commands.Group(
    name="ticketconfig", description="チケット機能の設定",
    default_permissions=discord.Permissions(administrator=True), guild_only=True,
)

TICKET_MEMBER_PERMS = dict(view_channel=True, send_messages=True, read_message_history=True,
                           attach_files=True, embed_links=True)


def ticket_is_staff(member: discord.Member, tc: dict) -> bool:
    return member.guild_permissions.administrator or any(r.id in tc["staff_roles"] for r in member.roles)


def ticket_open_of(guild: discord.Guild, tc: dict, uid: int) -> list:
    res = []
    for cid, info in list(tc["open"].items()):
        ch = guild.get_channel(int(cid))
        if ch is None:
            tc["open"].pop(cid, None)
        elif info["owner"] == uid and not info.get("closed"):
            res.append(ch)
    return res


async def build_transcript(channel: discord.TextChannel, info: dict) -> bytes:
    lines = [
        f"# チケット #{info['number']:04d} / {channel.guild.name}",
        f"# 件名: {info.get('subject', '')}",
        f"# 作成者ID: {info['owner']}",
        f"# 作成: {datetime.fromtimestamp(info['created'], JST):%Y-%m-%d %H:%M:%S} JST",
        "",
    ]
    async for m in channel.history(limit=2000, oldest_first=True):
        ts = m.created_at.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"[{ts}] {m.author} ({m.author.id}): " + m.clean_content.replace("\n", "\n    "))
        for a in m.attachments:
            lines.append(f"    [添付] {a.filename} {a.url}")
        for em in m.embeds:
            t = " ".join(x for x in (em.title, em.description) if x)
            if t:
                lines.append(f"    [埋め込み] {t[:300]}")
    return "\n".join(lines).encode("utf-8")[:7_000_000]


async def lock_ticket_channel(channel: discord.TextChannel) -> None:
    guild = channel.guild
    for target, ow in list(channel.overwrites.items()):
        if target.id in (guild.id, guild.me.id):
            continue
        ow.send_messages = False
        ow.attach_files = False
        try:
            await channel.set_permissions(target, overwrite=ow, reason="チケットクローズ")
        except discord.HTTPException:
            log.warning("チケットのロックに失敗 guild=%s channel=%s", guild.id, channel.id)


async def close_ticket(channel: discord.TextChannel, closer: Optional[discord.Member], reason: Optional[str]) -> bool:
    guild = channel.guild
    cfg = store.get(guild.id)
    tc = cfg["ticket"]
    info = tc["open"].get(str(channel.id))
    if not info or info.get("closed"):
        return False
    info["closed"] = True
    info["closed_by"] = closer.id if closer else None
    info["closed_at"] = int(time.time())
    tc["stats"]["closed"] += 1
    store.save()
    record_ticket_close(guild.id, info, closer, reason)
    await lock_ticket_channel(channel)
    data = None
    try:
        data = await build_transcript(channel, info)
    except discord.HTTPException:
        log.warning("トランスクリプト作成に失敗 guild=%s channel=%s", guild.id, channel.id)
    name = f"ticket-{info['number']:04d}"
    owner = guild.get_member(info["owner"])
    e = make_embed(f"🔒 チケット #{info['number']:04d} クローズ", color=GRAY)
    e.add_field(name="作成者", value=f"<@{info['owner']}>")
    e.add_field(name="件名", value=info.get("subject") or "なし")
    e.add_field(name="担当", value=f"<@{info['claimed_by']}>" if info["claimed_by"] else "なし")
    e.add_field(name="クローズ", value=str(closer) if closer else "自動")
    e.add_field(name="理由", value=reason or "なし", inline=False)
    dest_id = tc["transcript_channel"] or cfg["log_channel"]
    dest = guild.get_channel(dest_id) if dest_id else None
    if dest:
        try:
            if data:
                await dest.send(embed=e, file=discord.File(io.BytesIO(data), filename=f"{name}.txt"))
            else:
                await dest.send(embed=e)
        except discord.HTTPException:
            log.warning("トランスクリプトの送信に失敗 guild=%s", guild.id)
    if data and tc["dm_transcript"] and owner:
        try:
            await owner.send(f"**{guild.name}** のチケット #{info['number']:04d} の記録です。",
                             file=discord.File(io.BytesIO(data), filename=f"{name}.txt"))
        except discord.HTTPException:
            pass
    ce = make_embed(f"🔒 チケット #{info['number']:04d} はクローズされました", color=GRAY)
    ce.description = (f"{closer.mention if closer else '自動処理'} がチケットを閉じました。\n理由: {reason or 'なし'}\n\n"
                      "このチャンネルは閲覧のみになりました。**削除できるのは管理者のみ**です。")
    try:
        await channel.send(embed=ce, view=TicketClosedView(), allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        pass
    return True


async def delete_ticket(channel: discord.TextChannel, deleter: discord.Member) -> bool:
    guild = channel.guild
    tc = store.get(guild.id)["ticket"]
    info = tc["open"].pop(str(channel.id), None)
    if not info:
        return False
    store.save()
    await send_log(guild, make_embed("🗑️ チケット削除",
                                    f"#{info['number']:04d} / 作成者 <@{info['owner']}> / 削除 {deleter} (`{deleter.id}`)", RED))
    try:
        await channel.delete(reason=f"チケット削除: {deleter}")
    except discord.HTTPException:
        log.warning("チケットチャンネルの削除に失敗 guild=%s channel=%s", guild.id, channel.id)
        tc["open"][str(channel.id)] = info
        store.save()
        return False
    return True


async def create_ticket(interaction: discord.Interaction, subject: str, detail: str) -> None:
    await interaction.response.defer(ephemeral=True)
    guild, member = interaction.guild, interaction.user
    cfg = store.get(guild.id)
    tc = cfg["ticket"]
    category = guild.get_channel(tc["category"]) if tc["category"] else None
    if not tc["enabled"] or not isinstance(category, discord.CategoryChannel):
        return await interaction.followup.send("⚠️ チケットは現在利用できません。管理者に連絡してください。", ephemeral=True)
    if member.id in tc["blocked"]:
        return await interaction.followup.send("🚫 あなたはチケットを作成できません。", ephemeral=True)
    mine = ticket_open_of(guild, tc, member.id)
    if len(mine) >= tc["max_open"]:
        return await interaction.followup.send("❌ すでに開いているチケットがあります: " + " ".join(c.mention for c in mine), ephemeral=True)

    staff_roles = [r for r in (guild.get_role(i) for i in tc["staff_roles"]) if r]
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(**TICKET_MEMBER_PERMS),
        guild.me: discord.PermissionOverwrite(**TICKET_MEMBER_PERMS),
    }
    for r in staff_roles:
        overwrites[r] = discord.PermissionOverwrite(**TICKET_MEMBER_PERMS)
    tc["counter"] += 1
    n = tc["counter"]
    try:
        ch = await guild.create_text_channel(
            name=f"ticket-{n:04d}", category=category, overwrites=overwrites,
            topic=f"owner:{member.id} | {subject}"[:1000], reason=f"AZQ BOT チケット作成: {member}")
    except discord.HTTPException:
        log.warning("チケットチャンネル作成に失敗 guild=%s", guild.id, exc_info=True)
        store.save()
        return await interaction.followup.send("❌ チャンネルを作成できませんでした。(カテゴリの上限50個、またはBOTの権限不足の可能性があります)", ephemeral=True)

    tc["open"][str(ch.id)] = {"owner": member.id, "number": n, "created": int(time.time()),
                              "claimed_by": None, "subject": subject[:80]}
    tc["stats"]["created"] += 1
    ticket_last[(guild.id, member.id)] = time.time()
    store.save()

    e = make_embed(f"🎫 チケット #{n:04d}", color=BLUE)
    e.add_field(name="作成者", value=member.mention)
    e.add_field(name="件名", value=subject[:200])
    e.add_field(name="内容", value=detail[:1000] or "(未入力)", inline=False)
    e.set_footer(text="スタッフが対応するまでお待ちください。解決したら「クローズ」を押してください。")
    ping_roles = staff_roles if tc["ping_staff"] else []
    text = member.mention + ("".join(" " + r.mention for r in ping_roles))
    await ch.send(text, embed=e, view=TicketControlView(),
                  allowed_mentions=discord.AllowedMentions(users=[member], roles=ping_roles))
    await send_log(guild, make_embed("🎫 チケット作成", f"{ch.mention} / {member} (`{member.id}`)\n件名: {subject[:100]}", GREEN))
    await interaction.followup.send(f"✅ チケットを作成しました: {ch.mention}", ephemeral=True)


class TicketModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="チケットを作成", timeout=600)
        self.subject = discord.ui.TextInput(label="件名", placeholder="例: 購入について質問 / 違反の報告", min_length=1, max_length=80)
        self.detail = discord.ui.TextInput(label="内容(わかる範囲で詳しく)", style=discord.TextStyle.paragraph,
                                           min_length=1, max_length=1000)
        self.add_item(self.subject)
        self.add_item(self.detail)

    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket(interaction, self.subject.value.strip(), self.detail.value.strip())

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.exception("チケットモーダルでエラー", exc_info=error)
        await _eph(interaction, "⚠️ エラーが発生しました。もう一度お試しください。")


async def ticket_click(interaction: discord.Interaction) -> None:
    guild, member = interaction.guild, interaction.user
    if guild is None or not isinstance(member, discord.Member):
        return await _eph(interaction, "❌ サーバー内で使ってください。")
    cfg = store.get(guild.id)
    tc = cfg["ticket"]
    if not tc["enabled"] or not (tc["category"] and guild.get_channel(tc["category"])):
        return await _eph(interaction, "⚠️ チケットは現在利用できません。管理者に連絡してください。")
    if member.id in tc["blocked"]:
        return await _eph(interaction, "🚫 あなたはチケットを作成できません。")
    if verify_active(cfg):
        vrole = guild.get_role(cfg["verify"]["role"])
        if vrole and vrole not in member.roles:
            return await _eph(interaction, "🔐 先にメンバー認証を完了してください。")
    wait = TICKET_COOLDOWN - (time.time() - ticket_last.get((guild.id, member.id), 0))
    if wait > 0:
        return await _eph(interaction, f"⏳ {wait:.0f}秒後にもう一度お試しください。")
    mine = ticket_open_of(guild, tc, member.id)
    if len(mine) >= tc["max_open"]:
        return await _eph(interaction, "❌ すでに開いているチケットがあります: " + " ".join(c.mention for c in mine))
    await interaction.response.send_modal(TicketModal())


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="チケットを作成", emoji="🎫", style=discord.ButtonStyle.primary, custom_id="azq:ticket:create")
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ticket_click(interaction)


class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="閉じる", emoji="🔒", style=discord.ButtonStyle.danger)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="🔒 チケットを閉じています...", view=None)
        if not await close_ticket(interaction.channel, interaction.user, None):
            await interaction.edit_original_response(content="⚠️ すでにクローズされています。")

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="キャンセルしました。", view=None)


class ConfirmDeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="削除する", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        if not (isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator):
            return await interaction.response.edit_message(content="❌ チケットを削除できるのは管理者のみです。", view=None)
        await interaction.response.edit_message(content="🗑️ チケットを削除しています...", view=None)
        await delete_ticket(interaction.channel, interaction.user)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="キャンセルしました。", view=None)


class TicketClosedView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="チケットを削除(管理者のみ)", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="azq:ticket:delete")
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        tc = store.get(interaction.guild.id)["ticket"]
        info = tc["open"].get(str(interaction.channel_id))
        if not info:
            return await _eph(interaction, "⚠️ このチケットは管理対象ではありません。")
        if not interaction.user.guild_permissions.administrator:
            return await _eph(interaction, "❌ チケットを削除できるのは管理者のみです。")
        if not info.get("closed"):
            return await _eph(interaction, "⚠️ 先にチケットをクローズしてください。")
        await interaction.response.send_message("このチケットのチャンネルを削除しますか?(元に戻せません)",
                                                view=ConfirmDeleteView(), ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self, claimed: bool = False):
        super().__init__(timeout=None)
        if claimed:
            self.claim.disabled = True

    @discord.ui.button(label="クローズ", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="azq:ticket:close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        tc = store.get(interaction.guild.id)["ticket"]
        info = tc["open"].get(str(interaction.channel_id))
        if not info:
            return await _eph(interaction, "⚠️ このチケットは管理対象ではありません。")
        if info.get("closed"):
            return await _eph(interaction, "⚠️ このチケットはすでにクローズされています。")
        if not (info["owner"] == interaction.user.id or ticket_is_staff(interaction.user, tc)):
            return await _eph(interaction, "❌ 作成者かスタッフのみ閉じられます。")
        await interaction.response.send_message("このチケットを閉じますか?(記録を保存してチャンネルを閲覧のみにします。削除は管理者のみ可能です)",
                                                view=ConfirmCloseView(), ephemeral=True)

    @discord.ui.button(label="担当する", emoji="🙋", style=discord.ButtonStyle.success, custom_id="azq:ticket:claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        tc = store.get(interaction.guild.id)["ticket"]
        info = tc["open"].get(str(interaction.channel_id))
        if not info:
            return await _eph(interaction, "⚠️ このチケットは管理対象ではありません。")
        if info.get("closed"):
            return await _eph(interaction, "⚠️ このチケットはすでにクローズされています。")
        if not ticket_is_staff(interaction.user, tc):
            return await _eph(interaction, "❌ スタッフのみ担当できます。")
        if info["claimed_by"]:
            return await _eph(interaction, f"すでに <@{info['claimed_by']}> が担当しています。")
        info["claimed_by"] = interaction.user.id
        store.save()
        await interaction.response.edit_message(view=TicketControlView(claimed=True))
        await interaction.channel.send(f"🙋 {interaction.user.mention} が担当します。",
                                       allowed_mentions=discord.AllowedMentions(users=True))


def ticket_panel_embed(tc: dict) -> discord.Embed:
    return make_embed(tc["panel_title"], tc["panel_text"], BLUE)


async def delete_ticket_panel(guild: discord.Guild) -> None:
    tc = store.get(guild.id)["ticket"]
    ch = guild.get_channel(tc["panel_channel"]) if tc["panel_channel"] else None
    if ch and tc["panel_message"]:
        try:
            await (await ch.fetch_message(tc["panel_message"])).delete()
        except discord.HTTPException:
            pass
    tc["panel_channel"] = tc["panel_message"] = None


async def post_ticket_panel(guild: discord.Guild, channel: discord.TextChannel) -> discord.Message:
    await delete_ticket_panel(guild)
    tc = store.get(guild.id)["ticket"]
    msg = await channel.send(embed=ticket_panel_embed(tc), view=TicketPanelView())
    tc["panel_channel"], tc["panel_message"] = channel.id, msg.id
    store.save()
    return msg


@tasks.loop(minutes=15)
async def ticket_watch():
    now = discord.utils.utcnow()
    for guild in list(bot.guilds):
        if guild.unavailable:
            continue
        tc = store.get(guild.id)["ticket"]
        if not tc["enabled"] or not tc["auto_close_hours"]:
            continue
        for cid, info in list(tc["open"].items()):
            ch = guild.get_channel(int(cid))
            if ch is None:
                tc["open"].pop(cid, None)
                store.save()
                continue
            if info.get("closed"):
                continue
            last = (discord.utils.snowflake_time(ch.last_message_id) if ch.last_message_id
                    else datetime.fromtimestamp(info["created"], timezone.utc))
            if (now - last).total_seconds() >= tc["auto_close_hours"] * 3600:
                await close_ticket(ch, None, f"{tc['auto_close_hours']}時間操作がなかったため自動クローズ")


@ticket_watch.before_loop
async def _before_ticket_watch():
    await bot.wait_until_ready()
    await asyncio.sleep(40)


@bot.event
async def on_guild_channel_delete(channel):
    tc = store.get(channel.guild.id)["ticket"]
    if tc["open"].pop(str(channel.id), None) is not None:
        store.save()


def _ticket_here(interaction: discord.Interaction):
    tc = store.get(interaction.guild.id)["ticket"]
    return tc, tc["open"].get(str(interaction.channel_id))


@ticket_group.command(name="close", description="このチケットを閉じます")
@app_commands.describe(reason="閉じる理由")
async def ticket_close_cmd(interaction: discord.Interaction, reason: Optional[app_commands.Range[str, 1, 200]] = None):
    tc, info = _ticket_here(interaction)
    if not info:
        return await interaction.response.send_message("❌ ここはチケットチャンネルではありません。", ephemeral=True)
    if info.get("closed"):
        return await interaction.response.send_message("⚠️ このチケットはすでにクローズされています。", ephemeral=True)
    if not (info["owner"] == interaction.user.id or ticket_is_staff(interaction.user, tc)):
        return await interaction.response.send_message("❌ 作成者かスタッフのみ実行できます。", ephemeral=True)
    await interaction.response.send_message("🔒 チケットを閉じます...", ephemeral=True)
    await close_ticket(interaction.channel, interaction.user, reason)


@ticket_group.command(name="delete", description="クローズ済みのチケットを削除します(管理者のみ)")
async def ticket_delete_cmd(interaction: discord.Interaction):
    tc, info = _ticket_here(interaction)
    if not info:
        return await interaction.response.send_message("❌ ここはチケットチャンネルではありません。", ephemeral=True)
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ チケットを削除できるのは管理者のみです。", ephemeral=True)
    if not info.get("closed"):
        return await interaction.response.send_message("⚠️ 先に `/ticket close` でクローズしてください。", ephemeral=True)
    await interaction.response.send_message("このチケットのチャンネルを削除しますか?(元に戻せません)",
                                            view=ConfirmDeleteView(), ephemeral=True)


@ticket_group.command(name="add", description="メンバーをこのチケットに追加します(スタッフ用)")
async def ticket_add(interaction: discord.Interaction, member: discord.Member):
    tc, info = _ticket_here(interaction)
    if not info:
        return await interaction.response.send_message("❌ ここはチケットチャンネルではありません。", ephemeral=True)
    if not ticket_is_staff(interaction.user, tc):
        return await interaction.response.send_message("❌ スタッフのみ実行できます。", ephemeral=True)
    if info.get("closed"):
        return await interaction.response.send_message("⚠️ クローズ済みのチケットには追加できません。", ephemeral=True)
    await interaction.channel.set_permissions(member, overwrite=discord.PermissionOverwrite(**TICKET_MEMBER_PERMS),
                                              reason=f"ticket add by {interaction.user}")
    await interaction.response.send_message(f"➕ {member.mention} を追加しました。", allowed_mentions=discord.AllowedMentions(users=[member]))


@ticket_group.command(name="remove", description="メンバーをこのチケットから外します(スタッフ用)")
async def ticket_remove(interaction: discord.Interaction, member: discord.Member):
    tc, info = _ticket_here(interaction)
    if not info:
        return await interaction.response.send_message("❌ ここはチケットチャンネルではありません。", ephemeral=True)
    if not ticket_is_staff(interaction.user, tc):
        return await interaction.response.send_message("❌ スタッフのみ実行できます。", ephemeral=True)
    if member.id == info["owner"] or ticket_is_staff(member, tc):
        return await interaction.response.send_message("❌ 作成者とスタッフは外せません。", ephemeral=True)
    await interaction.channel.set_permissions(member, overwrite=None, reason=f"ticket remove by {interaction.user}")
    await interaction.response.send_message(f"➖ {member.mention} を外しました。", allowed_mentions=discord.AllowedMentions.none())


@ticket_group.command(name="rename", description="チケットの名前を変更します(スタッフ用)")
async def ticket_rename(interaction: discord.Interaction, name: app_commands.Range[str, 1, 80]):
    tc, info = _ticket_here(interaction)
    if not info:
        return await interaction.response.send_message("❌ ここはチケットチャンネルではありません。", ephemeral=True)
    if not ticket_is_staff(interaction.user, tc):
        return await interaction.response.send_message("❌ スタッフのみ実行できます。", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    try:
        await asyncio.wait_for(interaction.channel.edit(name=name, reason=f"ticket rename by {interaction.user}"), timeout=8)
    except asyncio.TimeoutError:
        return await interaction.followup.send("⏳ 名前変更の回数制限中です。しばらくしてからお試しください。", ephemeral=True)
    await interaction.followup.send("✅ 名前を変更しました。", ephemeral=True)


def _can_post(ch: discord.abc.GuildChannel, me: discord.Member, files: bool = False) -> bool:
    p = ch.permissions_for(me)
    return p.view_channel and p.send_messages and p.embed_links and (p.attach_files if files else True)


@ticketconfig_group.command(name="setup", description="チケットパネルを設置して機能を有効化します")
@app_commands.describe(
    panel_channel="チケット作成パネルを置くチャンネル", category="チケットチャンネルを作るカテゴリ",
    staff_role="チケットに対応するスタッフのロール", transcript_channel="クローズ時の記録の送信先(省略時はログチャンネル)",
    max_open="1人が同時に開けるチケット数(既定1)",
)
@app_commands.checks.has_permissions(administrator=True)
async def tcfg_setup(interaction: discord.Interaction, panel_channel: discord.TextChannel,
                     category: discord.CategoryChannel, staff_role: discord.Role,
                     transcript_channel: Optional[discord.TextChannel] = None,
                     max_open: Optional[app_commands.Range[int, 1, 5]] = None):
    g = interaction.guild
    me = g.me
    if staff_role.is_default():
        return await interaction.response.send_message("❌ @everyone はスタッフロールにできません。", ephemeral=True)
    cp = category.permissions_for(me)
    if not (cp.view_channel and cp.manage_channels):
        return await interaction.response.send_message(f"❌ BOTが「{category.name}」でチャンネルを管理できません。BOTに「チャンネルの管理」権限を付けてください。", ephemeral=True)
    if not _can_post(panel_channel, me):
        return await interaction.response.send_message(f"❌ BOTが {panel_channel.mention} に送信できません。", ephemeral=True)
    if transcript_channel and not _can_post(transcript_channel, me, files=True):
        return await interaction.response.send_message(f"❌ BOTが {transcript_channel.mention} に送信・ファイル添付できません。", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    tc = store.get(g.id)["ticket"]
    tc.update(enabled=True, category=category.id)
    if staff_role.id not in tc["staff_roles"]:
        tc["staff_roles"].append(staff_role.id)
    if transcript_channel:
        tc["transcript_channel"] = transcript_channel.id
    if max_open:
        tc["max_open"] = max_open
    try:
        await post_ticket_panel(g, panel_channel)
    except discord.HTTPException:
        tc["enabled"] = False
        store.save()
        return await interaction.followup.send("❌ パネルを送信できませんでした。BOTの権限を確認してください。", ephemeral=True)
    store.save()
    gp = g.me.guild_permissions
    missing = [n for n, ok in (("チャンネルの管理", gp.manage_channels), ("ロールの管理", gp.manage_roles),
                               ("ファイルを添付", gp.attach_files), ("メッセージ履歴を読む", gp.read_message_history)) if not ok]
    warn = ("\n⚠️ BOTに次の権限がないと、チケット作成や記録の保存に失敗することがあります: " + " / ".join(missing)) if missing else ""
    await interaction.followup.send(
        f"✅ チケット機能を有効化しました。\nパネル: {panel_channel.mention} / カテゴリ: **{category.name}** / スタッフ: {staff_role.mention}\n"
        "スタッフの追加は `/ticketconfig staff`、自動クローズなどは `/ticketconfig set` で設定できます。\n"
        "※ カテゴリには1つあたり最大50チャンネルの上限があります。" + warn,
        ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


@ticketconfig_group.command(name="set", description="チケットの詳細設定を変更します(指定した項目のみ変更)")
@app_commands.describe(
    max_open="1人が同時に開けるチケット数", auto_close_hours="この時間操作がないと自動クローズ(0=しない)",
    ping_staff="作成時にスタッフロールへメンションする", dm_transcript="クローズ時に作成者へ記録をDMする",
    transcript_channel="記録の送信先チャンネル", category="チケットを作るカテゴリ",
)
@app_commands.checks.has_permissions(administrator=True)
async def tcfg_set(interaction: discord.Interaction, max_open: Optional[app_commands.Range[int, 1, 5]] = None,
                   auto_close_hours: Optional[app_commands.Range[int, 0, 720]] = None,
                   ping_staff: Optional[bool] = None, dm_transcript: Optional[bool] = None,
                   transcript_channel: Optional[discord.TextChannel] = None,
                   category: Optional[discord.CategoryChannel] = None):
    tc = store.get(interaction.guild.id)["ticket"]
    me = interaction.guild.me
    if transcript_channel and not _can_post(transcript_channel, me, files=True):
        return await interaction.response.send_message("❌ BOTがそのチャンネルに送信・ファイル添付できません。", ephemeral=True)
    if category:
        cp = category.permissions_for(me)
        if not (cp.view_channel and cp.manage_channels):
            return await interaction.response.send_message("❌ BOTがそのカテゴリでチャンネルを管理できません。", ephemeral=True)
    changed = []
    for key, val in (("max_open", max_open), ("auto_close_hours", auto_close_hours), ("ping_staff", ping_staff),
                     ("dm_transcript", dm_transcript),
                     ("transcript_channel", transcript_channel.id if transcript_channel else None),
                     ("category", category.id if category else None)):
        if val is not None:
            tc[key] = val
            changed.append(f"`{key}` = `{val}`")
    if not changed:
        return await interaction.response.send_message("変更する項目を指定してください。", ephemeral=True)
    store.save()
    await interaction.response.send_message("✅ 更新しました:\n" + "\n".join(changed), ephemeral=True)


@ticketconfig_group.command(name="staff", description="スタッフロールの追加・削除・一覧")
@app_commands.choices(action=[
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="remove", value="remove"),
    app_commands.Choice(name="list", value="list"),
])
@app_commands.checks.has_permissions(administrator=True)
async def tcfg_staff(interaction: discord.Interaction, action: app_commands.Choice[str], role: Optional[discord.Role] = None):
    tc = store.get(interaction.guild.id)["ticket"]
    none = discord.AllowedMentions.none()
    if action.value == "list":
        return await interaction.response.send_message(
            "スタッフロール: " + (" ".join(f"<@&{i}>" for i in tc["staff_roles"]) or "なし"), ephemeral=True, allowed_mentions=none)
    if not role:
        return await interaction.response.send_message("❌ role を指定してください。", ephemeral=True)
    if action.value == "add":
        if role.is_default():
            return await interaction.response.send_message("❌ @everyone は指定できません。", ephemeral=True)
        if len(tc["staff_roles"]) >= 10:
            return await interaction.response.send_message("❌ スタッフロールは10個までです。", ephemeral=True)
        if role.id not in tc["staff_roles"]:
            tc["staff_roles"].append(role.id)
    elif role.id in tc["staff_roles"]:
        tc["staff_roles"].remove(role.id)
    store.save()
    await interaction.response.send_message(
        f"✅ {action.value}: {role.mention}\n※ すでに開いているチケットの閲覧権限には反映されません。", ephemeral=True, allowed_mentions=none)


@ticketconfig_group.command(name="panel", description="チケットパネルの再設置/文面を変更します")
@app_commands.describe(channel="省略すると現在のパネルのチャンネル", title="パネルのタイトル", text="パネルの説明文(改行は \\n)")
@app_commands.checks.has_permissions(administrator=True)
async def tcfg_panel(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None,
                     title: Optional[app_commands.Range[str, 1, 100]] = None,
                     text: Optional[app_commands.Range[str, 1, 1500]] = None):
    g = interaction.guild
    tc = store.get(g.id)["ticket"]
    target = channel or (g.get_channel(tc["panel_channel"]) if tc["panel_channel"] else None)
    if not target:
        return await interaction.response.send_message("❌ channel を指定してください(まず /ticketconfig setup を実行してください)。", ephemeral=True)
    if not _can_post(target, g.me):
        return await interaction.response.send_message("❌ BOTがそのチャンネルに送信できません。", ephemeral=True)
    if title:
        tc["panel_title"] = title
    if text:
        tc["panel_text"] = text.replace("\\n", "\n")
    await interaction.response.defer(ephemeral=True)
    try:
        await post_ticket_panel(g, target)
    except discord.HTTPException:
        return await interaction.followup.send("❌ パネルを送信できませんでした。", ephemeral=True)
    await interaction.followup.send(f"✅ {target.mention} にパネルを設置しました。", ephemeral=True)


@ticketconfig_group.command(name="block", description="ユーザーのチケット作成を禁止します")
@app_commands.checks.has_permissions(administrator=True)
async def tcfg_block(interaction: discord.Interaction, user: discord.User):
    tc = store.get(interaction.guild.id)["ticket"]
    if user.id not in tc["blocked"]:
        tc["blocked"].append(user.id)
        store.save()
    await interaction.response.send_message(f"🚫 {user} のチケット作成を禁止しました。", ephemeral=True)


@ticketconfig_group.command(name="unblock", description="チケット作成の禁止を解除します")
@app_commands.checks.has_permissions(administrator=True)
async def tcfg_unblock(interaction: discord.Interaction, user: discord.User):
    tc = store.get(interaction.guild.id)["ticket"]
    if user.id in tc["blocked"]:
        tc["blocked"].remove(user.id)
        store.save()
    await interaction.response.send_message(f"✅ {user} の禁止を解除しました。", ephemeral=True)


@ticketconfig_group.command(name="status", description="チケット機能の状態と開いているチケットを表示します")
@app_commands.checks.has_permissions(administrator=True)
async def tcfg_status(interaction: discord.Interaction):
    g = interaction.guild
    tc = store.get(g.id)["ticket"]
    e = make_embed("🎫 チケットの状態", color=GREEN if tc["enabled"] else GRAY)
    e.add_field(name="状態", value="ON" if tc["enabled"] else "OFF")
    e.add_field(name="カテゴリ", value=f"<#{tc['category']}>" if tc["category"] else "未設定")
    e.add_field(name="スタッフ", value=" ".join(f"<@&{i}>" for i in tc["staff_roles"]) or "なし")
    e.add_field(name="記録の送信先", value=f"<#{tc['transcript_channel']}>" if tc["transcript_channel"] else "ログチャンネル")
    e.add_field(name="同時作成数", value=f"{tc['max_open']}件/人")
    e.add_field(name="自動クローズ", value=f"{tc['auto_close_hours']}時間" if tc["auto_close_hours"] else "なし")
    e.add_field(name="スタッフ通知 / DM記録", value=f"{'ON' if tc['ping_staff'] else 'OFF'} / {'ON' if tc['dm_transcript'] else 'OFF'}")
    e.add_field(name="禁止ユーザー", value=f"{len(tc['blocked'])}人")
    e.add_field(name="累計", value=f"作成 {tc['stats']['created']} / クローズ {tc['stats']['closed']}")
    opened = {c: i for c, i in tc["open"].items() if not i.get("closed")}
    closed = {c: i for c, i in tc["open"].items() if i.get("closed")}
    if opened:
        lines = []
        for cid, info in list(opened.items())[:15]:
            claim = f" 担当<@{info['claimed_by']}>" if info["claimed_by"] else ""
            lines.append(f"<#{cid}> <@{info['owner']}>{claim}")
        e.add_field(name=f"開いているチケット ({len(opened)})", value="\n".join(lines), inline=False)
    if closed:
        e.add_field(name=f"クローズ済み・削除待ち ({len(closed)})",
                    value="\n".join(f"<#{cid}> <@{i['owner']}>" for cid, i in list(closed.items())[:15]), inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


@ticketconfig_group.command(name="disable", description="チケット機能を無効化し、パネルを削除します")
@app_commands.checks.has_permissions(administrator=True)
async def tcfg_disable(interaction: discord.Interaction):
    tc = store.get(interaction.guild.id)["ticket"]
    await interaction.response.defer(ephemeral=True)
    tc["enabled"] = False
    await delete_ticket_panel(interaction.guild)
    store.save()
    await interaction.followup.send("✅ チケット機能を無効化しました。\n※ すでに開いているチケットは、クローズするまでそのまま残ります。", ephemeral=True)


RP_MAX_ROLES = 25
rolepanel_group = app_commands.Group(
    name="rolepanel", description="ロールパネル(ボタンでロールを付与/解除)の管理",
    default_permissions=discord.Permissions(administrator=True), guild_only=True,
)


def rp_dangerous(role: discord.Role) -> list:
    return [n for n in DANGEROUS_PERMS if getattr(role.permissions, n)]


def rp_role_problem(interaction: discord.Interaction, role: discord.Role) -> Optional[str]:
    if p := role_problem(interaction, role):
        return p
    if bad := rp_dangerous(role):
        return "危険な権限が含まれています(誰でも取得できてしまうため): " + ", ".join(bad)
    return None


def rp_embed(p: dict) -> discord.Embed:
    e = make_embed(p["title"], p["text"], BLUE)
    e.add_field(name="選べるロール" + (" (1つだけ選択)" if p["exclusive"] else ""),
                value="\n".join(f"・<@&{r['id']}>" for r in p["roles"]) or "なし", inline=False)
    e.set_footer(text="ボタンを押すとロールを付与、もう一度押すと解除します")
    return e


class RoleButton(discord.ui.Button):
    def __init__(self, rid: int, label: str):
        super().__init__(label=(label or "ロール")[:80], style=discord.ButtonStyle.primary, custom_id=f"azq:rp:{rid}")
        self.rid = rid

    async def callback(self, interaction: discord.Interaction):
        await role_panel_click(interaction, self.rid)


class RolePanelView(discord.ui.View):
    def __init__(self, roles: list):
        super().__init__(timeout=None)
        for r in roles:
            self.add_item(RoleButton(r["id"], r["label"]))


async def role_panel_click(interaction: discord.Interaction, rid: int) -> None:
    guild, member = interaction.guild, interaction.user
    if guild is None or not isinstance(member, discord.Member):
        return await _eph(interaction, "❌ サーバー内で使ってください。")
    cfg = store.get(guild.id)
    p = cfg["rolepanel"]["panels"].get(str(interaction.message.id))
    if not p or not any(r["id"] == rid for r in p["roles"]):
        return await _eph(interaction, "⚠️ このロールパネルは無効です。管理者に連絡してください。")
    if verify_active(cfg) and str(member.id) in cfg["verify"]["pending"]:
        return await _eph(interaction, "🔐 先にメンバー認証を完了してください。")
    role = guild.get_role(rid)
    me = guild.me
    if role is None:
        return await _eph(interaction, "⚠️ このロールは削除されています。管理者に連絡してください。")
    if (not me.guild_permissions.manage_roles or role >= me.top_role or role.managed
            or role.is_default() or rp_dangerous(role)):
        return await _eph(interaction, "⚠️ このロールは付与できません。管理者にBOTの権限・ロール順位の確認を依頼してください。")
    await interaction.response.defer(ephemeral=True)
    try:
        if role in member.roles:
            await member.remove_roles(role, reason="AZQ BOT ロールパネル")
            msg = f"➖ {role.mention} を外しました。"
        else:
            if p["exclusive"]:
                others = [guild.get_role(r["id"]) for r in p["roles"] if r["id"] != rid]
                others = [o for o in others if o and o in member.roles and o < me.top_role and not o.managed]
                if others:
                    await member.remove_roles(*others, reason="AZQ BOT ロールパネル(1つだけ選択)")
            await member.add_roles(role, reason="AZQ BOT ロールパネル")
            msg = f"➕ {role.mention} を付与しました。"
    except discord.HTTPException:
        log.warning("ロールパネルでの付与に失敗 guild=%s role=%s", guild.id, rid, exc_info=True)
        msg = "⚠️ ロールの付与に失敗しました。BOTの権限・ロール順位の確認を管理者に依頼してください。"
    await interaction.followup.send(msg, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


async def refresh_role_panel(guild: discord.Guild, mid: str) -> bool:
    p = store.get(guild.id)["rolepanel"]["panels"].get(mid)
    ch = guild.get_channel(p["channel"]) if p else None
    if not ch:
        return False
    view = RolePanelView(p["roles"])
    try:
        msg = await ch.fetch_message(int(mid))
        await msg.edit(embed=rp_embed(p), view=view)
    except discord.HTTPException:
        return False
    bot.add_view(view, message_id=int(mid))
    return True


def _rp_find(interaction: discord.Interaction, message_id: str):
    panels = store.get(interaction.guild.id)["rolepanel"]["panels"]
    mid = message_id.strip()
    return mid, panels.get(mid)


@rolepanel_group.command(name="create", description="ロールパネルを作成します(ボタンでロールを付与/解除)")
@app_commands.describe(
    channel="パネルを置くチャンネル", role1="1つ目のロール", role2="2つ目以降は任意(最大10個。11個目以降は /rolepanel add)",
    title="パネルのタイトル", text="パネルの説明文(改行は \\n)", exclusive="Trueにすると1つだけ選択(押すと他のロールが外れる)",
)
@app_commands.checks.has_permissions(administrator=True)
async def rp_create(interaction: discord.Interaction, channel: discord.TextChannel, role1: discord.Role,
                    role2: Optional[discord.Role] = None, role3: Optional[discord.Role] = None,
                    role4: Optional[discord.Role] = None, role5: Optional[discord.Role] = None,
                    role6: Optional[discord.Role] = None, role7: Optional[discord.Role] = None,
                    role8: Optional[discord.Role] = None, role9: Optional[discord.Role] = None,
                    role10: Optional[discord.Role] = None,
                    title: Optional[app_commands.Range[str, 1, 100]] = None,
                    text: Optional[app_commands.Range[str, 1, 1500]] = None, exclusive: bool = False):
    roles = []
    for r in (role1, role2, role3, role4, role5, role6, role7, role8, role9, role10):
        if r and r not in roles:
            roles.append(r)
    for r in roles:
        if p := rp_role_problem(interaction, r):
            return await interaction.response.send_message(f"❌ {r.mention}: {p}", ephemeral=True,
                                                           allowed_mentions=discord.AllowedMentions.none())
    if not _can_post(channel, interaction.guild.me):
        return await interaction.response.send_message(f"❌ BOTが {channel.mention} に送信できません。", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    p = {"channel": channel.id, "title": title or "🎭 ロールパネル",
         "text": (text or "ボタンを押して、好きなロールを受け取りましょう。").replace("\\n", "\n"),
         "exclusive": exclusive, "roles": [{"id": r.id, "label": r.name} for r in roles]}
    try:
        msg = await channel.send(embed=rp_embed(p), view=RolePanelView(p["roles"]))
    except discord.HTTPException:
        return await interaction.followup.send("❌ パネルを送信できませんでした。BOTの権限を確認してください。", ephemeral=True)
    store.get(interaction.guild.id)["rolepanel"]["panels"][str(msg.id)] = p
    store.save()
    warn = "" if interaction.guild.me.guild_permissions.manage_roles else "\n⚠️ BOTに「ロールの管理」権限がありません。このままではロールを付与できません。"
    await interaction.followup.send(
        f"✅ {channel.mention} にロールパネルを設置しました。(メッセージID: `{msg.id}`)\n"
        "ロールの追加・削除は `/rolepanel add` `/rolepanel remove` で行えます。\n"
        "※ BOTのロールを、付与するロールより**上**に配置してください。" + warn, ephemeral=True)


@rolepanel_group.command(name="add", description="既存のロールパネルにロールを追加します")
@app_commands.describe(message_id="パネルのメッセージID(/rolepanel list で確認)", role="追加するロール")
@app_commands.checks.has_permissions(administrator=True)
async def rp_add(interaction: discord.Interaction, message_id: str, role: discord.Role):
    mid, p = _rp_find(interaction, message_id)
    if not p:
        return await interaction.response.send_message("❌ そのIDのロールパネルが見つかりません。`/rolepanel list` で確認してください。", ephemeral=True)
    if any(r["id"] == role.id for r in p["roles"]):
        return await interaction.response.send_message("❌ すでにこのパネルにあるロールです。", ephemeral=True)
    if len(p["roles"]) >= RP_MAX_ROLES:
        return await interaction.response.send_message(f"❌ 1つのパネルに置けるロールは{RP_MAX_ROLES}個までです。", ephemeral=True)
    if prob := rp_role_problem(interaction, role):
        return await interaction.response.send_message(f"❌ {prob}", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    p["roles"].append({"id": role.id, "label": role.name})
    if not await refresh_role_panel(interaction.guild, mid):
        p["roles"].pop()
        return await interaction.followup.send("❌ パネルを更新できませんでした。(メッセージが削除されている可能性があります)", ephemeral=True)
    store.save()
    await interaction.followup.send(f"✅ {role.mention} を追加しました。", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


@rolepanel_group.command(name="remove", description="ロールパネルからロールを外します")
@app_commands.describe(message_id="パネルのメッセージID(/rolepanel list で確認)", role="外すロール")
@app_commands.checks.has_permissions(administrator=True)
async def rp_remove(interaction: discord.Interaction, message_id: str, role: discord.Role):
    mid, p = _rp_find(interaction, message_id)
    if not p:
        return await interaction.response.send_message("❌ そのIDのロールパネルが見つかりません。`/rolepanel list` で確認してください。", ephemeral=True)
    target = next((r for r in p["roles"] if r["id"] == role.id), None)
    if not target:
        return await interaction.response.send_message("❌ そのロールはこのパネルにありません。", ephemeral=True)
    if len(p["roles"]) <= 1:
        return await interaction.response.send_message("❌ 最後のロールは外せません。パネルごと消すには `/rolepanel delete` を使ってください。", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    p["roles"].remove(target)
    if not await refresh_role_panel(interaction.guild, mid):
        p["roles"].append(target)
        return await interaction.followup.send("❌ パネルを更新できませんでした。(メッセージが削除されている可能性があります)", ephemeral=True)
    store.save()
    await interaction.followup.send(f"✅ {role.mention} を外しました。", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


@rolepanel_group.command(name="delete", description="ロールパネルを削除します")
@app_commands.describe(message_id="パネルのメッセージID(/rolepanel list で確認)")
@app_commands.checks.has_permissions(administrator=True)
async def rp_delete(interaction: discord.Interaction, message_id: str):
    mid, p = _rp_find(interaction, message_id)
    if not p:
        return await interaction.response.send_message("❌ そのIDのロールパネルが見つかりません。", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    ch = interaction.guild.get_channel(p["channel"])
    if ch:
        try:
            await (await ch.fetch_message(int(mid))).delete()
        except discord.HTTPException:
            pass
    store.get(interaction.guild.id)["rolepanel"]["panels"].pop(mid, None)
    store.save()
    await interaction.followup.send("✅ ロールパネルを削除しました。(付与済みのロールはそのままです)", ephemeral=True)


class RolePanelTextModal(discord.ui.Modal, title="ロールパネルの文面を編集"):
    def __init__(self, mid: str, p: dict):
        super().__init__()
        self.mid = mid
        self.t = discord.ui.TextInput(label="タイトル", default=p["title"][:100], max_length=100)
        self.d = discord.ui.TextInput(label="説明文", style=discord.TextStyle.paragraph, default=p["text"][:1500], max_length=1500)
        self.b = discord.ui.TextInput(label="ボタンの名前(1行に1つ・上のロールから順)", style=discord.TextStyle.paragraph,
                                      default="\n".join(r["label"] for r in p["roles"])[:2500], max_length=2500)
        for item in (self.t, self.d, self.b):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        p = store.get(interaction.guild.id)["rolepanel"]["panels"].get(self.mid)
        if not p:
            return await interaction.response.send_message("❌ このロールパネルは見つかりません。", ephemeral=True)
        labels = [l.strip()[:80] for l in self.b.value.splitlines() if l.strip()]
        if len(labels) != len(p["roles"]):
            return await interaction.response.send_message(
                f"❌ ボタンの名前の行数({len(labels)})が、ボタンの数({len(p['roles'])})と合いません。1行に1つずつ入力してください。", ephemeral=True)
        p["title"], p["text"] = self.t.value.strip(), self.d.value.strip()
        for r, label in zip(p["roles"], labels):
            r["label"] = label
        await interaction.response.defer(ephemeral=True)
        if not await refresh_role_panel(interaction.guild, self.mid):
            return await interaction.followup.send("❌ パネルを更新できませんでした。(メッセージが削除されている可能性があります)", ephemeral=True)
        store.save()
        await interaction.followup.send("✅ ロールパネルの文面を更新しました。", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.exception("ロールパネルの文面編集でエラー", exc_info=error)
        await _eph(interaction, "⚠️ 更新に失敗しました。もう一度お試しください。")


@rolepanel_group.command(name="text", description="ロールパネルの文面(タイトル・説明・ボタン名)を入力フォームで編集します")
@app_commands.describe(message_id="編集するパネル(候補から選べます)")
@app_commands.checks.has_permissions(administrator=True)
async def rp_text(interaction: discord.Interaction, message_id: str):
    mid, p = _rp_find(interaction, message_id)
    if not p:
        return await interaction.response.send_message("❌ そのIDのロールパネルが見つかりません。候補から選んでください。", ephemeral=True)
    await interaction.response.send_modal(RolePanelTextModal(mid, p))


async def rp_panel_choices(interaction: discord.Interaction, current: str):
    out = []
    for mid, p in store.get(interaction.guild.id)["rolepanel"]["panels"].items():
        ch = interaction.guild.get_channel(p["channel"])
        name = f"{p['title'][:55]} (#{ch.name if ch else '不明'})"
        if not current or current.lower() in name.lower() or current in mid:
            out.append(app_commands.Choice(name=name[:100], value=mid))
    return out[:25]


for _cmd in (rp_add, rp_remove, rp_delete, rp_text):
    _cmd.autocomplete("message_id")(rp_panel_choices)


@rolepanel_group.command(name="list", description="設置中のロールパネルを一覧表示します")
@app_commands.checks.has_permissions(administrator=True)
async def rp_list(interaction: discord.Interaction):
    panels = store.get(interaction.guild.id)["rolepanel"]["panels"]
    if not panels:
        return await interaction.response.send_message("ロールパネルはありません。`/rolepanel create` で作成できます。", ephemeral=True)
    e = make_embed("🎭 ロールパネル一覧", color=BLUE)
    for mid, p in list(panels.items())[:20]:
        link = f"https://discord.com/channels/{interaction.guild.id}/{p['channel']}/{mid}"
        e.add_field(name=f"{p['title'][:60]}", value=f"[メッセージへ]({link}) / ID: `{mid}`\n"
                    + " ".join(f"<@&{r['id']}>" for r in p["roles"])[:900]
                    + ("\n(1つだけ選択)" if p["exclusive"] else ""), inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


DASH_TTL = 30 * 24 * 3600
WEB_HINT_ROOTS = {"config", "verify", "ticketconfig", "rolepanel"}


class DashSessions:
    """ログイン状態。再起動やブラウザを閉じてもログインが続くよう、ファイルに保存する。
    ブラウザに渡すクッキーの値そのものは保存せず、ハッシュだけを保存する(ファイルが漏れてもなりすませない)。"""

    def __init__(self, directory: str):
        self.path = os.path.join(directory, "dash_sessions.json")
        self.data: dict = {}
        self._saved = 0.0
        try:
            with open(self.path, encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            pass
        self._prune()

    @staticmethod
    def _key(sid: str) -> str:
        return hashlib.sha256(sid.encode()).hexdigest()

    def _prune(self) -> None:
        now = time.time()
        for k in [k for k, v in self.data.items() if v.get("exp", 0) < now]:
            self.data.pop(k, None)

    def _write(self) -> None:
        self._saved = time.time()
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, separators=(",", ":"))
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, self.path)
        except OSError:
            log.exception("ダッシュボードのログイン情報を保存できませんでした")

    def create(self, user: dict) -> str:
        sid = secrets.token_urlsafe(32)
        self._prune()
        self.data[self._key(sid)] = {"exp": time.time() + DASH_TTL, "user": user}
        self._write()
        return sid

    def get(self, sid: str):
        rec = self.data.get(self._key(sid)) if sid else None
        return rec if rec and rec["exp"] > time.time() else None

    def touch(self, sid: str) -> None:
        rec = self.get(sid)
        if rec:
            rec["exp"] = time.time() + DASH_TTL
            if time.time() - self._saved > 3600:
                self._write()

    def delete(self, sid: str) -> None:
        if self.data.pop(self._key(sid), None) is not None:
            self._write()


dash_sessions = DashSessions(DATA_DIR)
dash_states: dict = {}


def _dash_sid(request) -> str:
    return request.cookies.get("azq_sid", "")


def _dash_session(request):
    return dash_sessions.get(_dash_sid(request))


def _is_https() -> bool:
    return DASH_BASE.startswith("https")


def _set_sid_cookie(resp, sid: str) -> None:
    resp.set_cookie("azq_sid", sid, max_age=DASH_TTL, httponly=True, samesite="Lax", secure=_is_https(), path="/")


def _valid_gid(v) -> str:
    v = str(v or "")
    return v if v.isdigit() and len(v) <= 20 else ""


def dash_url(guild_id=None) -> str:
    """ダッシュボードのURL。サーバーIDを付けると、そのサーバーの画面から開く(ログインしていなければ、ログイン後に開く)"""
    return DASH_BASE + (f"/?g={guild_id}" if guild_id else "/")


def _can_manage(m: discord.Member) -> bool:
    p = m.guild_permissions
    return bool(p.administrator or p.manage_guild)


async def _dash_member(g: discord.Guild, uid: int) -> Optional[discord.Member]:
    m = g.get_member(uid)
    if m is None:
        try:
            m = await g.fetch_member(uid)
        except discord.HTTPException:
            return None
    return m


async def _dash_guild(request):
    """ログイン中のユーザーが、このサーバーを管理できるかを、Discordの今の権限で毎回確認する(権限が変わればすぐ反映される)"""
    sess = _dash_session(request)
    if not sess:
        raise web.HTTPUnauthorized()
    try:
        gid = int(request.match_info["gid"])
        uid = int(sess["user"]["id"])
    except (ValueError, KeyError):
        raise web.HTTPNotFound()
    guild = bot.get_guild(gid)
    m = await _dash_member(guild, uid) if guild else None
    if not m or not _can_manage(m):
        raise web.HTTPForbidden()
    request["dash_member"] = m
    return guild


def _oauth_setup_page() -> web.Response:
    return web_page("<h1>ダッシュボードの準備ができていません</h1><p>BOTの管理者が、環境変数 <code>DISCORD_CLIENT_SECRET</code> を設定し、Developer Portal の OAuth2 > Redirects に "
                    f"<code>{_esc(DASH_BASE or 'https://(公開URL)')}/callback</code> を登録すると使えます。</p>", 503)


async def dash_index(request):
    if not OAUTH_READY:
        return _oauth_setup_page()
    if not _dash_session(request):
        gid = _valid_gid(request.query.get("g"))
        raise web.HTTPFound("/login" + (f"?g={gid}" if gid else ""))
    try:
        with open(os.path.join(BASE_DIR, "dashboard.html"), encoding="utf-8") as f:
            page = f.read()
        if 'href="/web/manage"' not in page:
            link = ('<a href="/web/manage" style="position:fixed;right:14px;top:14px;z-index:9999;padding:7px 16px;border-radius:99px;'
                    'background:#5865f2;color:#fff;text-decoration:none;font:600 13px system-ui,sans-serif">サーバー管理</a>')
            page = page.replace("</body>", link + "</body>", 1) if "</body>" in page else page + link
        return web.Response(text=page, content_type="text/html",
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex"})
    except OSError:
        return web.Response(text="dashboard.html が bot.py と同じフォルダにありません。", status=404)


async def dash_login(request):
    if not OAUTH_READY:
        return _oauth_setup_page()
    if not _rate_ok(client_ip(request)):
        return web_page("<h1>アクセスが多すぎます</h1><p>しばらく待ってからやり直してください。</p>", 429)
    gid = _valid_gid(request.query.get("g"))
    if _dash_session(request):
        raise web.HTTPFound("/" + (f"?g={gid}" if gid else ""))
    none = not request.query.get("consent")
    now = time.time()
    for k in [k for k, v in dash_states.items() if v["exp"] < now]:
        dash_states.pop(k, None)
    state = secrets.token_urlsafe(24)
    dash_states[state] = {"exp": now + 600, "g": gid, "none": none}
    q = (f"client_id={bot.application_id}&response_type=code&scope=identify&state={state}&prompt={'none' if none else 'consent'}"
         f"&redirect_uri={quote(DASH_BASE + '/callback', safe='')}")
    resp = web.HTTPFound("https://discord.com/oauth2/authorize?" + q)
    resp.set_cookie("azq_state", state, max_age=600, httponly=True, samesite="Lax", secure=_is_https(), path="/")
    raise resp


async def dash_callback(request):
    if not _rate_ok(client_ip(request)):
        return web_page("<h1>アクセスが多すぎます</h1><p>しばらく待ってからやり直してください。</p>", 429)
    state = request.query.get("state", "")
    rec = dash_states.pop(state, None)
    if not rec or rec["exp"] < time.time() or not hmac.compare_digest(request.cookies.get("azq_state", ""), state):
        return web_page("<h1>ログインの有効期限が切れました</h1><p><a href=\"/login\">もう一度ログインする</a></p>", 400)
    gq = f"&g={rec['g']}" if rec["g"] else ""
    if request.query.get("error"):
        if rec["none"]:
            raise web.HTTPFound("/login?consent=1" + gq)
        return web_page("<h1>ログインが取り消されました</h1><p><a href=\"/login?consent=1\">もう一度ログインする</a></p>", 400)
    code = request.query.get("code", "")
    if not code:
        return web_page("<h1>ログインできませんでした</h1><p><a href=\"/login\">もう一度ログインする</a></p>", 400)
    try:
        async with bot.session.post("https://discord.com/api/oauth2/token", data={
                "client_id": str(bot.application_id), "client_secret": CLIENT_SECRET, "grant_type": "authorization_code",
                "code": code, "redirect_uri": DASH_BASE + "/callback"}) as r:
            tok = (await r.json())["access_token"]
        async with bot.session.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {tok}"}) as r:
            user = await r.json()
        uid = str(int(user["id"]))
    except Exception:
        log.exception("ダッシュボードのログインに失敗(DISCORD_CLIENT_SECRET と、Redirects に登録したURLを確認してください: %s/callback)", DASH_BASE)
        return web_page("<h1>ログインに失敗しました</h1><p>BOTの管理者に連絡してください。</p>", 502)
    sid = dash_sessions.create({"id": uid, "name": user.get("global_name") or user.get("username") or uid})
    resp = web.HTTPFound("/" + (f"?g={rec['g']}" if rec["g"] else ""))
    _set_sid_cookie(resp, sid)
    resp.del_cookie("azq_state", path="/")
    raise resp


async def dash_logout(request):
    if request.method == "POST" and request.headers.get("X-Requested-With") != "azq-dashboard":
        raise web.HTTPForbidden()
    dash_sessions.delete(_dash_sid(request))
    if request.method == "POST":
        resp = web.json_response({"ok": True})
    else:
        resp = web.HTTPFound("/bye")
    resp.del_cookie("azq_sid", path="/")
    if request.method == "POST":
        return resp
    raise resp


async def dash_bye(request):
    return web_page("<h1>ログアウトしました</h1><p><a href=\"/login?consent=1\">もう一度ログインする</a></p>")


async def dash_me(request):
    sid = _dash_sid(request)
    sess = dash_sessions.get(sid)
    if not sess:
        return web.json_response({"user": None}, headers={"Cache-Control": "no-store"})
    dash_sessions.touch(sid)
    uid = int(sess["user"]["id"])
    gs = []
    for g in bot.guilds:
        m = g.get_member(uid)
        if m and _can_manage(m):
            gs.append({"id": str(g.id), "name": g.name, "icon": g.icon.url if g.icon else None})
    gs.sort(key=lambda x: x["name"].lower())
    resp = web.json_response({"user": sess["user"], "guilds": gs}, headers={"Cache-Control": "no-store"})
    _set_sid_cookie(resp, sid)
    return resp


def _s(x):
    """DiscordのIDは大きすぎてブラウザ(JavaScript)では桁が丸められるので、必ず文字列で渡す"""
    return None if x in (None, "", 0) else str(x)


def _who(g: discord.Guild, uid) -> str:
    m = g.get_member(int(uid))
    return f"{m.display_name} ({m.name})" if m else f"(退出済み) {uid}"


def _warned_list(g: discord.Guild) -> list:
    ws = store.get(g.id)["warns"]
    top = sorted(((u, len(l)) for u, l in ws.items() if l), key=lambda x: -x[1])[:50]
    return [{"id": str(u), "name": _who(g, u), "count": n} for u, n in top]


def _pending_list(g: discord.Guild) -> list:
    v, now = store.get(g.id)["verify"], time.time()
    rows = sorted(v["pending"].items(), key=lambda kv: kv[1])[:50]
    return [{"id": str(u), "name": _who(g, u), "minutes": int((now - t) // 60), "suspect": v["suspects"].get(str(u))} for u, t in rows]


def dash_snapshot(g: discord.Guild) -> dict:
    c = store.get(g.id)
    am, v, tc, kk = c["automod"], c["verify"], c["ticket"], c["kaso"]
    left = int(max(0, raid_until.get(g.id, 0) - time.time()) // 60)
    return {
        "v": 2, "gid": str(g.id), "web_ready": WEB_READY,
        "channels": [{"id": str(x.id), "name": x.name} for x in g.text_channels],
        "categories": [{"id": str(x.id), "name": x.name} for x in g.categories],
        "roles": [{"id": str(r.id), "name": r.name} for r in g.roles if not r.is_default() and not r.managed],
        "cfg": {"log_channel": _s(c["log_channel"]), "welcome_channel": _s(c["welcome"]["channel"]), "welcome_message": c["welcome"]["message"],
                **{"welcome_image_" + k: v for k, v in {**DEFAULTS["welcome"]["image"], **c["welcome"].get("image", {})}.items()
                   if k in ("enabled", "title", "subtitle", "style", "color")},
                "welcome_image_count": c["welcome"].get("image", {}).get("show_count", True),
                "welcome_image_bg": bool(c["welcome"].get("image", {}).get("bg")),
                "autorole": _s(c["autorole"]), "meigen_enabled": c["meigen"]["enabled"],
                "warn_limit": c["warn_limit"], "warn_timeout_minutes": c["warn_timeout_minutes"],
                "automod_enabled": am["enabled"], "block_invites": am["block_invites"], "ng_words": am["ng_words"],
                **{k: am[k] for k in AM_NUM}, "ignore_channels": [str(i) for i in am["ignore_channels"]],
                "ignore_roles": [str(i) for i in am["ignore_roles"]],
                "kaso_enabled": kk["enabled"], "kaso_channel": _s(kk["channel"]), "kaso_threshold": kk["threshold"]},
        "verify": {**{k: v[k] for k in ("enabled", "mode", "panel_title", "panel_text", "panel_button", "min_account_days", "kick_minutes",
                                         "max_attempts", "lockout_minutes", "violation", "bot_check", "block_default_avatar", "block_rejoin",
                                         "block_cluster", "block_vpn", "block_alt_ip", "suspect_action")},
                   "role": _s(v["role"]), "unverified_role": _s(v["unverified_role"]), "panel_channel": _s(v["panel_channel"]),
                   "stats": v["stats"], "pending": len(v["pending"]), "ips": len(v["ip_hashes"]), "raid_left": left},
        "ticket": {**{k: tc[k] for k in ("enabled", "panel_title", "panel_text", "max_open", "auto_close_hours", "ping_staff", "dm_transcript", "stats")},
                   "category": _s(tc["category"]), "transcript_channel": _s(tc["transcript_channel"]), "panel_channel": _s(tc["panel_channel"]),
                   "staff_roles": [str(i) for i in tc["staff_roles"]], "blocked": [str(i) for i in tc["blocked"]],
                   "open": sum(1 for i in tc["open"].values() if not i.get("closed"))},
        "warned": _warned_list(g), "pending_list": _pending_list(g),
        "rolepanels": [{"id": mid, "channel": str(p["channel"]), "title": p["title"], "text": p["text"], "exclusive": p["exclusive"],
                        "roles": [{"id": str(r["id"]), "label": r["label"]} for r in p["roles"]],
                        "url": f"https://discord.com/channels/{g.id}/{p['channel']}/{mid}"}
                       for mid, p in c["rolepanel"]["panels"].items()],
    }


class SettingsError(Exception):
    pass


AM_NUM = {"spam_count": (1, 100000), "spam_seconds": (1, 100000), "dup_count": (1, 100000), "mention_limit": (1, 100000),
          "strikes_to_timeout": (1, 100000), "punish_minutes": (1, 100000), "raid_joins": (1, 100000), "raid_seconds": (1, 100000)}


AM_LABEL = {"spam_count": "連投とみなす件数", "spam_seconds": "連投の判定秒数", "dup_count": "同一投稿の件数", "mention_limit": "メンション上限",
            "strikes_to_timeout": "タイムアウトまでの違反数", "punish_minutes": "タイムアウトの分数", "raid_joins": "レイド判定の参加人数", "raid_seconds": "レイド判定の秒数"}


def _num(d: dict, key: str, lo: int, hi: int, label: str, default=None) -> int:
    try:
        n = int(d[key]) if d.get(key) not in (None, "") else default
        if n is None:
            raise ValueError
    except (ValueError, TypeError):
        raise SettingsError(f"{label}は数字で入力してください")
    if not lo <= n <= hi:
        raise SettingsError(f"{label}は {lo}〜{hi} の範囲で入力してください")
    return n


def _chan(g: discord.Guild, v, kinds=(discord.TextChannel,), label="チャンネル"):
    if v in (None, "", 0, "0"):
        return None
    try:
        ch = g.get_channel(int(v))
    except (ValueError, TypeError):
        ch = None
    if not isinstance(ch, kinds):
        raise SettingsError(f"{label}が見つかりません")
    return ch


def _role(g: discord.Guild, v, label="ロール"):
    if v in (None, "", 0, "0"):
        return None
    try:
        r = g.get_role(int(v))
    except (ValueError, TypeError):
        r = None
    if r is None:
        raise SettingsError(f"{label}が見つかりません")
    return r


def apply_settings(g: discord.Guild, d: dict) -> None:
    """ダッシュボードの基本設定をサーバーに反映する(入力は必ず検証する)。不正なら SettingsError。"""
    c = store.get(g.id)
    try:
        role = None
        if d.get("autorole"):
            role = g.get_role(int(d["autorole"]))
            if (not role or role.managed or role >= g.me.top_role or any(getattr(role.permissions, n) for n in DANGEROUS_PERMS)):
                raise SettingsError("このロールは自動ロールに設定できません(権限が強い/BOTより上/管理ロール)")
        new = {
            "log": _chan(g, d.get("log_channel")), "wch": _chan(g, d.get("welcome_channel")), "kch": _chan(g, d.get("kaso_channel")),
            "wmsg": str(d.get("welcome_message", c["welcome"]["message"]))[:1500],
            "ng": [str(w).strip()[:50] for w in d.get("ng_words", []) if str(w).strip()][:100],
            "th": _num(d, "kaso_threshold", 1, 100000, "過疎アラートのしきい値", c["kaso"]["threshold"]),
            "wl": _num(d, "warn_limit", 1, 20, "警告の上限回数", c["warn_limit"]),
            "wt": _num(d, "warn_timeout_minutes", 1, 40320, "警告到達時のタイムアウト(分)", c["warn_timeout_minutes"]),
            "am": {k: _num(d, k, lo, hi, AM_LABEL[k], c["automod"][k]) for k, (lo, hi) in AM_NUM.items()},
            "ich": [ch.id for ch in (_chan(g, x, (discord.abc.GuildChannel,), "除外チャンネル") for x in d.get("ignore_channels", [])[:100]) if ch],
            "irl": [r.id for r in (_role(g, x, "除外ロール") for x in d.get("ignore_roles", [])[:100]) if r],
        }
        wi_style = str(d.get("welcome_image_style", "black"))
        if wi_style not in WELCOME_STYLES:
            raise SettingsError("ウェルカム画像のデザインが正しくありません")
        wi_title = str(d.get("welcome_image_title", "")).strip()
        if not 1 <= len(wi_title) <= 24:
            raise SettingsError("ウェルカム画像のタイトルは 1〜24 文字で入力してください")
        wi_sub = str(d.get("welcome_image_subtitle", "")).replace("\n", " ").strip()
        if len(wi_sub) > 60:
            raise SettingsError("ウェルカム画像のサブタイトルは 60 文字以内で入力してください")
        new["wi"] = {"enabled": bool(d.get("welcome_image_enabled")), "title": wi_title, "subtitle": wi_sub, "style": wi_style,
                     "color": bool(d.get("welcome_image_color")), "show_count": bool(d.get("welcome_image_count")),
                     "bg": bool(c["welcome"].get("image", {}).get("bg"))}
    except (ValueError, TypeError, AttributeError):
        raise SettingsError("入力が正しくありません")
    if new["wi"]["enabled"] and not new["wch"]:
        raise SettingsError("ウェルカム画像を使うには、ウェルカムメッセージの送信先チャンネルを選んでください")
    c["welcome"]["image"] = new["wi"]
    c["log_channel"] = new["log"].id if new["log"] else None
    c["welcome"]["channel"], c["welcome"]["message"] = (new["wch"].id if new["wch"] else None), new["wmsg"]
    c["autorole"] = role.id if role else None
    am = c["automod"]
    am["enabled"], am["block_invites"] = bool(d.get("automod_enabled")), bool(d.get("block_invites"))
    am["ng_words"] = new["ng"]
    am.update(new["am"])
    am["ignore_channels"], am["ignore_roles"] = list(dict.fromkeys(new["ich"])), list(dict.fromkeys(new["irl"]))
    c["warn_limit"], c["warn_timeout_minutes"] = new["wl"], new["wt"]
    c["kaso"]["enabled"], c["kaso"]["channel"], c["kaso"]["threshold"] = bool(d.get("kaso_enabled")), (new["kch"].id if new["kch"] else None), new["th"]
    c["meigen"]["enabled"] = bool(d.get("meigen_enabled"))
    store.save()


async def dash_get(request):
    g = await _dash_guild(request)
    return web.json_response(dash_snapshot(g))


async def dash_save(request):
    g = await _dash_guild(request)
    if request.headers.get("X-Requested-With") != "azq-dashboard":
        raise web.HTTPForbidden()
    try:
        apply_settings(g, await request.json())
    except SettingsError as e:
        raise web.HTTPBadRequest(text=str(e))
    return web.json_response({"ok": True})


def _is_dash_admin(member) -> bool:
    return isinstance(member, discord.Member) and (member.guild_permissions.administrator or member.guild_permissions.manage_guild)


def _dash_admin_member(request, g: discord.Guild) -> discord.Member:
    m = request.get("dash_member")
    if not m or not m.guild_permissions.administrator:
        raise SettingsError("この操作はサーバーの管理者(Administrator)だけが行えます。")
    return m


def _shim(g, m):
    return SimpleNamespace(guild=g, user=m)


def _text(d: dict, key: str, label: str, lo: int, hi: int) -> str:
    t = str(d.get(key, "")).replace("\\n", "\n").strip()
    if not lo <= len(t) <= hi:
        raise SettingsError(f"{label}は {lo}〜{hi} 文字で入力してください")
    return t


async def refresh_ticket_panel(guild: discord.Guild) -> bool:
    tc = store.get(guild.id)["ticket"]
    ch = guild.get_channel(tc["panel_channel"]) if tc["panel_channel"] else None
    if ch and tc["panel_message"]:
        try:
            await (await ch.fetch_message(tc["panel_message"])).edit(embed=ticket_panel_embed(tc))
            return True
        except discord.HTTPException:
            pass
    return False


async def act_verify_save(g, m, d):
    v, me, sh = store.get(g.id)["verify"], g.me, _shim(g, m)
    mode = str(d.get("mode", "button"))
    if mode not in VERIFY_MODES:
        raise SettingsError("認証方式が正しくありません")
    if mode == "web" and not WEB_READY:
        raise SettingsError("Web認証は、BOTの環境変数 WEB_URL を設定すると使えます。")
    enabled = bool(d.get("enabled"))
    role, ur = _role(g, d.get("role"), "認証ロール"), _role(g, d.get("unverified_role"), "未認証ロール")
    if enabled and not role:
        raise SettingsError("認証ロールを選んでください。")
    if role and (p := role_problem(sh, role, check_dangerous=True)):
        raise SettingsError(f"認証ロール: {p}")
    if ur:
        if role and ur.id == role.id:
            raise SettingsError("認証ロールと未認証ロールは別のロールにしてください。")
        if p := role_problem(sh, ur):
            raise SettingsError(f"未認証ロール: {p}")
    nums = {"min_account_days": _num(d, "min_account_days", 0, 365, "最低アカウント年齢"), "kick_minutes": _num(d, "kick_minutes", 0, 1440, "未認証キックの時間"),
            "max_attempts": _num(d, "max_attempts", 1, 10, "失敗の上限回数"), "lockout_minutes": _num(d, "lockout_minutes", 1, 1440, "ロック時間")}
    if d.get("violation") not in VIOLATION_MODES or d.get("suspect_action") not in ("hold", "kick"):
        raise SettingsError("処置の選択が正しくありません")
    title, text, btn = _text(d, "panel_title", "パネルのタイトル", 1, 100), _text(d, "panel_text", "パネルの説明文", 1, 1500), _text(d, "panel_button", "ボタンの名前", 1, 30)
    ch = _chan(g, d.get("panel_channel"), label="パネルのチャンネル")
    if enabled:
        if not ch:
            raise SettingsError("認証パネルを置くチャンネルを選んでください。")
        if not _can_post(ch, me):
            raise SettingsError(f"BOTが #{ch.name} で「チャンネルを見る・メッセージを送信・埋め込みリンク」を行えません。")
    was = v["enabled"]
    v.update(nums, mode=mode, role=role.id if role else None, unverified_role=ur.id if ur else None, panel_title=title, panel_text=text,
             panel_button=btn, violation=d["violation"], suspect_action=d["suspect_action"],
             **{k: bool(d.get(k)) for k in ("bot_check", "block_default_avatar", "block_rejoin", "block_cluster", "block_vpn", "block_alt_ip")})
    notes = []
    if enabled:
        v["enabled"] = True
        try:
            if v["panel_message"] and v["panel_channel"] == ch.id and not d.get("repost") and await refresh_panel(g):
                pass
            else:
                await post_panel(g, ch)
        except discord.HTTPException:
            v["enabled"] = False
            store.save()
            raise SettingsError("パネルを送信できませんでした。BOTの権限を確認してください。")
        gp = me.guild_permissions
        if not gp.manage_roles:
            notes.append("⚠️ BOTに「ロールの管理」権限がありません。認証ロールを付与できません。")
        if v["kick_minutes"] and not gp.kick_members:
            notes.append("⚠️ BOTに「メンバーをキック」権限がありません。未認証キックは動作しません。")
        if not was:
            notes.append("最後に、@everyone は認証パネル以外を見られないようにし、認証ロールに通常チャンネルの権限を付けてください。")
    else:
        v["enabled"] = False
        if was:
            v["pending"] = {}
            await delete_panel(g)
    store.save()
    return ("✅ 認証を有効にしました。" if enabled else "✅ 認証設定を保存しました。(無効です)") + (" " + " ".join(notes) if notes else "")


async def act_verify_raid(g, m, d):
    if d.get("enabled"):
        mins = _num(d, "minutes", 1, 1440, "時間(分)", 30)
        raid_until[g.id] = time.time() + mins * 60
    else:
        raid_until.pop(g.id, None)
    await send_log(g, make_embed("🚨 レイド警戒モード", f"{'ON' if d.get('enabled') else 'OFF'} / 実行者: {m} (ダッシュボード)", YELLOW if d.get("enabled") else GREEN))
    return "✅ レイド警戒モードを " + ("ON" if d.get("enabled") else "OFF") + " にしました。"


async def act_verify_clearips(g, m, d):
    v = store.get(g.id)["verify"]
    n = len(v["ip_hashes"])
    v["ip_hashes"] = {}
    store.save()
    return f"✅ 保存していたIPのハッシュ({n}件)を削除しました。"


async def act_ticket_save(g, m, d):
    tc, me = store.get(g.id)["ticket"], g.me
    enabled = bool(d.get("enabled"))
    cat = _chan(g, d.get("category"), (discord.CategoryChannel,), "カテゴリ")
    tr = _chan(g, d.get("transcript_channel"), label="記録の送信先")
    ch = _chan(g, d.get("panel_channel"), label="パネルのチャンネル")
    staff = []
    for x in (d.get("staff_roles") or [])[:10]:
        r = _role(g, x, "スタッフロール")
        if r.is_default():
            raise SettingsError("@everyone はスタッフロールにできません。")
        staff.append(r.id)
    staff = list(dict.fromkeys(staff))
    mo, ac = _num(d, "max_open", 1, 5, "同時に開けるチケット数"), _num(d, "auto_close_hours", 0, 720, "自動クローズ(時間)")
    title, text = _text(d, "panel_title", "パネルのタイトル", 1, 100), _text(d, "panel_text", "パネルの説明文", 1, 1500)
    blocked = []
    for x in (d.get("blocked") or [])[:500]:
        try:
            blocked.append(int(str(x).strip()))
        except ValueError:
            raise SettingsError(f"禁止ユーザーのIDが数字ではありません: {str(x)[:30]}")
    if tr and not _can_post(tr, me, files=True):
        raise SettingsError(f"BOTが #{tr.name} に送信・ファイル添付できません。")
    if enabled:
        if not cat or not staff or not ch:
            raise SettingsError("有効にするには、カテゴリ・スタッフロール・パネルのチャンネルを選んでください。")
        cp = cat.permissions_for(me)
        if not (cp.view_channel and cp.manage_channels):
            raise SettingsError(f"BOTが「{cat.name}」でチャンネルを管理できません。BOTに「チャンネルの管理」権限を付けてください。")
        if not _can_post(ch, me):
            raise SettingsError(f"BOTが #{ch.name} に送信できません。")
    was = tc["enabled"]
    tc.update(category=cat.id if cat else None, staff_roles=staff, transcript_channel=tr.id if tr else None, max_open=mo, auto_close_hours=ac,
              ping_staff=bool(d.get("ping_staff")), dm_transcript=bool(d.get("dm_transcript")), panel_title=title, panel_text=text,
              blocked=list(dict.fromkeys(blocked)))
    notes = []
    if enabled:
        tc["enabled"] = True
        try:
            if tc["panel_message"] and tc["panel_channel"] == ch.id and not d.get("repost") and await refresh_ticket_panel(g):
                pass
            else:
                await post_ticket_panel(g, ch)
        except discord.HTTPException:
            tc["enabled"] = False
            store.save()
            raise SettingsError("パネルを送信できませんでした。BOTの権限を確認してください。")
        gp = me.guild_permissions
        miss = [n for n, ok in (("チャンネルの管理", gp.manage_channels), ("ロールの管理", gp.manage_roles), ("ファイルを添付", gp.attach_files),
                                ("メッセージ履歴を読む", gp.read_message_history)) if not ok]
        if miss:
            notes.append("⚠️ BOTに次の権限がないと、チケット作成や記録の保存に失敗することがあります: " + " / ".join(miss))
    else:
        tc["enabled"] = False
        if was:
            await delete_ticket_panel(g)
    store.save()
    return ("✅ チケット機能を有効にしました。" if enabled else "✅ チケット設定を保存しました。(無効です)") + (" " + " ".join(notes) if notes else "")


async def act_rp_save(g, m, d):
    sh, panels = _shim(g, m), store.get(g.id)["rolepanel"]["panels"]
    mid = str(d.get("id") or "")
    old = panels.get(mid) if mid else None
    if mid and not old:
        raise SettingsError("ロールパネルが見つかりません。(削除された可能性があります)")
    title = _text({"t": d.get("title") or "🎭 ロールパネル"}, "t", "タイトル", 1, 100)
    text = _text({"t": d.get("text") or "ボタンを押して、好きなロールを受け取りましょう。"}, "t", "説明文", 1, 1500)
    roles, seen = [], set()
    for x in (d.get("roles") or [])[:RP_MAX_ROLES]:
        r = _role(g, x.get("id") if isinstance(x, dict) else None, "ロール")
        if r.id in seen:
            continue
        seen.add(r.id)
        if not (old and any(o["id"] == r.id for o in old["roles"])) and (prob := rp_role_problem(sh, r)):
            raise SettingsError(f"{r.name}: {prob}")
        roles.append({"id": r.id, "label": (str(x.get("label") or "").strip() or r.name)[:80]})
    if not roles:
        raise SettingsError("ロールを1つ以上選んでください。")
    excl = bool(d.get("exclusive"))
    if old:
        backup = copy.deepcopy(old)
        old.update(title=title, text=text, exclusive=excl, roles=roles)
        if not await refresh_role_panel(g, mid):
            old.clear()
            old.update(backup)
            raise SettingsError("パネルを更新できませんでした。(メッセージが削除されている可能性があります)")
        store.save()
        return "✅ ロールパネルを更新しました。"
    ch = _chan(g, d.get("channel"), label="パネルを置くチャンネル")
    if not ch:
        raise SettingsError("パネルを置くチャンネルを選んでください。")
    if not _can_post(ch, g.me):
        raise SettingsError(f"BOTが #{ch.name} に送信できません。")
    p = {"channel": ch.id, "title": title, "text": text, "exclusive": excl, "roles": roles}
    try:
        msg = await ch.send(embed=rp_embed(p), view=RolePanelView(roles))
    except discord.HTTPException:
        raise SettingsError("パネルを送信できませんでした。BOTの権限を確認してください。")
    panels[str(msg.id)] = p
    store.save()
    return "✅ ロールパネルを設置しました。" + ("" if g.me.guild_permissions.manage_roles else " ⚠️ BOTに「ロールの管理」権限がありません。")


async def act_rp_delete(g, m, d):
    panels = store.get(g.id)["rolepanel"]["panels"]
    mid = str(d.get("id") or "")
    p = panels.get(mid)
    if not p:
        raise SettingsError("ロールパネルが見つかりません。")
    ch = g.get_channel(p["channel"])
    if ch:
        try:
            await (await ch.fetch_message(int(mid))).delete()
        except discord.HTTPException:
            pass
    panels.pop(mid, None)
    store.save()
    return "✅ ロールパネルを削除しました。(付与済みのロールはそのままです)"


def _uid(d: dict) -> int:
    try:
        return int(str(d.get("uid", "")).strip())
    except ValueError:
        raise SettingsError("メンバーのIDが正しくありません")


def _member_view(g: discord.Guild, uid: int) -> dict:
    c = store.get(g.id)
    v, mem = c["verify"], g.get_member(uid)
    role = g.get_role(v["role"]) if v["role"] else None
    ws = c["warns"].get(str(uid), [])
    shown = [{"n": i, "reason": w["reason"], "mod": _who(g, w["mod"]), "time": w["time"]} for i, w in enumerate(ws, 1)][-30:]
    state = None
    if role:
        state = "done" if mem and role in mem.roles else ("pending" if str(uid) in v["pending"] else "none")
    return {"id": str(uid), "name": _who(g, uid), "in_guild": bool(mem), "bot": bool(mem and mem.bot), "warn_total": len(ws), "warns": shown,
            "verify": state, "suspect": v["suspects"].get(str(uid))}


async def act_member_search(g, m, d):
    q = str(d.get("q", "")).strip()[:100]
    if not q:
        raise SettingsError("名前かユーザーIDを入力してください。")
    if q.isdigit():
        found = [int(q)] if (g.get_member(int(q)) or str(int(q)) in store.get(g.id)["warns"]) else []
    else:
        ql = q.lower()
        found = [x.id for x in g.members if ql in x.name.lower() or ql in x.display_name.lower() or (x.global_name and ql in x.global_name.lower())][:20]
    if not found:
        raise SettingsError("該当するメンバーが見つかりませんでした。")
    return f"{len(found)}人見つかりました。", [_member_view(g, u) for u in found]


async def act_warn_remove(g, m, d):
    uid, n = _uid(d), _num(d, "number", 1, 10000, "警告の番号")
    ws = store.get(g.id)["warns"]
    lst = ws.get(str(uid), [])
    if n > len(lst):
        raise SettingsError("その番号の警告はありません。(すでに取り消された可能性があります)")
    removed = lst.pop(n - 1)
    if not lst:
        ws.pop(str(uid), None)
    store.save()
    await send_log(g, make_embed("↩️ Unwarn", f"{_who(g, uid)} (`{uid}`)\n実行者: {m} (ダッシュボード)\n取消した警告: {removed['reason']}", GREEN))
    return f"✅ 警告 #{n} を取り消しました。(残り {len(lst)}件)", _member_view(g, uid)


async def act_warn_clear(g, m, d):
    uid = _uid(d)
    store.get(g.id)["warns"].pop(str(uid), None)
    store.save()
    await send_log(g, make_embed("🧹 警告を消去", f"{_who(g, uid)} (`{uid}`)\n実行者: {m} (ダッシュボード)", GREEN))
    return "🧹 警告をすべて消去しました。", _member_view(g, uid)


async def act_verify_approve(g, m, d):
    uid, v = _uid(d), store.get(g.id)["verify"]
    if not v["role"]:
        raise SettingsError("認証が未設定です。(認証タブで認証ロールを選んでください)")
    mem = g.get_member(uid)
    if not mem:
        raise SettingsError("そのメンバーはサーバーにいません。")
    err = await grant_verification(g, mem, f"手動承認 by {m}(ダッシュボード)")
    if err:
        raise SettingsError(err.replace("⚠️ ", ""))
    return "✅ 認証済みにしました。", _member_view(g, uid)


async def act_verify_revoke(g, m, d):
    uid, v = _uid(d), store.get(g.id)["verify"]
    mem = g.get_member(uid)
    role = g.get_role(v["role"]) if v["role"] else None
    if not mem or not role:
        raise SettingsError("メンバーまたは認証ロールが見つかりません。")
    if err := hierarchy_error(_shim(g, m), mem):
        raise SettingsError(err)
    try:
        if role in mem.roles:
            await mem.remove_roles(role, reason=f"認証取り消し by {m}(ダッシュボード)")
        ur = g.get_role(v["unverified_role"]) if v["unverified_role"] else None
        if ur:
            await mem.add_roles(ur, reason="認証取り消し")
    except discord.HTTPException:
        raise SettingsError("ロールの操作に失敗しました。BOTの権限・ロール順位を確認してください。")
    verify_fails.pop((g.id, uid), None)
    verify_lock.pop((g.id, uid), None)
    v["pending"][str(uid)] = int(time.time())
    store.save()
    await send_log(g, make_embed("↩️ 認証取り消し", f"{mem} (`{uid}`)\n実行者: {m} (ダッシュボード)", YELLOW))
    return "↩️ 認証を取り消しました。", _member_view(g, uid)


dash_bulk_last: dict = {}


async def act_verify_bulk(g, m, d):
    v = store.get(g.id)["verify"]
    role = g.get_role(v["role"]) if v["role"] else None
    if not role:
        raise SettingsError("認証が未設定です。(認証タブで認証ロールを選んでください)")
    now = time.time()
    if now - dash_bulk_last.get(g.id, 0) < 300:
        raise SettingsError("一括承認は5分に1回までです。しばらくしてからやり直してください。")
    dash_bulk_last[g.id] = now
    targets = [x for x in g.members if not x.bot and role not in x.roles and str(x.id) not in v["pending"]
               and not (v["unverified_role"] and any(r.id == v["unverified_role"] for r in x.roles))]
    cap, done, failed = 1500, 0, 0
    for x in targets[:cap]:
        try:
            await x.add_roles(role, reason=f"AZQ BOT 一括認証 by {m}(ダッシュボード)")
            done += 1
        except discord.HTTPException:
            failed += 1
    await send_log(g, make_embed("✅ 一括認証", f"{done}人に付与 / 失敗 {failed}人\n実行者: {m} (ダッシュボード)", GREEN))
    return f"✅ {done}人に認証ロールを付与しました(失敗 {failed}人)。" + (f" 対象が多いため先頭{cap}人までです。もう一度実行してください。" if len(targets) > cap else ""), None


async def act_welcome_bg_delete(g, m, d):
    store.get(g.id)["welcome"]["image"]["bg"] = False
    store.save()
    try:
        os.remove(welcome_bg_path(g.id))
    except OSError:
        pass
    return "✅ 背景画像を削除しました。(元のグラデーションに戻ります)"


dash_wtest_last: dict = {}


async def act_welcome_test(g, m, d):
    now = time.time()
    if now - dash_wtest_last.get(g.id, 0) < 10:
        raise SettingsError("テスト送信は10秒に1回までです。")
    dash_wtest_last[g.id] = now
    ok, why = await send_welcome(m, test=True)
    if not ok:
        raise SettingsError(why)
    ch = g.get_channel(store.get(g.id)["welcome"]["channel"])
    return f"✅ テストを #{ch.name} に送信しました。" + (f" ⚠️ {why}" if why else "")


async def dash_welcome_bg(request):
    g = await _dash_guild(request)
    if request.headers.get("X-Requested-With") != "azq-dashboard":
        raise web.HTTPForbidden()
    try:
        _dash_admin_member(request, g)
        data = await request.read()
        if not data:
            raise SettingsError("画像が空です。")
        await run_heavy(save_welcome_bg, g.id, data)
    except SettingsError as e:
        raise web.HTTPBadRequest(text=str(e))
    store.get(g.id)["welcome"]["image"]["bg"] = True
    store.save()
    return web.json_response({"ok": True, "msg": "✅ 背景画像を設定しました。"})


DASH_ACTIONS = {"welcome_test": act_welcome_test, "welcome_bg_delete": act_welcome_bg_delete, "member_search": act_member_search, "warn_remove": act_warn_remove, "warn_clear": act_warn_clear,
                "verify_approve": act_verify_approve, "verify_revoke": act_verify_revoke, "verify_bulk": act_verify_bulk,
                "verify_save": act_verify_save, "verify_raid": act_verify_raid, "verify_clearips": act_verify_clearips,
                "ticket_save": act_ticket_save, "rp_save": act_rp_save, "rp_delete": act_rp_delete}


async def dash_do(request):
    g = await _dash_guild(request)
    if request.headers.get("X-Requested-With") != "azq-dashboard":
        raise web.HTTPForbidden()
    d = None
    try:
        d = await request.json()
        fn = DASH_ACTIONS.get(str(d.get("action")))
        if not fn:
            raise SettingsError("不明な操作です")
        res = await fn(g, _dash_admin_member(request, g), d)
        msg, data = res if isinstance(res, tuple) else (res, None)
    except SettingsError as e:
        raise web.HTTPBadRequest(text=str(e))
    except (ValueError, TypeError, KeyError, AttributeError):
        log.exception("ダッシュボードの操作で想定外のエラー(入力が不正、または不具合): %s", (d.get("action") if isinstance(d, dict) else None))
        raise web.HTTPBadRequest(text="入力が正しくありません")
    except discord.HTTPException:
        log.exception("ダッシュボードの操作でDiscordのエラー")
        raise web.HTTPBadGateway(text="Discordとの通信に失敗しました。BOTの権限を確認してください。")
    return web.json_response({"ok": True, "msg": msg, "snap": dash_snapshot(g), "data": data})


# ───────────────────────── /web:サーバー管理ページ(/web/manage) ─────────────────────────
# ログインは既存のダッシュボードと共通(Discordでログイン)。操作できる範囲は、Discordの管理権限ではなく
# スラッシュコマンドと同じ「役職」で毎回判定する。(サーバーの管理者でなくても、役職があれば自分の権限の範囲で使える)

SRVADM_HTML = r'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="color-scheme" content="dark light">
<title>サーバー管理 | AZQ BOT</title>
<style>
:root{color-scheme:dark light;--bg:#0b0c11;--surface:#13151d;--surface2:#1a1d28;--line:#252a38;--line2:#343b4f;--text:#eceef6;--mute:#8e95aa;--accent:#5865f2;--accent2:#7783ff;--soft:rgba(88,101,242,.16);--ok:#34d399;--danger:#ff5c6c;--warn:#f5c451;--shadow:0 10px 34px rgba(0,0,0,.45);--r:14px;--font:"Inter","Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic UI","Noto Sans JP",system-ui,-apple-system,"Segoe UI",sans-serif}
@media(prefers-color-scheme:light){:root{--bg:#f4f5fa;--surface:#fff;--surface2:#f0f2f8;--line:#e3e6ef;--line2:#cfd5e3;--text:#151823;--mute:#626a80;--accent:#4a56e2;--accent2:#3a46cc;--soft:rgba(74,86,226,.1);--ok:#0c9467;--danger:#d62c3f;--warn:#9a6f00;--shadow:0 10px 34px rgba(24,30,56,.10)}}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font:15px/1.7 var(--font);color:var(--text);background:radial-gradient(900px 420px at 8% -8%,var(--soft),transparent 62%),var(--bg);background-attachment:fixed;-webkit-font-smoothing:antialiased;padding-bottom:calc(96px + env(safe-area-inset-bottom,0px))}
a{color:var(--accent2);text-underline-offset:3px}
:focus-visible{outline:2px solid var(--accent2);outline-offset:2px;border-radius:8px}
::selection{background:var(--soft)}
h1{font-size:26px;line-height:1.3;letter-spacing:-.01em;margin:4px 0 22px;font-weight:800}
/* 上部バー */
.top{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 82%,transparent);-webkit-backdrop-filter:saturate(1.4) blur(14px);backdrop-filter:saturate(1.4) blur(14px);border-bottom:1px solid var(--line);padding-top:env(safe-area-inset-top,0px)}
.bar{max-width:1080px;margin:0 auto;padding:12px 20px;display:flex;justify-content:space-between;align-items:center;gap:14px}
.brand{display:flex;align-items:baseline;gap:10px;white-space:nowrap}
.bn{font-weight:800;letter-spacing:.04em;font-size:16px}
.bs{color:var(--mute);font-size:13px;font-weight:500}
.who{display:flex;align-items:center;gap:8px;color:var(--mute);font-size:13px;min-width:0;flex-wrap:wrap;justify-content:flex-end}
.who>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:200px;padding:4px 12px;border-radius:99px;background:var(--surface2);border:1px solid var(--line);color:var(--text);font-weight:600}
.who>span:empty{display:none}
/* レイアウト:左にナビ、右に内容 */
.shell{max-width:1080px;margin:0 auto;padding:26px 20px;display:grid;grid-template-columns:196px minmax(0,1fr);gap:32px;align-items:start}
.shell:has(#tabs.hidden){grid-template-columns:minmax(0,780px);justify-content:start}
.side{position:sticky;top:78px}
.side:has(#tabs.hidden){display:none}
.tabs{display:flex;flex-direction:column;gap:3px}
.tabs button{position:relative;display:block;width:100%;text-align:left;background:none;border:0;border-radius:10px;color:var(--mute);font:600 14px var(--font);padding:9px 14px;cursor:pointer;white-space:nowrap;transition:background .15s,color .15s}
.tabs button:hover{color:var(--text);background:var(--surface2)}
.tabs button[aria-selected=true],.tabs button.on{color:var(--text);background:var(--soft)}
.tabs button[aria-selected=true]::before,.tabs button.on::before{content:"";position:absolute;left:0;top:9px;bottom:9px;width:3px;border-radius:3px;background:var(--accent2)}
main{min-width:0;max-width:780px}
/* カード */
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:20px 24px;margin:0 0 16px;box-shadow:0 1px 0 rgba(255,255,255,.02) inset}
.card h2{font-size:15px;font-weight:700;letter-spacing:.01em;margin:0 0 4px}
.desc{color:var(--mute);font-size:13px;margin:0 0 14px;line-height:1.65}
/* 入力 */
select,input:not([type]),input[type=number],input[type=text],textarea{width:100%;background:var(--surface2);color:var(--text);border:1px solid var(--line);border-radius:10px;padding:9px 13px;font:inherit;font-size:14px;transition:border-color .15s,box-shadow .15s,background .15s}
select{appearance:none;-webkit-appearance:none;padding-right:36px;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1.5l5 5 5-5' fill='none' stroke='%238e95aa' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 13px center;cursor:pointer}
select:hover,input:hover,textarea:hover{border-color:var(--line2)}
select:focus,input:focus,textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--soft)}
textarea{resize:vertical;min-height:88px;line-height:1.6}
::placeholder{color:var(--mute);opacity:.7}
input[type=file]{color:var(--mute);font-size:13px;max-width:100%}
input[type=file]::file-selector-button{margin-right:10px;padding:7px 14px;border-radius:9px;border:1px solid var(--line2);background:var(--surface2);color:var(--text);font:600 13px var(--font);cursor:pointer}
/* ボタン */
.btn,.b{display:inline-flex;align-items:center;justify-content:center;gap:6px;background:var(--accent);color:#fff;border:1px solid transparent;border-radius:10px;padding:8px 18px;font:700 14px var(--font);cursor:pointer;text-decoration:none;transition:background .15s,border-color .15s,transform .05s,box-shadow .15s}
.btn:hover{background:var(--accent2)}
.btn:active,.b:active{transform:translateY(1px)}
.btn:disabled,.b:disabled{opacity:.5;cursor:not-allowed}
.btn.sub,.b{background:var(--surface2);border-color:var(--line);color:var(--text);padding:7px 14px;font-size:13px}
.btn.sub:hover,.b:hover{border-color:var(--line2);background:var(--line)}
.b.pri{background:var(--accent);border-color:transparent;color:#fff;padding:8px 18px;font-size:14px}
.b.pri:hover{background:var(--accent2)}
.btn.red,.b.ng{background:var(--danger);border-color:transparent;color:#fff}
.btn.red:hover,.b.ng:hover{filter:brightness(1.1);background:var(--danger)}
.b.ok{background:var(--ok);border-color:transparent;color:#06281c}
.b.ok:hover{filter:brightness(1.08);background:var(--ok)}
/* 切り替えスイッチ */
.check{display:flex;gap:12px;align-items:flex-start;padding:9px 0;cursor:pointer}
.check input{appearance:none;-webkit-appearance:none;flex:none;width:40px;height:23px;margin:1px 0 0;border-radius:99px;background:var(--line2);position:relative;cursor:pointer;transition:background .2s}
.check input::after{content:"";position:absolute;top:3px;left:3px;width:17px;height:17px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.35);transition:transform .2s}
.check input:checked{background:var(--accent)}
.check input:checked::after{transform:translateX(17px)}
.check small{display:block;color:var(--mute);font-size:12px;line-height:1.55;margin-top:1px}
/* チップ */
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}
.chip{background:var(--soft);border:1px solid transparent;color:var(--text);border-radius:99px;padding:2px 12px;font:600 13px var(--font);cursor:pointer;transition:background .15s,border-color .15s}
.chip:hover{border-color:var(--danger);background:transparent}
/* 通知・保存バー */
.msg{border-radius:12px;padding:11px 16px;margin:0 0 16px;border:1px solid var(--line);background:var(--surface2);font-size:14px}
.msg.err{border-color:var(--danger);color:var(--danger)}
.savebar{position:fixed;left:0;right:0;bottom:0;z-index:20;padding:0 16px calc(16px + env(safe-area-inset-bottom,0px));pointer-events:none}
.savebar .bar2{pointer-events:auto;max-width:780px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:14px;padding:10px 12px 10px 20px;border-radius:16px;background:color-mix(in srgb,var(--surface) 88%,transparent);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);border:1px solid var(--line2);box-shadow:var(--shadow)}
/* 保存ボタンが無い画面で、メッセージも無いときは、バーごと隠す */
.savebar:has(#saveBtn.hidden):has(#status:empty){display:none}
#status{font-size:13px;color:var(--mute);min-width:0}
#status.err{color:var(--danger)}#status.ok{color:var(--ok)}#status.dirty{color:var(--warn)}
#status a{color:var(--accent2);margin:0 4px}
.hidden{display:none!important}
footer{color:var(--mute);font-size:12px;margin:28px 0 8px}
@media(max-width:860px){
  .shell{grid-template-columns:minmax(0,1fr);gap:14px;padding:16px 14px}
  .side{position:sticky;top:57px;z-index:15;margin:0 -14px;padding:8px 14px;background:color-mix(in srgb,var(--bg) 86%,transparent);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
  .tabs{flex-direction:row;overflow-x:auto;gap:4px;scrollbar-width:none}
  .tabs::-webkit-scrollbar{display:none}
  .tabs button{width:auto;flex:0 0 auto;padding:8px 14px}
  .tabs button[aria-selected=true]::before,.tabs button.on::before{left:12px;right:12px;top:auto;bottom:2px;width:auto;height:2px}
  .bar{padding:10px 14px}.bs{display:none}
  .who{flex-wrap:nowrap;gap:6px}.who>span{display:none}.who .btn,.who select{padding:6px 11px;font-size:12px}.who select{padding-right:30px}
  .card{padding:16px 16px}
  h1{font-size:22px;margin-bottom:16px}
}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
/* サーバー管理ページ固有 */
.card h3{font-size:12px;font-weight:700;letter-spacing:.04em;margin:18px 0 8px;color:var(--mute)}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.mut{color:var(--mute);font-size:13px}
.tag{display:inline-flex;align-items:center;padding:1px 10px;border-radius:99px;background:var(--surface2);border:1px solid var(--line);font-size:12px;font-weight:600}
.tag.ok{color:var(--ok);border-color:color-mix(in srgb,var(--ok) 45%,transparent);background:color-mix(in srgb,var(--ok) 10%,transparent)}
.tag.ng{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent);background:color-mix(in srgb,var(--danger) 10%,transparent)}
.tag.wa{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 45%,transparent);background:color-mix(in srgb,var(--warn) 10%,transparent)}
form{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;align-items:end}
form label{display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:600;color:var(--mute)}
form .wide{grid-column:1/-1}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
th{color:var(--mute);font-weight:600;font-size:12px;letter-spacing:.03em}
td b{font-variant-numeric:tabular-nums}
.qa{margin:10px 0}.qa .q{font-size:12px;color:var(--mute);margin-bottom:3px}
.qa .a{white-space:pre-wrap;word-break:break-word;background:var(--surface2);border:1px solid var(--line);border-radius:10px;padding:9px 13px;font-size:14px}
.mp{position:relative;display:flex;gap:8px;flex-wrap:wrap}.mp .mq{flex:1 1 150px;width:auto}
.mr{flex:1 0 100%;display:flex;flex-wrap:wrap;gap:6px}
.mr button{border:1px solid var(--line);background:var(--surface2);color:var(--text);border-radius:99px;padding:3px 13px;cursor:pointer;font:600 13px var(--font);transition:border-color .15s}
.mr button:hover{border-color:var(--accent)}
#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);max-width:92vw;padding:11px 20px;border-radius:12px;background:var(--text);color:var(--bg);font-weight:600;font-size:14px;white-space:pre-wrap;display:none;z-index:50;box-shadow:var(--shadow)}
#toast.err{background:var(--danger);color:#fff}
.empty{color:var(--mute);padding:6px 0;font-size:14px}
.log{font-size:13px;border-bottom:1px solid var(--line);padding:8px 0;word-break:break-word;line-height:1.6}
.log:last-child{border-bottom:0}
.rank-n{display:inline-grid;place-items:center;width:26px;height:26px;border-radius:8px;background:var(--surface2);font-weight:800;font-size:13px;font-variant-numeric:tabular-nums}
.rank-n.t1{background:var(--accent);color:#fff}.rank-n.t2{background:var(--soft);color:var(--accent2)}.rank-n.t3{background:var(--soft);color:var(--accent2)}
.plus{color:var(--ok);font-weight:700}.minus{color:var(--danger);font-weight:700}
.lock{display:flex;gap:8px;align-items:center;color:var(--mute);font-size:13px;padding:2px 0}
.lock::before{content:"";flex:none;width:7px;height:7px;border-radius:50%;background:var(--warn)}
main{max-width:none}
</style>
</head>
<body>
<header class="top"><div class="bar"><div class="brand"><span class="bn">AZQ BOT</span><span class="bs">サーバー管理</span></div>
<div class="who"><select id="gsel" aria-label="サーバー" style="width:auto;max-width:46vw"></select><span id="who"></span><a class="btn sub" href="/">設定ダッシュボード</a><a href="#" id="logout" class="btn sub">ログアウト</a></div></div></header>
<div class="shell">
<aside class="side"><nav class="tabs" id="tabs" aria-label="項目"></nav></aside>
<main id="main"><div class="empty">読み込み中…</div></main>
</div>
<div id="toast"></div>
<script>
const H = {'Content-Type': 'application/json', 'X-Requested-With': 'azq-dashboard'};
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const fmt = t => t ? new Date(t * 1000).toLocaleString('ja-JP', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'}) : '';
let S = null, GID = null, TAB = 'home', PER = 'week', busy = false;
const TABS = [['home', '概要'], ['apply', '参加申請'], ['staff', 'スタッフ応募'], ['roles', 'ロール'], ['points', 'ポイント'], ['logs', '履歴・ログ'], ['admin', '役職・権限']];

function toast(msg, err) {
  const t = $('#toast');
  t.textContent = msg; t.className = err ? 'err' : ''; t.style.display = 'block';
  clearTimeout(toast.h); toast.h = setTimeout(() => t.style.display = 'none', err ? 7000 : 4000);
}
async function api(url, opt) {
  const r = await fetch(url, opt);
  if (r.status === 401) { location.href = '/login' + (GID ? '?g=' + GID : ''); throw new Error('ログインが必要です'); }
  if (!r.ok) throw new Error((await r.text()) || (r.status === 403 ? 'この操作の権限がありません。' : 'エラーが発生しました (' + r.status + ')'));
  return r.json();
}
async function load() {
  S = await api(`/api/guild/${GID}/manage`);
  render();
}
async function act(action, data) {
  if (busy) return;
  busy = true; document.body.style.cursor = 'wait';
  try {
    const r = await api(`/api/guild/${GID}/manage`, {method: 'POST', headers: H, body: JSON.stringify({action, ...data})});
    S = r.snap; render(); toast(r.msg);
  } catch (e) { toast(e.message, true); }
  finally { busy = false; document.body.style.cursor = ''; }
}

const sel = (name, list, cur, blank) => `<select name="${name}">${blank !== undefined ? `<option value="">${esc(blank)}</option>` : ''}${list.map(x => `<option value="${esc(x.id)}"${String(x.id) === String(cur) ? ' selected' : ''}>${esc(x.name)}</option>`).join('')}</select>`;
const field = (label, inner, cls) => `<label class="${cls || ''}">${esc(label)}${inner}</label>`;
const num = (name, v, ph) => `<input type="number" name="${name}" value="${esc(v ?? '')}" placeholder="${esc(ph || '')}">`;
const mp = (name = 'member') => `<div class="mp"><input type="hidden" name="${name}"><input class="mq" placeholder="名前またはIDで検索"><button type="button" class="b" data-search>検索</button><div class="mr"></div></div>`;
const form = (act, body, btn, cls) => `<form data-act="${act}" class="${cls || ''}">${body}<div class="wide"><button class="b pri">${esc(btn || '実行')}</button></div></form>`;
const rankOpts = (blank) => Object.entries(S.rank_names).sort((a, b) => b[0] - a[0]).map(([k, v]) => ({id: k, name: v + '以上'}));
const empty = t => `<div class="empty">${esc(t)}</div>`;
const lock = (k, inner) => S.can[k] ? inner : `<div class="lock">この操作は「${esc(S.rank_names[S.perms.find(p => p.key === k).need])}」以上の役職が必要です。</div>`;

function appCard(kind, a) {
  const btn = a.can
    ? `<button class="b ok" data-do="review" data-args='${esc(JSON.stringify({kind, id: a.id, approve: true}))}' data-confirm="承認して、ロールを付与します。よろしいですか?">承認</button>
       <button class="b ng" data-do="review" data-prompt="却下の理由(申請者にDMで伝わります・空でも可)" data-args='${esc(JSON.stringify({kind, id: a.id, approve: false}))}'>却下</button>`
    : `<span class="mut">審査には「${esc(a.need)}」以上の役職が必要です(自分の申請は審査できません)</span>`;
  return `<div class="card"><div class="row"><b>#${a.id}</b><span>${esc(a.name)}</span>${a.pos ? `<span class="tag">${esc(a.pos)}</span>` : ''}<span class="mut">${fmt(a.t)}</span></div>
    ${a.ans.map(([q, x]) => `<div class="qa"><div class="q">${esc(q)}</div><div class="a">${esc(x || '(未入力)')}</div></div>`).join('')}
    <div class="row" style="margin-top:8px">${btn}</div></div>`;
}
function histTable(list) {
  if (!list.length) return empty('履歴はありません。');
  return `<table><tr><th>#</th><th>申請者</th><th>結果</th><th>審査</th><th>日時</th></tr>${list.map(a =>
    `<tr><td>${a.id}</td><td>${esc(a.name)}${a.pos ? ` <span class="tag">${esc(a.pos)}</span>` : ''}</td><td><span class="tag ${a.st === 'approved' ? 'ok' : 'ng'}">${a.st === 'approved' ? '承認' : '却下'}</span>${a.why ? `<div class="mut">${esc(a.why)}</div>` : ''}</td><td>${esc(a.by || '')}</td><td>${fmt(a.rt || a.t)}</td></tr>`).join('')}</table>`;
}
const qForm = (kind, qs) => lock('rank_manage', `<form data-act="questions"><input type="hidden" name="kind" value="${kind}"><label class="wide">質問(1行に1つ・最大5つ・各45文字まで)<textarea name="questions">${esc(qs.join('\n'))}</textarea></label><div class="wide"><button class="b">質問を保存</button></div></form>`);

const VIEWS = {
  home() {
    const pj = S.apply.pending.filter(a => a.can).length, ps = S.staff.pending.filter(a => a.can).length;
    return `<div class="card"><h2>${esc(S.gname)}</h2><div class="row"><span>あなた: <b>${esc(S.me.name)}</b></span><span class="tag">${esc(S.me.rank_name)}</span></div>
      <div class="row" style="margin-top:8px"><span>審査待ちの参加申請: <b>${pj}</b>件</span><span>スタッフ応募: <b>${ps}</b>件</span></div></div>
      <div class="card"><h2>あなたができる操作</h2><table>${S.perms.map(p => `<tr><td>${esc(p.desc)}</td><td>${S.can[p.key] ? '<span class="tag ok">できる</span>' : `<span class="tag">${esc(S.rank_names[p.need])}以上</span>`}</td></tr>`).join('')}</table></div>`;
  },
  apply() {
    const a = S.apply;
    return `<div class="card"><h2>審査待ち (${a.pending.length})</h2>${a.pending.length ? '' : empty('審査待ちの申請はありません。')}</div>${a.pending.map(x => appCard('j', x)).join('')}
      <div class="card"><h2>設定 ${a.enabled ? '<span class="tag ok">受付中</span>' : '<span class="tag">停止中</span>'}</h2>${lock('rank_manage', `
        ${form('apply_setup', field('申請ボタンを置くチャンネル', sel('panel_channel', S.channels, a.panel_channel, '選択')) + field('審査チャンネル(スタッフ専用に)', sel('review_channel', S.channels, a.review_channel, '選択')) + field('承認時に付与するロール', sel('role', S.roles, a.role, '選択')) + field('却下後の再申請まで(時間)', num('cooldown_hours', a.cooldown)), a.enabled ? 'パネルを再設置して更新' : '有効化してパネルを設置')}
        ${a.enabled ? `<div class="row" style="margin-top:10px"><button class="b ng" data-do="apply_disable" data-confirm="参加申請を停止し、パネルを削除します。">受付を停止</button></div>` : ''}
        <h3>質問</h3>${qForm('j', a.questions)}`)}</div>
      <div class="card"><h2>履歴</h2>${histTable(a.history)}</div>`;
  },
  staff() {
    const a = S.staff;
    return `<div class="card"><h2>審査待ち (${a.pending.length})</h2>${a.pending.length ? '' : empty('審査待ちの応募はありません。')}</div>${a.pending.map(x => appCard('s', x)).join('')}
      <div class="card"><h2>設定 ${a.enabled ? '<span class="tag ok">募集中</span>' : '<span class="tag">停止中</span>'}</h2>${lock('rank_manage', `
        ${form('staff_setup', field('応募メニューを置くチャンネル', sel('panel_channel', S.channels, a.panel_channel, '選択')) + field('審査チャンネル(幹部以上専用に)', sel('review_channel', S.channels, a.review_channel, '選択')) + field('不合格後の再応募まで(時間)', num('cooldown_hours', a.cooldown)), a.enabled ? 'パネルを再設置して更新' : '有効化してパネルを設置')}
        ${a.enabled ? `<div class="row" style="margin-top:10px"><button class="b ng" data-do="staff_disable" data-confirm="スタッフ応募を停止し、パネルを削除します。">募集を停止</button></div>` : ''}
        <h3>募集する役職と、合格時に付与するロール</h3>
        ${a.positions.map(p => `<form data-act="staff_position" style="margin-bottom:6px"><input type="hidden" name="key" value="${esc(p.key)}">
          ${field('表示名', `<input name="label" value="${esc(p.label)}" maxlength="40">`)}${field('付与ロール', sel('role', S.roles, p.role, p.role ? '(変更しない)' : '未設定'))}
          ${field('受付', `<select name="enabled"><option value="1"${p.enabled ? ' selected' : ''}>受付する</option><option value="0"${p.enabled ? '' : ' selected'}>停止</option></select>`)}
          <div><button class="b">保存</button> <span class="mut">役職ランク: ${esc(p.rank_name)}</span></div></form>`).join('')}
        <h3>質問</h3>${qForm('s', a.questions)}`)}</div>
      <div class="card"><h2>履歴</h2>${histTable(a.history)}</div>`;
  },
  roles() {
    const slotOpts = S.slots.map(s => ({id: s.name, name: s.name}));
    return `<div class="card"><h2>登録ロール</h2>${S.slots.length ? `<table>${S.slots.map(s => `<tr><td><b>${esc(s.name)}</b></td><td>${esc(s.role_name)}</td><td>${S.can.rank_manage ? `<button class="b" data-do="role_unset" data-args='${esc(JSON.stringify({name: s.name}))}' data-confirm="登録から外します。(Discord上のロールは消えません)">外す</button>` : ''}</td></tr>`).join('')}</table>` : empty('登録されたロールはありません。')}
      ${lock('rank_manage', form('role_set', field('登録名(メンバー・情報提供者 など)', '<input name="name" maxlength="20">') + field('ロール', sel('role', S.roles, '', '選択')), '登録'))}</div>
      <div class="card"><h2>ロールの付与・剥奪</h2>${lock('role_grant', S.slots.length ? `<form data-act="role_grant">${field('メンバー', mp())}${field('ロール', sel('name', slotOpts))}${field('自動で外すまでの日数(空=外さない)', num('days', ''))}
        <div class="wide row"><button class="b pri">付与</button><button class="b ng" type="button" data-form-act="role_revoke">剥奪</button></div></form>` : empty('先にロールを登録してください。'))}
        ${S.temp_roles && S.temp_roles.length ? `<h3>期限つきの付与</h3><table>${S.temp_roles.map(t => `<tr><td>${esc(t.name)}</td><td>${esc(t.role)}</td><td>${fmt(t.exp)} まで</td></tr>`).join('')}</table>` : ''}</div>
      <div class="card"><h2>地域(都道府県)ロール</h2><div class="mut">地方 ${S.region.regions}/8・都道府県 ${S.region.prefs}/47 を登録済み ${S.region.panel ? '/ パネル設置済み' : '/ パネル未設置'}</div>
        ${lock('rank_manage', `<div class="row" style="margin:8px 0"><button class="b" data-do="region_create" data-args='{"include_prefectures":true}' data-confirm="地方8個・都道府県47個のロールを作成します(同名があれば再利用)。数十秒かかります。">ロールを作成</button></div>
        ${form('region_panel', field('選択パネルを置くチャンネル', sel('channel', S.channels, S.region.panel, '選択')), 'パネルを設置')}
        ${form('region_set_role', field('地方・都道府県', sel('name', S.region.names.map(n => ({id: n, name: n})))) + field('ロール', sel('role', S.roles, '', '選択')), '既存のロールを登録')}`)}</div>
      ${S.role_hist ? `<div class="card"><h2>ロール変更履歴</h2>${S.role_hist.length ? S.role_hist.map(h => `<div class="log"><span class="mut">${fmt(h.t)}</span> <b>${esc(h.name)}</b> ${h.add.map(x => `<span class="plus">+ ${esc(x)}</span>`).join(' ')} ${h.rem.map(x => `<span class="minus">− ${esc(x)}</span>`).join(' ')} <span class="mut">実行: ${esc(h.by)}${h.why ? ' / ' + esc(h.why) : ''}</span></div>`).join('') : empty('履歴はありません。')}</div>` : ''}`;
  },
  points() {
    const p = S.points, c = p.cfg;
    const per = [['week', '週間'], ['month', '月間'], ['total', '累計(貢献度)']];
    const rows = p.top[PER];
    return `<div class="card"><h2>ランキング</h2><div class="row">${per.map(([k, n]) => `<button class="b${PER === k ? ' pri' : ''}" data-per="${k}">${n}</button>`).join('')}
        <span class="mut">あなた: 今週 ${p.mine.week}pt / 今月 ${p.mine.month}pt / 累計 ${p.mine.total}pt</span></div>
      ${rows.length ? `<table>${rows.map((r, i) => `<tr><td><span class="rank-n${i < 3 ? ' t' + (i + 1) : ''}">${i + 1}</span></td><td>${esc(r.name)}</td><td><b>${r.pts.toLocaleString()}</b> pt</td></tr>`).join('')}</table>` : empty('まだポイントがありません。')}</div>
      <div class="card"><h2>ポイントの付与</h2>${lock('points_add', form('points_add', field('メンバー', mp()) + field('ポイント', num('amount', '', '1〜' + c.max_award)) + field('カテゴリ', sel('cat', p.cats)) + field('理由(必須)', '<input name="reason" maxlength="100">'), '付与'))}</div>
      <div class="card"><h2>ポイントの減算</h2>${lock('points_remove', form('points_remove', field('メンバー', mp()) + field('ポイント', num('amount', '')) + field('理由(必須)', '<input name="reason" maxlength="100">'), '減算'))}</div>
      <div class="card"><h2>履歴</h2>${p.log.length ? `<table><tr><th>#</th><th>日時</th><th>対象</th><th>増減</th><th>内容</th><th></th></tr>${p.log.map(e => `<tr><td>${e.id}</td><td>${fmt(e.t)}</td><td>${esc(e.name)}</td><td><b class="${e.d > 0 ? 'plus' : 'minus'}">${e.d > 0 ? '+' : ''}${e.d}</b></td><td>${esc(e.cat)} ${esc(e.why)}<div class="mut">${esc(e.by)}</div></td><td>${e.x ? '<span class="tag">取消済</span>' : (S.can.points_undo && e.cat !== '取消' ? `<button class="b" data-do="points_undo" data-args='${esc(JSON.stringify({id: e.id}))}' data-confirm="この履歴を取り消します。">取消</button>` : '')}</td></tr>`).join('')}</table>` : empty('履歴はありません。')}</div>
      <div class="card"><h2>月間MVP</h2>${p.mvp_hist.length ? p.mvp_hist.map(h => `<div class="log">${esc(h.ym)}: <b>${esc(h.name)}</b> ${h.pts.toLocaleString()}pt</div>`).join('') : empty('まだ発表されていません。')}
        ${lock('mvp', form('mvp', field('対象月(空=先月・例 2026-09)', '<input name="month" placeholder="2026-09">') + field('発表先(空=設定済み)', sel('channel', S.channels, '', '設定済みのチャンネル')), '発表する'))}</div>
      ${lock('rank_manage', `<div class="card"><h2>ポイントの設定</h2><form data-act="points_config">
        ${field('1回の付与上限', num('max_award', c.max_award))}${field('スタッフ1人の1日の付与上限', num('staff_daily_budget', c.staff_daily_budget))}${field('1人が1日に受け取れる上限', num('user_daily_cap', c.user_daily_cap))}${field('高額アラートのしきい値', num('alert_threshold', c.alert_threshold))}
        ${field('自動付与:1回(0で停止)', num('auto_points', c.auto_points))}${field('自動付与:最低文字数', num('auto_min_len', c.auto_min_len))}${field('自動付与:間隔(秒)', num('auto_cooldown', c.auto_cooldown))}${field('自動付与:1日の上限', num('auto_daily_cap', c.auto_daily_cap))}${field('自動付与:参加から(日)', num('min_member_days', c.min_member_days))}
        ${field('自動付与の対象に追加', sel('auto_channel_add', S.channels, '', '(なし)'))}${field('自動付与の対象から外す', sel('auto_channel_remove', S.channels.filter(x => p.auto_channels.includes(x.id)), '', '(なし)'))}
        ${field('MVP発表チャンネル', sel('mvp_channel', S.channels, p.mvp_channel, '(変更しない)'))}${field('MVPロール', sel('mvp_role', S.roles, p.mvp_role, '(変更しない)'))}
        ${field('毎月1日に自動発表', `<select name="mvp_auto"><option value="1"${c.mvp_auto ? ' selected' : ''}>ON</option><option value="0"${c.mvp_auto ? '' : ' selected'}>OFF</option></select>`)}
        <div class="wide"><button class="b pri">保存</button></div></form></div>`)}`;
  },
  logs() {
    if (!S.audit) return `<div class="card">${empty('履歴・ログの閲覧には「' + S.rank_names[S.perms.find(p => p.key === 'audit_view').need] + '」以上の役職が必要です。')}</div>`;
    return `<div class="card"><h2>管理ログ(直近100件)</h2>${S.audit.length ? S.audit.map(x => `<div class="log"><span class="mut">${fmt(x.t)}</span> <b>${esc(x.title)}</b> ${esc(x.text)}</div>`).join('') : empty('ログはありません。')}</div>
      <div class="card"><h2>チケット対応履歴</h2>${S.tickets.length ? S.tickets.map(x => `<div class="log"><b>#${String(x.n).padStart(4, '0')}</b> ${esc(x.owner)}${x.claimed ? ' / 担当 ' + esc(x.claimed) : ''} — ${esc(x.subject)} <span class="mut">${fmt(x.closed)} クローズ(${esc(x.by)})${x.why ? ' ' + esc(x.why) : ''}</span></div>`).join('') : empty('履歴はありません。')}</div>`;
  },
  admin() {
    const ranks = [5, 4, 3, 2, 1];
    return `<div class="card"><h2>役職とDiscordロールの対応</h2><div class="mut" style="margin-bottom:8px">サーバーオーナーとDiscordの管理者権限を持つ人は、常に管理者として扱われます。</div>
      ${lock('rank_manage', ranks.map(r => form('rank_set', `<input type="hidden" name="rank" value="${r}">` + field(S.rank_names[r], sel('role', S.roles, S.ranks[r], '未設定')), '保存')).join(''))}</div>
      <div class="card"><h2>機能ごとの必要役職</h2><table>${S.perms.map(p => `<tr><td>${esc(p.desc)}${p.changed ? ' <span class="tag wa">変更済み</span>' : ''}</td><td>${p.fixed || !S.can.rank_manage ? `<span class="tag">${esc(S.rank_names[p.need])}以上</span>` : `<form data-act="perm_set" style="display:flex;gap:6px"><input type="hidden" name="key" value="${esc(p.key)}">${sel('rank', rankOpts(), p.need)}<button class="b">変更</button></form>`}</td></tr>`).join('')}</table></div>`;
  },
};

function render() {
  if (!S) return;
  $('#who').textContent = `${S.me.name}(${S.me.rank_name})`;
  $('#tabs').innerHTML = TABS.map(([k, n]) => `<button data-tab="${k}" class="${k === TAB ? 'on' : ''}">${n}</button>`).join('');
  $('#main').innerHTML = VIEWS[TAB]();
}

function collect(f) {
  const o = {};
  for (const [k, v] of new FormData(f)) o[k] = v;
  return o;
}
document.addEventListener('submit', e => {
  const f = e.target.closest('form[data-act]');
  if (!f) return;
  e.preventDefault();
  act(f.dataset.act, collect(f));
});
document.addEventListener('click', async e => {
  const t = e.target.closest('button,a');
  if (!t) return;
  if (t.dataset.tab) { TAB = t.dataset.tab; render(); window.scrollTo(0, 0); }
  else if (t.dataset.per) { PER = t.dataset.per; render(); }
  else if (t.dataset.do) {
    if (t.dataset.confirm && !confirm(t.dataset.confirm)) return;
    const data = t.dataset.args ? JSON.parse(t.dataset.args) : {};
    if (t.dataset.prompt) { const r = prompt(t.dataset.prompt, ''); if (r === null) return; data.reason = r; }
    act(t.dataset.do, data);
  }
  else if (t.dataset.formAct) { const f = t.closest('form'); if (confirm('剥奪します。よろしいですか?')) act(t.dataset.formAct, collect(f)); }
  else if ('search' in t.dataset) {
    const box = t.closest('.mp'), q = box.querySelector('.mq').value.trim();
    if (!q) return;
    try {
      const list = await api(`/api/guild/${GID}/manage/members?q=${encodeURIComponent(q)}`);
      box.querySelector('.mr').innerHTML = list.length ? list.map(x => `<button type="button" data-pick="${esc(x.id)}" data-label="${esc(x.name)}">${esc(x.name)} · ${esc(x.rank)}</button>`).join('') : '<span class="mut">見つかりません</span>';
    } catch (err) { toast(err.message, true); }
  }
  else if (t.dataset.pick) {
    const box = t.closest('.mp');
    box.querySelector('input[type=hidden]').value = t.dataset.pick;
    box.querySelector('.mq').value = t.dataset.label;
    box.querySelector('.mr').innerHTML = `<span class="tag ok">選択: ${esc(t.dataset.label)}</span>`;
  }
  else if (t.id === 'logout') {
    e.preventDefault();
    try { await fetch('/api/logout', {method: 'POST', headers: H}); } catch (_) {}
    location.href = '/bye';
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.classList.contains('mq')) { e.preventDefault(); e.target.closest('.mp').querySelector('[data-search]').click(); }
});
$('#gsel').addEventListener('change', async e => { GID = e.target.value; history.replaceState(null, '', '?g=' + GID); try { await load(); } catch (err) { toast(err.message, true); } });

(async () => {
  try {
    const me = await api('/api/manage/guilds');
    if (!me.user) { location.href = '/login'; return; }
    if (!me.guilds.length) { $('#main').innerHTML = '<div class="card">役職を持っているサーバーがありません。管理者に、役職ロールの付与を依頼してください。</div>'; return; }
    const want = new URLSearchParams(location.search).get('g');
    GID = (me.guilds.find(g => g.id === want) || me.guilds[0]).id;
    $('#gsel').innerHTML = me.guilds.map(g => `<option value="${esc(g.id)}"${g.id === GID ? ' selected' : ''}>${esc(g.name)}</option>`).join('');
    await load();
  } catch (err) { $('#main').innerHTML = `<div class="card">${esc(err.message)}</div>`; }
})();
</script>
</body>
</html>'''


async def _srvadm_guild(request):
    """ログイン中のユーザーが、このサーバーで役職(一般スタッフ以上)を持っているかを毎回確認する"""
    sess = _dash_session(request)
    if not sess:
        raise web.HTTPUnauthorized()
    try:
        gid = int(request.match_info["gid"])
        uid = int(sess["user"]["id"])
    except (ValueError, KeyError):
        raise web.HTTPNotFound()
    guild = bot.get_guild(gid)
    m = await _dash_member(guild, uid) if guild else None
    if not m or rank_of(m) < 1:
        raise web.HTTPForbidden()
    return guild, m


def _wid(v) -> Optional[int]:
    v = str(v or "").strip()
    return int(v) if v.isdigit() and len(v) <= 20 else None


def _wint(d: dict, key: str, lo: int, hi: int, label: str, optional: bool = False) -> Optional[int]:
    v = d.get(key)
    if v is None or str(v).strip() == "":
        if optional:
            return None
        raise SrvAdmError(f"{label}を入力してください。")
    try:
        n = int(str(v).strip())
    except ValueError:
        raise SrvAdmError(f"{label}は数字で入力してください。")
    if not lo <= n <= hi:
        raise SrvAdmError(f"{label}は {lo}〜{hi} の範囲で入力してください。")
    return n


def _wbool(d: dict, key: str) -> Optional[bool]:
    v = d.get(key)
    if v in (None, ""):
        return None
    return v in (True, 1, "1", "true", "on")


def _wchannel(g: discord.Guild, d: dict, key: str, required: bool = True):
    ch = g.get_channel(_wid(d.get(key)) or 0)
    if not isinstance(ch, discord.TextChannel):
        if required:
            raise SrvAdmError("チャンネルを選んでください。")
        return None
    return ch


def _wrole(g: discord.Guild, d: dict, key: str, required: bool = True):
    r = g.get_role(_wid(d.get(key)) or 0)
    if r is None and required:
        raise SrvAdmError("ロールを選んでください。")
    return r


async def _wmember(g: discord.Guild, d: dict, key: str = "member") -> discord.Member:
    uid = _wid(d.get(key))
    m = (g.get_member(uid) or await _dash_member(g, uid)) if uid else None
    if not m:
        raise SrvAdmError("メンバーが見つかりません。検索して候補から選んでください。")
    return m


async def wa_review(g, m, d):
    kind = d.get("kind")
    if kind not in SEC:
        raise SrvAdmError("種類が正しくありません。")
    return await process_app(g, m, kind, _wint(d, "id", 1, 10 ** 9, "申請番号"), bool(d.get("approve")),
                             str(d.get("reason") or "").strip()[:300])


async def wa_rank_set(g, m, d):
    return core_rank_set(g, _wint(d, "rank", 1, 5, "役職"), _wrole(g, d, "role", False))


async def wa_perm_set(g, m, d):
    return await core_perm_set(g, m, str(d.get("key") or ""), _wint(d, "rank", 1, 5, "役職", optional=True))


async def wa_role_set(g, m, d):
    return core_role_set(g, m, str(d.get("name") or ""), _wrole(g, d, "role"))


async def wa_role_unset(g, m, d):
    return core_role_unset(g, str(d.get("name") or ""))


async def wa_role_grant(g, m, d):
    return await core_role_grant(g, m, await _wmember(g, d), str(d.get("name") or ""), _wint(d, "days", 1, 365, "日数", optional=True))


async def wa_role_revoke(g, m, d):
    return await core_role_revoke(g, m, await _wmember(g, d), str(d.get("name") or ""))


async def wa_points_add(g, m, d):
    member = await _wmember(g, d)
    ent, bal = await core_points_add(g, m, member, _wint(d, "amount", 1, 100000, "ポイント"), str(d.get("reason") or ""), str(d.get("cat") or "other"))
    return f"💰 {member.display_name} に +{ent['d']}pt を付与しました。(合計 {bal:,}pt)"


async def wa_points_remove(g, m, d):
    member = await _wmember(g, d)
    ent, bal = await core_points_remove(g, m, member, _wint(d, "amount", 1, 100000, "ポイント"), str(d.get("reason") or ""))
    return f"➖ {member.display_name} から {-ent['d']}pt を減らしました。(合計 {bal:,}pt)"


async def wa_points_undo(g, m, d):
    return await core_points_undo(g, m, _wint(d, "id", 1, 10_000_000, "履歴番号"))


async def wa_points_config(g, m, d):
    vals = {k: _wint(d, k, lo, hi, k, optional=True) for k, (lo, hi) in POINT_RANGES.items()}
    vals["mvp_auto"] = _wbool(d, "mvp_auto")
    return await core_points_config(g, m, vals, _wchannel(g, d, "mvp_channel", False), _wrole(g, d, "mvp_role", False),
                                    _wchannel(g, d, "auto_channel_add", False), _wchannel(g, d, "auto_channel_remove", False))


async def wa_mvp(g, m, d):
    return await core_mvp(g, str(d.get("month") or "").strip() or None, _wchannel(g, d, "channel", False))


async def wa_apply_setup(g, m, d):
    return await core_apply_setup(g, m, _wchannel(g, d, "panel_channel"), _wchannel(g, d, "review_channel"), _wrole(g, d, "role"),
                                  _wint(d, "cooldown_hours", 0, 720, "再申請までの時間", optional=True))


async def wa_apply_disable(g, m, d):
    return await core_apply_disable(g)


async def wa_staff_setup(g, m, d):
    return await core_staff_setup(g, _wchannel(g, d, "panel_channel"), _wchannel(g, d, "review_channel"),
                                  _wint(d, "cooldown_hours", 0, 720, "再応募までの時間", optional=True))


async def wa_staff_disable(g, m, d):
    return await core_staff_disable(g)


async def wa_staff_position(g, m, d):
    label = str(d.get("label") or "").strip()
    return await core_staff_position(g, m, str(d.get("key") or ""), _wrole(g, d, "role", False), label or None,
                                     _wbool(d, "enabled"), bool(d.get("clear_role")))


async def wa_questions(g, m, d):
    kind = d.get("kind")
    qs = d.get("questions")
    if not isinstance(qs, list):
        qs = str(qs or "").splitlines()
    return core_set_questions(g, kind, qs)


async def wa_region_create(g, m, d):
    return await core_region_create(g, bool(d.get("include_prefectures", True)))


async def wa_region_panel(g, m, d):
    return await core_region_panel(g, _wchannel(g, d, "channel"))


async def wa_region_set_role(g, m, d):
    return core_region_set_role(g, m, str(d.get("name") or ""), _wrole(g, d, "role"))


# 操作 → (処理, 必要な権限キー)。review は申請ごとに必要な役職が違うので、処理の中で確認する。
SRVADM_ACTIONS = {
    "review": (wa_review, None),
    "rank_set": (wa_rank_set, "rank_manage"), "perm_set": (wa_perm_set, "rank_manage"),
    "role_set": (wa_role_set, "rank_manage"), "role_unset": (wa_role_unset, "rank_manage"),
    "role_grant": (wa_role_grant, "role_grant"), "role_revoke": (wa_role_revoke, "role_grant"),
    "points_add": (wa_points_add, "points_add"), "points_remove": (wa_points_remove, "points_remove"),
    "points_undo": (wa_points_undo, "points_undo"), "points_config": (wa_points_config, "rank_manage"),
    "mvp": (wa_mvp, "mvp"),
    "apply_setup": (wa_apply_setup, "rank_manage"), "apply_disable": (wa_apply_disable, "rank_manage"),
    "staff_setup": (wa_staff_setup, "rank_manage"), "staff_disable": (wa_staff_disable, "rank_manage"),
    "staff_position": (wa_staff_position, "rank_manage"), "questions": (wa_questions, "rank_manage"),
    "region_create": (wa_region_create, "rank_manage"), "region_panel": (wa_region_panel, "rank_manage"),
    "region_set_role": (wa_region_set_role, "rank_manage"),
}


def srvadm_snapshot(g: discord.Guild, m: discord.Member) -> dict:
    c = lg.get(g.id)
    r = rank_of(m)
    can = {k: r >= need(g.id, k) for k in PERMS}
    pos_all = c["staff"]["positions"]

    def app_row(kind: str, a: dict, pending: bool) -> dict:
        row = {"id": a["id"], "u": str(a["u"]), "name": _who(g, a["u"]), "t": a["t"], "st": a["st"],
               "pos": pos_all.get(a.get("pos") or "", {}).get("label") if kind == "s" else None}
        if pending:
            n = review_need(g.id, kind, a)
            row.update(ans=a["ans"], need=rname(n), can=bool(r >= n and a["u"] != m.id))
        else:
            row.update(by=_who(g, a["by"]) if a.get("by") else None, rt=a.get("rt"), why=a.get("why") or "")
        return row

    def sec_snap(kind: str) -> dict:
        sec = c[SEC[kind]]
        apps = list(sec["apps"].values())
        out = {"enabled": sec["enabled"], "panel_channel": _s(sec["panel_channel"]), "review_channel": _s(sec["review_channel"]),
               "cooldown": sec["cooldown_hours"], "questions": sec["questions"],
               "pending": [app_row(kind, a, True) for a in apps if a["st"] == "pending"][:50],
               "history": [app_row(kind, a, False) for a in reversed(apps) if a["st"] in ("approved", "rejected")][:40]}
        if kind == "j":
            out["role"] = _s(sec["role"])
        else:
            out["positions"] = [{"key": k, "label": p["label"], "rank": p["rank"], "rank_name": rname(p["rank"]),
                                 "role": _s(p["role"]), "enabled": p["enabled"]} for k, p in sec["positions"].items()]
        return out

    p = c["points"]

    def top(per: str) -> list:
        return [{"id": str(x.id), "name": x.display_name, "pts": n} for x, n in ranked(g, period_totals(g.id, per))[:10]]

    mine = {per: period_totals(g.id, per).get(str(m.id), 0) for per in ("week", "month", "total")}
    entries = [e for e in p["log"] if can["points_peek"] or e["u"] == m.id][-40:]
    snap = {
        "gid": str(g.id), "gname": g.name,
        "me": {"name": m.display_name, "rank": r, "rank_name": rname(r)},
        "can": can,
        "rank_names": {str(k): v for k, v in RANK_NAMES.items()},
        "perms": [{"key": k, "desc": desc, "need": need(g.id, k), "changed": k in c["perm"], "fixed": k == "rank_manage"} for k, (_, desc) in PERMS.items()],
        "channels": [{"id": str(x.id), "name": "#" + x.name} for x in g.text_channels],
        "roles": [{"id": str(x.id), "name": x.name} for x in reversed(g.roles) if not x.is_default() and not x.managed],
        "ranks": {k: _s(v) for k, v in c["ranks"].items()},
        "slots": [{"name": n, "role": _s(rid), "role_name": (g.get_role(rid).name if g.get_role(rid) else "(削除済み)")} for n, rid in c["slots"].items()],
        "apply": sec_snap("j"), "staff": sec_snap("s"),
        "points": {"cfg": {k: p[k] for k in list(POINT_RANGES) + ["mvp_auto"]}, "mvp_channel": _s(p["mvp_channel"]), "mvp_role": _s(p["mvp_role"]),
                   "auto_channels": [str(i) for i in p["auto_channels"]],
                   "top": {per: top(per) for per in ("week", "month", "total")}, "mine": mine,
                   "log": [{"id": e["id"], "t": e["t"], "name": _who(g, e["u"]), "d": e["d"], "why": e["why"], "cat": CAT_NAMES.get(e["cat"], e["cat"]),
                            "by": _who(g, e["by"]) if e["by"] else "自動", "x": bool(e.get("x"))} for e in reversed(entries)],
                   "mvp_hist": [{"ym": h["ym"], "name": _who(g, h["u"]), "pts": h["pts"]} for h in reversed(p["mvp_hist"][-12:])],
                   "cats": [{"id": k, "name": n} for k, n in CAT_NAMES.items() if k not in ("auto", "undo")]},
        "region": {"prefs": len(c["region"]["pref"]), "regions": len(c["region"]["region"]), "panel": _s(c["region"]["panel_channel"]),
                   "names": list(REGIONS) + list(PREF_TO_REGION)},
    }
    if can["audit_view"]:
        now = time.time()
        snap["temp_roles"] = [{"name": _who(g, t["u"]), "role": (g.get_role(t["r"]).name if g.get_role(t["r"]) else "?"), "exp": int(t["exp"])}
                              for t in sorted(c["temp_roles"], key=lambda t: t["exp"])[:30] if t["exp"] > now]
        snap["role_hist"] = [{"t": x["t"], "name": _who(g, x["u"]), "by": _who(g, x["by"]) if x.get("by") else "不明", "why": x.get("why", ""),
                              "add": [(g.get_role(i).name if g.get_role(i) else str(i)) for i in x["add"]],
                              "rem": [(g.get_role(i).name if g.get_role(i) else str(i)) for i in x["rem"]]} for x in reversed(c["role_hist"][-60:])]
        snap["audit"] = [{"t": x["t"], "title": x["title"], "text": x["text"][:300]} for x in reversed(c["audit"][-100:])]
        snap["tickets"] = [{"n": x.get("n") or 0, "owner": _who(g, x["owner"]), "claimed": _who(g, x["claimed"]) if x.get("claimed") else None,
                            "subject": x.get("subject", ""), "closed": x["closed"], "by": _who(g, x["by"]) if x.get("by") else "自動", "why": x.get("why", "")}
                           for x in reversed(c["tickets"][-40:])]
    return snap


async def srvadm_index(request):
    if not OAUTH_READY:
        return _oauth_setup_page()
    if not _dash_session(request):
        gid = _valid_gid(request.query.get("g"))
        raise web.HTTPFound("/login" + (f"?g={gid}" if gid else ""))
    return web.Response(text=SRVADM_HTML, content_type="text/html",
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex"})


async def srvadm_guilds(request):
    sess = _dash_session(request)
    if not sess:
        return web.json_response({"user": None}, headers={"Cache-Control": "no-store"})
    uid = int(sess["user"]["id"])
    gs = []
    for g in bot.guilds:
        m = g.get_member(uid)
        if m and rank_of(m) >= 1:
            gs.append({"id": str(g.id), "name": g.name, "rank": rname(rank_of(m))})
    gs.sort(key=lambda x: x["name"].lower())
    return web.json_response({"user": sess["user"], "guilds": gs}, headers={"Cache-Control": "no-store"})


async def srvadm_get(request):
    g, m = await _srvadm_guild(request)
    return web.json_response(srvadm_snapshot(g, m), headers={"Cache-Control": "no-store"})


async def srvadm_members(request):
    g, m = await _srvadm_guild(request)
    q = request.query.get("q", "").strip()[:100]
    found = []
    if q.isdigit():
        x = g.get_member(int(q)) or await _dash_member(g, int(q))
        found = [x] if x else []
    elif q:
        ql = q.lower()
        found = [x for x in g.members if not x.bot and (ql in x.name.lower() or ql in x.display_name.lower()
                                                         or (x.global_name and ql in x.global_name.lower()))][:15]
    return web.json_response([{"id": str(x.id), "name": f"{x.display_name} ({x.name})", "rank": rname(rank_of(x))} for x in found],
                             headers={"Cache-Control": "no-store"})


async def srvadm_do(request):
    g, m = await _srvadm_guild(request)
    if request.headers.get("X-Requested-With") != "azq-dashboard":
        raise web.HTTPForbidden()
    d = None
    try:
        d = await request.json()
        act = str(d.get("action"))
        fn, key = SRVADM_ACTIONS.get(act, (None, None))
        if not fn:
            raise SrvAdmError("不明な操作です。")
        if key:
            need_rank(g, m, key)
        msg = await fn(g, m, d)
        if act != "review":
            await send_log(g, make_embed("🌐 Webからの操作", f"{m} (`{m.id}`) が `{act}` を実行しました。", GRAY))
    except SrvAdmError as e:
        raise web.HTTPBadRequest(text=str(e))
    except (ValueError, TypeError, KeyError, AttributeError):
        log.exception("サーバー管理ページの操作で想定外のエラー(入力が不正、または不具合): %s", (d.get("action") if isinstance(d, dict) else None))
        raise web.HTTPBadRequest(text="入力が正しくありません。")
    except discord.HTTPException:
        log.exception("サーバー管理ページの操作でDiscordのエラー")
        raise web.HTTPBadGateway(text="Discordとの通信に失敗しました。BOTの権限を確認してください。")
    return web.json_response({"ok": True, "msg": msg, "snap": srvadm_snapshot(g, m)}, headers={"Cache-Control": "no-store"})


def add_dashboard_routes(app: web.Application) -> None:
    for path in ("/", "/web", "/dashboard"):
        app.router.add_get(path, dash_index)
    app.router.add_get("/login", dash_login)
    app.router.add_get("/callback", dash_callback)
    app.router.add_get("/logout", dash_logout)
    app.router.add_get("/bye", dash_bye)
    app.router.add_post("/api/logout", dash_logout)
    app.router.add_get("/api/me", dash_me)
    app.router.add_get("/api/guild/{gid}", dash_get)
    app.router.add_post("/api/guild/{gid}", dash_save)
    app.router.add_post("/api/guild/{gid}/do", dash_do)
    app.router.add_post("/api/guild/{gid}/welcome_bg", dash_welcome_bg)
    app.router.add_get("/web/manage", srvadm_index)
    app.router.add_get("/api/manage/guilds", srvadm_guilds)
    app.router.add_get("/api/guild/{gid}/manage", srvadm_get)
    app.router.add_post("/api/guild/{gid}/manage", srvadm_do)
    app.router.add_get("/api/guild/{gid}/manage/members", srvadm_members)


@bot.tree.command(name="web", description="Webで設定・サーバー管理を操作します")
@app_commands.guild_only()
async def web_cmd(interaction: discord.Interaction):
    rk = rank_of(interaction.user)
    if not _is_dash_admin(interaction.user) and rk < 1:
        return await interaction.response.send_message("❌ サーバー管理者、または役職(一般スタッフ以上)を持つ人のみ使えます。", ephemeral=True)
    if not OAUTH_READY:
        return await interaction.response.send_message(
            "⚠️ Webダッシュボードは、このBOTでは有効になっていません。\n"
            "BOTの管理者が `DISCORD_CLIENT_SECRET` と `WEB_URL` を設定し、Developer Portal の OAuth2 > Redirects に "
            f"`{DASH_BASE or 'https://(公開URL)'}/callback` を登録すると使えます。設定は `/config` などのスラッシュコマンドでも変更できます。", ephemeral=True)
    v = discord.ui.View()
    if _is_dash_admin(interaction.user):
        v.add_item(discord.ui.Button(label="設定ダッシュボードを開く", emoji="🌐", style=discord.ButtonStyle.link, url=dash_url(interaction.guild.id)))
    if rk >= 1:
        v.add_item(discord.ui.Button(label="サーバー管理を開く", style=discord.ButtonStyle.link, url=f"{DASH_BASE}/web/manage?g={interaction.guild.id}"))
    await interaction.response.send_message(
        "🌐 下のボタンから、ブラウザで操作できます。\n"
        "Discordでログインし、権限(管理者・役職)を確認してから開きます。(一度ログインすると、ブラウザを閉じても30日間は保たれます)\n"
        "・設定ダッシュボード: サーバー管理者のみ\n・サーバー管理: 申請の審査・ロール・ポイントなど。操作できる範囲は役職ごとに決まります",
        view=v, ephemeral=True)


def web_available() -> bool:
    """/web が使える状態か"""
    return OAUTH_READY


async def _web_hint_check(interaction: discord.Interaction) -> bool:
    """設定系スラッシュコマンドの初回実行時に、Webでも操作できることを一度だけ案内する(コマンド自体は通常どおり実行)"""
    try:
        cmd = interaction.command
        root = (getattr(cmd, "root_parent", None) or cmd)
        if (root and root.name in WEB_HINT_ROOTS and web_available()
                and not user_prefs.rec(interaction.user.id).get("web_hint")):
            user_prefs.rec(interaction.user.id)["web_hint"] = True
            user_prefs.save()

            async def hint():
                await asyncio.sleep(2)
                v = discord.ui.View()
                v.add_item(discord.ui.Button(label="Webで操作する", emoji="🌐", style=discord.ButtonStyle.link, url=dash_url(interaction.guild.id)))
                try:
                    await interaction.followup.send("💡 設定は **Webダッシュボード**(`/web`)でも簡単に変更できます。"
                                                    "このままスラッシュコマンドで続けてもOKです。(この案内は一度だけ表示されます)", view=v, ephemeral=True)
                except discord.HTTPException:
                    pass
            asyncio.create_task(hint())
    except Exception:
        log.exception("Web案内の表示に失敗")
    return True


bot.tree.interaction_check = _web_hint_check


@bot.tree.command(name="help", description="AZQ BOTのコマンド一覧")
async def help_cmd(interaction: discord.Interaction):
    e = make_embed("🤖 AZQ BOT コマンド一覧")
    e.add_field(name="🛡️ 荒らし対策", value="自動で動作 (連投/同一投稿/メンション爆撃/招待リンク/NGワード/レイド検知)\n設定: `/config automod_set` `/config ngword` `/config show`", inline=False)
    e.add_field(name="📊 過疎検出", value="`/kaso` 診断 / `/config kaso` 自動アラート設定", inline=False)
    e.add_field(name="🧠 脳内メーカー", value="`/nounai [name]` / ユーザーを右クリック→アプリ→脳内メーカー", inline=False)
    e.add_field(name="🖼️ 名言画像", value="`/meigen text:名言` / メッセージを右クリック→アプリ→名言画像にする\n他の人のアイコン・名前を使うには本人の許可が必要(未設定の人にはDMで確認)。`/meigenprivacy` で自分の許可設定を変更\n管理者は `/config meigen enabled:False` でサーバー内を無効化できます", inline=False)
    e.add_field(name="👑 王様ゲーム", value="`/ousama [max_players]` 参加者を募集 → 開始で王様と番号が自動で決まる\nチャンネルに王様と参加者を表示し、各自の番号はDMで届きます(命令は自由)", inline=False)
    e.add_field(name="🏓 ping", value="`/ping` BOT速度 / `/ping target:example.com` Webサイト", inline=False)
    e.add_field(name="🔐 認証", value="`/verify setup` 設置 / `/verify set` 詳細設定 / `/verify text` パネルの文面を編集 / `/verify status` 状態\n`/verify approve` `/verify revoke` `/verify bulk_approve` `/verify raid` `/verify panel` `/verify disable`\n方式: ボタン・計算・画像CAPTCHA・Web認証(VPN/サブ垢の判定つき)、未認証ロール、アカウント年齢制限、未認証キック、レイド時の自動強化\nロボット確認の強化、疑わしいアカウント対策(デフォルトアイコン・再参加・集団参加 → 承認待ち/キック)は `/verify set` から", inline=False)
    e.add_field(name="🎫 チケット", value="`/ticketconfig setup` 設置 / `/ticketconfig set` `staff` `panel` `block` `unblock` `status` `disable`\nチケット内: `/ticket close` `/ticket add` `/ticket remove` `/ticket rename` `/ticket delete`\nクローズは作成者・スタッフ・管理者、**削除は管理者のみ**(クローズ後は閲覧のみ)\n機能: 非公開chの自動作成、担当者、記録(.txt)の保存/DM、無操作の自動クローズ、認証連携", inline=False)
    e.add_field(name="🌐 Webダッシュボード", value="`/web` でブラウザから設定を編集(設定不要・管理者のみ)", inline=False)
    e.add_field(name="🎭 ロールパネル", value="`/rolepanel create` 作成 / `/rolepanel text` 文面を編集 / `/rolepanel add` `remove` `delete` `list`\nボタンを押すとロールを付与・もう一度押すと解除。「1つだけ選択」モードあり\n(管理者のみ設定可)", inline=False)
    e.add_field(name="🔨 モデレーション", value="`/kick` `/ban` `/unban` `/timeout` `/untimeout` `/warn` `/warnings` `/unwarn` `/clearwarns` `/purge` `/slowmode` `/lock` `/unlock` `/role_add` `/role_remove`", inline=False)
    e.add_field(name="⚙️ 設定", value="`/config log_channel` `/config welcome` `/config welcome_image`(Webで設定) `/config autorole` `/config warn_limit` `/config automod_ignore` `/config show`", inline=False)
    e.add_field(name="🎖️ 役職・権限", value="`/manage rank_set` 役職とロールを対応づけ / `/manage rank_show` / `/manage perm_list` `perm_set`\n管理者>副管理者>幹部>モデレーター>一般スタッフ。機能ごとの必要役職を変更できます(Discord管理者・オーナーは常に管理者扱い)", inline=False)
    e.add_field(name="📝 申請・応募", value="`/apply setup` 参加申請 / `/staffapp setup` スタッフ応募 / `/staffapp position` 役職ごとのロール\n承認・却下はボタン(却下は理由つき)。結果はDM、承認でロール自動付与。履歴は `/apply history` `/staffapp history`", inline=False)
    e.add_field(name="🏷️ ロール管理", value="`/manage role_set` 登録 / `role_grant`(日数で自動解除) / `role_revoke` / `role_list` / `role_history`(変更履歴)\n`/region create` `/region panel` 都道府県ロール", inline=False)
    e.add_field(name="💰 ポイント", value="`/points add` `remove` `undo` `show` `history` `config` `mvp` / `/ranking` 週間・月間・累計\n付与上限・二重/相互付与の防止・自動付与(情報共有chのみ)つき", inline=False)
    e.add_field(name="📜 ログ", value="`/manage log` 管理ログ(再起動後も保存) / `/manage ticket_history` チケット対応履歴\n`/web` からブラウザでも操作できます(サーバー管理ページ)", inline=False)
    e.add_field(name="ℹ️ 情報", value="`/userinfo` `/serverinfo` `/avatar`", inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)


config_group = app_commands.Group(
    name="config", description="AZQ BOTの設定",
    default_permissions=discord.Permissions(administrator=True), guild_only=True,
)

AUTOMOD_KEYS = [
    app_commands.Choice(name="enabled (1=ON/0=OFF)", value="enabled"),
    app_commands.Choice(name="spam_count (連投とみなす件数)", value="spam_count"),
    app_commands.Choice(name="spam_seconds (連投の判定秒数)", value="spam_seconds"),
    app_commands.Choice(name="dup_count (同一投稿の件数)", value="dup_count"),
    app_commands.Choice(name="mention_limit (メンション上限)", value="mention_limit"),
    app_commands.Choice(name="block_invites (招待リンク禁止 1/0)", value="block_invites"),
    app_commands.Choice(name="strikes_to_timeout (タイムアウトまでの違反数)", value="strikes_to_timeout"),
    app_commands.Choice(name="punish_minutes (タイムアウト分数)", value="punish_minutes"),
    app_commands.Choice(name="raid_joins (レイド判定の参加人数)", value="raid_joins"),
    app_commands.Choice(name="raid_seconds (レイド判定の秒数)", value="raid_seconds"),
]


@config_group.command(name="log_channel", description="ログの送信先チャンネルを設定(省略で解除)")
@app_commands.checks.has_permissions(administrator=True)
async def cfg_log(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
    store.get(interaction.guild.id)["log_channel"] = channel.id if channel else None
    store.save()
    await interaction.response.send_message(f"✅ ログチャンネル: {channel.mention if channel else '解除'}", ephemeral=True)


@config_group.command(name="meigen", description="このサーバーで名言画像(/meigen・右クリック)を使えるか設定")
@app_commands.describe(enabled="OFFにすると、このサーバーでは名言画像を作れなくなります")
@app_commands.checks.has_permissions(administrator=True)
async def cfg_meigen(interaction: discord.Interaction, enabled: bool):
    store.get(interaction.guild.id)["meigen"]["enabled"] = enabled
    store.save()
    await interaction.response.send_message(f"✅ このサーバーの名言画像: {'有効' if enabled else '無効'}", ephemeral=True)


@config_group.command(name="welcome", description="ウェルカムメッセージを設定(channel省略で無効化)")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(message="{user} {server} {count} が使えます")
async def cfg_welcome(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None, message: Optional[str] = None):
    wc = store.get(interaction.guild.id)["welcome"]
    wc["channel"] = channel.id if channel else None
    if message:
        wc["message"] = message[:500]
    store.save()
    await interaction.response.send_message(
        f"✅ ウェルカム: {channel.mention if channel else '無効'}\n{wc['message']}\n🖼️ 画像を付けるオプションは `/web` で設定できます。", ephemeral=True,
        allowed_mentions=discord.AllowedMentions.none())


@config_group.command(name="welcome_image", description="ウェルカムメッセージの画像オプション(Webダッシュボード専用)")
@app_commands.checks.has_permissions(administrator=True)
async def cfg_welcome_image(interaction: discord.Interaction):
    if not OAUTH_READY:
        return await interaction.response.send_message(
            "🖼️ ウェルカム画像の設定は **Webダッシュボード(`/web`)専用**です。\n"
            "このBOTではダッシュボードがまだ有効になっていません。BOTの管理者が `DISCORD_CLIENT_SECRET` と `WEB_URL` を設定してください。", ephemeral=True)
    v = discord.ui.View()
    v.add_item(discord.ui.Button(label="Webで設定する", emoji="🌐", style=discord.ButtonStyle.link, url=dash_url(interaction.guild.id)))
    await interaction.response.send_message(
        "🖼️ ウェルカム画像の設定は、スラッシュコマンドではできません。\n**`/web` にアクセスして**、「基本」タブの「ウェルカムメッセージ」にある画像のオプションから設定してください。",
        view=v, ephemeral=True)


@config_group.command(name="autorole", description="参加時に自動付与するロールを設定(省略で解除)")
@app_commands.checks.has_permissions(administrator=True)
async def cfg_autorole(interaction: discord.Interaction, role: Optional[discord.Role] = None):
    if role and (role >= interaction.guild.me.top_role or role.managed or role.is_default()):
        return await interaction.response.send_message("❌ BOTがそのロールを付与できません(ロール順位を確認してください)。", ephemeral=True)
    store.get(interaction.guild.id)["autorole"] = role.id if role else None
    store.save()
    await interaction.response.send_message(f"✅ 自動ロール: {role.mention if role else '解除'}", ephemeral=True,
                                            allowed_mentions=discord.AllowedMentions.none())


@config_group.command(name="kaso", description="過疎アラートの設定(24時間のメッセージ数がしきい値未満で通知)")
@app_commands.checks.has_permissions(administrator=True)
async def cfg_kaso(interaction: discord.Interaction, enabled: bool, channel: Optional[discord.TextChannel] = None,
                   threshold: Optional[app_commands.Range[int, 1, 10000]] = None):
    k = store.get(interaction.guild.id)["kaso"]
    if enabled and not (channel or k["channel"]):
        return await interaction.response.send_message("❌ 通知先の channel を指定してください。", ephemeral=True)
    k["enabled"] = enabled
    if channel:
        k["channel"] = channel.id
    if threshold:
        k["threshold"] = threshold
    store.save()
    await interaction.response.send_message(
        f"✅ 過疎アラート: {'ON' if enabled else 'OFF'} / しきい値 {k['threshold']}件 / 通知先 <#{k['channel']}>" if k["channel"]
        else "✅ 過疎アラート: OFF", ephemeral=True)


@config_group.command(name="automod_set", description="荒らし対策の数値設定")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.choices(setting=AUTOMOD_KEYS)
async def cfg_automod(interaction: discord.Interaction, setting: app_commands.Choice[str], value: app_commands.Range[int, 0, 100000]):
    am = store.get(interaction.guild.id)["automod"]
    key = setting.value
    am[key] = bool(value) if key in ("enabled", "block_invites") else max(1, value)
    store.save()
    await interaction.response.send_message(f"✅ `{key}` = `{am[key]}`", ephemeral=True)


@config_group.command(name="ngword", description="NGワードの追加/削除/一覧")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.choices(action=[
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="remove", value="remove"),
    app_commands.Choice(name="list", value="list"),
])
async def cfg_ngword(interaction: discord.Interaction, action: app_commands.Choice[str], word: Optional[str] = None):
    words = store.get(interaction.guild.id)["automod"]["ng_words"]
    if action.value == "list":
        return await interaction.response.send_message("NGワード: " + (", ".join(f"||{w}||" for w in words) or "なし"), ephemeral=True)
    if not word:
        return await interaction.response.send_message("❌ word を指定してください。", ephemeral=True)
    if action.value == "add" and word not in words:
        words.append(word)
    elif action.value == "remove" and word in words:
        words.remove(word)
    store.save()
    await interaction.response.send_message(f"✅ {action.value}: ||{word}||", ephemeral=True)


@config_group.command(name="warn_limit", description="警告の上限回数と、到達時の自動タイムアウト時間を設定")
@app_commands.checks.has_permissions(administrator=True)
async def cfg_warn_limit(interaction: discord.Interaction, limit: app_commands.Range[int, 1, 20],
                         timeout_minutes: Optional[app_commands.Range[int, 1, 40320]] = None):
    cfg = store.get(interaction.guild.id)
    cfg["warn_limit"] = limit
    if timeout_minutes:
        cfg["warn_timeout_minutes"] = timeout_minutes
    store.save()
    await interaction.response.send_message(f"✅ 警告 {limit}回 → {cfg['warn_timeout_minutes']}分タイムアウト", ephemeral=True)


@config_group.command(name="automod_ignore", description="荒らし対策の除外チャンネル/ロールを追加・削除・一覧")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.choices(action=[
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="remove", value="remove"),
    app_commands.Choice(name="list", value="list"),
])
async def cfg_automod_ignore(interaction: discord.Interaction, action: app_commands.Choice[str],
                             channel: Optional[discord.TextChannel] = None, role: Optional[discord.Role] = None):
    am = store.get(interaction.guild.id)["automod"]
    if action.value == "list":
        chs = " ".join(f"<#{i}>" for i in am["ignore_channels"]) or "なし"
        rls = " ".join(f"<@&{i}>" for i in am["ignore_roles"]) or "なし"
        return await interaction.response.send_message(f"除外チャンネル: {chs}\n除外ロール: {rls}", ephemeral=True,
                                                       allowed_mentions=discord.AllowedMentions.none())
    if not channel and not role:
        return await interaction.response.send_message("❌ channel か role を指定してください。", ephemeral=True)
    for target, lst in ((channel, am["ignore_channels"]), (role, am["ignore_roles"])):
        if not target:
            continue
        if action.value == "add" and target.id not in lst:
            lst.append(target.id)
        elif action.value == "remove" and target.id in lst:
            lst.remove(target.id)
    store.save()
    await interaction.response.send_message(f"✅ {action.value}: {(channel or role).mention}", ephemeral=True,
                                            allowed_mentions=discord.AllowedMentions.none())


@config_group.command(name="show", description="現在の設定を表示します")
@app_commands.checks.has_permissions(administrator=True)
async def cfg_show(interaction: discord.Interaction):
    c = store.get(interaction.guild.id)
    am = c["automod"]
    ch = lambda i: f"<#{i}>" if i else "未設定"
    e = make_embed("⚙️ AZQ BOT 設定")
    e.add_field(name="ログ", value=ch(c["log_channel"]))
    e.add_field(name="ウェルカム", value=ch(c["welcome"]["channel"]))
    e.add_field(name="自動ロール", value=f"<@&{c['autorole']}>" if c["autorole"] else "未設定")
    e.add_field(name="過疎アラート", value=f"{'ON' if c['kaso']['enabled'] else 'OFF'} ({c['kaso']['threshold']}件未満) {ch(c['kaso']['channel'])}")
    e.add_field(name="警告上限", value=f"{c['warn_limit']}回 → {c['warn_timeout_minutes']}分タイムアウト")
    vf = c["verify"]
    e.add_field(name="認証", value=(f"ON ({VERIFY_MODES[vf['mode']]}) <@&{vf['role']}>" if verify_active(c) else "OFF") + "  詳細: `/verify status`")
    tk = c["ticket"]
    e.add_field(name="チケット", value=(f"ON (開いている: {len(tk['open'])}件)" if tk["enabled"] else "OFF") + "  詳細: `/ticketconfig status`")
    e.add_field(
        name="AutoMod",
        value="\n".join(f"`{k}`: {v}" for k, v in am.items() if k not in ("ng_words", "ignore_channels", "ignore_roles"))
        + f"\n`ng_words`: {len(am['ng_words'])}件 / 除外ch: {len(am['ignore_channels'])} / 除外ロール: {len(am['ignore_roles'])}",
        inline=False,
    )
    await interaction.response.send_message(embed=e, ephemeral=True)

def _describe_pid(pid: str) -> str:
    """ロックを握っているプロセスの正体(起動元のサービス名・コマンド)を調べる(Linuxのみ)"""
    info = []
    try:
        with open(f"/proc/{pid}/cgroup", encoding="utf-8") as f:
            cg = f.read().strip().splitlines()[-1]
        info.append(f"起動元: {cg.split(':', 2)[-1]}")
    except OSError:
        pass
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            info.append("コマンド: " + f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip())
    except OSError:
        pass
    return " / ".join(info)


def _single_instance_lock():
    """同じデータフォルダで BOT を2つ同時に起動しない(二重応答・設定の上書きを防ぐ)。Linux/Macのみ有効。"""
    try:
        import fcntl
    except ImportError:
        return None
    fh = open(os.path.join(DATA_DIR, "bot.lock"), "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.seek(0)
        pid = fh.read().strip()
        detail = _describe_pid(pid) if pid.isdigit() else ""
        raise SystemExit(
            "すでに別のプロセスでこのBOTが起動しています。二重起動を防ぐため終了します。\n"
            f"先に動いているプロセス: PID {pid or '不明'}" + (f"\n{detail}" if detail else "") + "\n"
            "(止め方: systemd のサービスなら systemctl stop <サービス名> / 手動起動なら kill <PID>)")
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


if __name__ == "__main__":
    if not TOKEN or TOKEN == "YOUR-TOKEN":
        raise SystemExit("トークンが設定されていません。環境変数 DISCORD_TOKEN(または bot.py 上部の TOKEN)にBOTトークンを設定してください。")
    _lock = _single_instance_lock()

    def _on_sigterm(signum, frame):
        raise SystemExit(0)
    try:
        signal.signal(signal.SIGTERM, _on_sigterm)
    except (ValueError, AttributeError):
        pass
    bot.run(TOKEN, log_handler=None)
