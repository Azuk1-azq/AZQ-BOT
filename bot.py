import asyncio
import atexit
import base64
import bisect
import copy
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
import zlib
from array import array
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional
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
DASHBOARD_URL = (os.getenv("DASHBOARD_URL") or "").rstrip("/")
DASHBOARD_PAGE = (os.getenv("DASHBOARD_PAGE") or "").strip()
PAGE_DEFAULT = "https://azuk1-azq.github.io/AZQ-BOT/dashboard.html"
PAGE_URL = DASHBOARD_PAGE or DASHBOARD_URL or PAGE_DEFAULT
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET") or ""
WEB_URL = (os.getenv("WEB_URL") or "").rstrip("/")
WEB_READY = bool(WEB_URL)
VPN_LIST_URLS = [u for u in (os.getenv("VPN_LIST_URLS") or
                             "https://raw.githubusercontent.com/X4BNet/lists_vpn/main/output/vpn/ipv4.txt,"
                             "https://raw.githubusercontent.com/X4BNet/lists_vpn/main/output/datacenter/ipv4.txt").split(",") if u.strip()]
VPN_LIST_AUTO = os.getenv("VPN_LIST_AUTO", "1") != "0"
TUNNEL_MODE = (os.getenv("AUTO_TUNNEL", "0") == "1") and not (DASHBOARD_URL and CLIENT_SECRET) and sys.platform.startswith("linux")
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
    "welcome": {"channel": None, "message": "ようこそ {user} さん！ {server} へ 🎉 (あなたは {count} 人目です)"},
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
        "block_alt_ip": False,
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
        self._lag_task = asyncio.create_task(loop_lag_monitor())
    async def close(self):
        t = getattr(self, "_tunnel_task", None)
        if t:
            t.cancel()
        if _tunnel_proc and _tunnel_proc.returncode is None:
            _tunnel_proc.terminate()
        await store.flush_async()
        if self.session:
            await self.session.close()
        if self.web_runner:
            await self.web_runner.cleanup()
        await super().close()
bot = AzqBot()
async def loop_lag_monitor():
    await bot.wait_until_ready()
    interval = 5
    while not bot.is_closed():
        t0 = time.monotonic()
        await asyncio.sleep(interval)
        lag = time.monotonic() - t0 - interval
        if lag > 1.0:
            log.warning("イベントループが約 %.1f 秒間、詰まりました。重い処理が応答を遅らせています。", lag)
async def start_web():
    async def health(_request):
        lat = bot.latency
        return web.json_response({
            "status": "ok",
            "guilds": len(bot.guilds),
            "latency_ms": None if lat != lat else round(lat * 1000),
        })
    port = PORT or (int(os.getenv("WEB_PORT") or 8080) if (DASHBOARD_URL or TUNNEL_MODE or WEB_READY) else 0)
    if not port:
        log.info("Webサーバーは無効です(PORT または DASHBOARD_URL を設定すると有効になります)")
        return
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/health", health)
    if DASHBOARD_URL and CLIENT_SECRET:
        add_dashboard_routes(app)
    elif TUNNEL_MODE:
        add_dashboard_routes(app, oauth=False)
    else:
        app.router.add_get("/", health)
    if WEB_READY:
        app.router.add_get("/v", web_verify_get)
        app.router.add_post("/v", web_verify_post)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.TCPSite(runner, "127.0.0.1" if TUNNEL_MODE else "0.0.0.0", port).start()
    except OSError as e:
        log.warning("Webサーバーを起動できませんでした(ポート %s: %s)。BOTは続行します。"
                    "すでに別のBOTプロセスが動いていないか確認してください。", port, e)
        await runner.cleanup()
        return
    bot.web_runner = runner
    if TUNNEL_MODE:
        bot._tunnel_task = asyncio.create_task(tunnel_supervisor(port))
    if WEB_READY:
        bot._vpn_task = asyncio.create_task(vpn_list_loop())
    log.info("Webサーバー起動: 0.0.0.0:%s (ダッシュボード: %s)", port, "有効" if DASHBOARD_URL and CLIENT_SECRET else "無効")
def make_embed(title: str, desc: Optional[str] = None, color: int = BLUE) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=color, timestamp=discord.utils.utcnow())
async def send_log(guild: discord.Guild, embed: discord.Embed) -> None:
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
    return None
async def try_dm(user: discord.abc.User, text: str) -> None:
    try:
        await user.send(text)
    except discord.HTTPException:
        pass
@bot.tree.error
async def on_app_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
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
async def send_welcome(member: discord.Member) -> None:
    guild = member.guild
    wc = store.get(guild.id)["welcome"]
    ch = guild.get_channel(wc["channel"]) if wc["channel"] else None
    if not ch:
        return
    text = (wc["message"].replace("{user}", member.mention)
            .replace("{server}", guild.name).replace("{count}", str(guild.member_count)))
    try:
        await ch.send(text[:2000], allowed_mentions=discord.AllowedMentions(users=[member]))
    except discord.HTTPException:
        pass
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
    await send_welcome(member)
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
async def on_ready():
    log.info("ログイン: %s (サーバー数: %d)", bot.user, len(bot.guilds))
    if getattr(bot, "_restored", False):
        return
    bot._restored = True
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
_scan_sem: Optional[asyncio.Semaphore] = None
async def measure_activity(guild: discord.Guild, hours: int = 24, per_channel: int = 500, max_channels: int = 50):
    global _scan_sem
    if _scan_sem is None:
        _scan_sem = asyncio.Semaphore(1)
    async with _scan_sem:
        return await _measure_activity(guild, hours, per_channel, max_channels)
async def _measure_activity(guild: discord.Guild, hours: int, per_channel: int, max_channels: int):
    since = discord.utils.utcnow() - timedelta(hours=hours)
    total, authors, per = 0, set(), {}
    channels = [
        c for c in guild.text_channels
        if c.permissions_for(guild.me).view_channel and c.permissions_for(guild.me).read_message_history
    ][:max_channels]
    for c in channels:
        n = 0
        try:
            async for m in c.history(after=since, limit=per_channel):
                if m.author.bot:
                    continue
                n += 1
                authors.add(m.author.id)
        except discord.HTTPException:
            continue
        if n:
            per[c] = n
            total += n
        await asyncio.sleep(0.3)
    humans = sum(1 for m in guild.members if not m.bot)
    return total, len(authors), humans, per
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
    e.set_footer(text="※ BOTが閲覧可能なチャンネルのみ・1chあたり最大500件まで集計 / BOT発言は除外")
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
@bot.tree.command(name="kick", description="メンバーをキックします")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.describe(delete_days="過去何日分のメッセージを削除するか(0〜7)")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.describe(minutes="分(1〜40320 = 28日)")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(moderate_members=True)
@app_commands.guild_only()
async def untimeout(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None, reason=f"{interaction.user}")
    await interaction.response.send_message(f"🔊 {member.mention} のタイムアウトを解除しました。")
@bot.tree.command(name="warn", description="メンバーに警告を与えます(規定回数で自動タイムアウト)")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def warnings(interaction: discord.Interaction, member: discord.Member):
    lst = store.get(interaction.guild.id)["warns"].get(str(member.id), [])
    if not lst:
        return await interaction.response.send_message(f"{member} に警告はありません。", ephemeral=True)
    start = max(0, len(lst) - 15)
    lines = [f"`{i}.` <t:{w['time']}:d> {w['reason']} (by <@{w['mod']}>)" for i, w in enumerate(lst[start:], start + 1)]
    await interaction.response.send_message(embed=make_embed(f"⚠️ {member} の警告 ({len(lst)}件)", "\n".join(lines), YELLOW), ephemeral=True)
@bot.tree.command(name="clearwarns", description="メンバーの警告をすべて消去します")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def clearwarns(interaction: discord.Interaction, member: discord.Member):
    store.get(interaction.guild.id)["warns"].pop(str(member.id), None)
    store.save()
    await interaction.response.send_message(f"🧹 {member} の警告を消去しました。")
@bot.tree.command(name="unwarn", description="警告を1件取り消します(番号は /warnings で確認)")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def unwarn(interaction: discord.Interaction, member: discord.Member, number: app_commands.Range[int, 1, 10000]):
    lst = store.get(interaction.guild.id)["warns"].get(str(member.id), [])
    if number > len(lst):
        return await interaction.response.send_message("❌ その番号の警告はありません。`/warnings` で確認してください。", ephemeral=True)
    removed = lst.pop(number - 1)
    if not lst:
        store.get(interaction.guild.id)["warns"].pop(str(member.id), None)
    store.save()
    await interaction.response.send_message(f"✅ {member.mention} の警告
                                            allowed_mentions=discord.AllowedMentions.none())
    await send_log(interaction.guild, make_embed("↩️ Unwarn", f"{member} (`{member.id}`)\n実行者: {interaction.user}\n取消した警告: {removed['reason']}", GREEN))
@bot.tree.command(name="purge", description="メッセージを一括削除します")
@app_commands.describe(amount="削除件数(1〜100)", member="このメンバーのメッセージのみ削除")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(manage_messages=True, read_message_history=True)
@app_commands.guild_only()
async def purge(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100], member: Optional[discord.Member] = None):
    await interaction.response.defer(ephemeral=True)
    check = (lambda m: m.author.id == member.id) if member else None
    deleted = await interaction.channel.purge(limit=amount, check=check)
    await interaction.followup.send(f"🧹 {len(deleted)}件削除しました。", ephemeral=True)
    await send_log(interaction.guild, make_embed("🧹 Purge", f"{interaction.channel.mention} で {len(deleted)}件削除\n実行者: {interaction.user}", GRAY))
@bot.tree.command(name="slowmode", description="チャンネルの低速モードを設定します(0で解除)")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(manage_channels=True)
@app_commands.guild_only()
async def slowmode(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message("🐢 低速モードを解除しました。" if seconds == 0 else f"🐢 低速モードを {seconds}秒 に設定しました。")
@bot.tree.command(name="lock", description="このチャンネルを@everyoneの発言禁止にします")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(manage_roles=True, manage_channels=True)
@app_commands.guild_only()
async def lock(interaction: discord.Interaction):
    ch, role = interaction.channel, interaction.guild.default_role
    ow = ch.overwrites_for(role)
    ow.send_messages = False
    await ch.set_permissions(role, overwrite=ow, reason=f"lock by {interaction.user}")
    await interaction.response.send_message("🔒 チャンネルをロックしました。")
@bot.tree.command(name="unlock", description="チャンネルのロックを解除します")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.guild_only()
async def role_add(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await _role_change(interaction, member, role, True)
@bot.tree.command(name="role_remove", description="メンバーからロールを剥奪します")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
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
@bot.tree.command(name="avatar", description="アイコン画像を表示します")
async def avatar(interaction: discord.Interaction, user: Optional[discord.User] = None):
    u = user or interaction.user
    e = make_embed(f"🖼️ {u} のアイコン")
    e.set_image(url=u.display_avatar.replace(size=1024).url)
    await interaction.response.send_message(embed=e)
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
    def __init__(self):
        self.starts, self.ends = array("L"), array("L")
    def load(self, lines) -> int:
        spans = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("
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
    addr = ipaddress.ip_address(ip)
    key = str(ipaddress.ip_network(f"{ip}/64", strict=False)) if addr.version == 6 else ip
    return hmac.new(_ip_salt(), key.encode(), hashlib.sha256).hexdigest()[:20]
WEB_TTL = 600
web_nonces: dict = {}
web_rate: dict = defaultdict(deque)
def make_web_link(guild_id: int, user_id: int) -> str:
    now = time.time()
    for k in [k for k, r in web_nonces.items() if r["exp"] < now]:
        web_nonces.pop(k, None)
    n = secrets.token_urlsafe(18)
    web_nonces[n] = {"g": guild_id, "u": user_id, "cookie": secrets.token_urlsafe(16), "exp": now + WEB_TTL}
    return f"{WEB_URL}/v?t={n}"
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
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&
def web_page(body: str, status: int = 200) -> web.Response:
    html = ("<!DOCTYPE html><html lang=\"ja\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<meta name=\"robots\" content=\"noindex\"><title>認証</title><style>:root{--bg:
            "@media(prefers-color-scheme:dark){:root{--bg:
            "body{margin:0;font:15px/1.7 system-ui,'Hiragino Sans','Noto Sans JP',sans-serif;background:var(--bg);color:var(--text);display:grid;place-items:center;min-height:100vh;padding:16px;box-sizing:border-box}"
            ".card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px;max-width:480px;width:100%}h1{font-size:18px;margin:0 0 12px}.sub{color:var(--sub);font-size:13px}"
            "button{background:var(--pri);color:
            f"<body><div class=\"card\">{body}</div></body></html>")
    return web.Response(text=html, status=status, content_type="text/html",
                        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex", "Referrer-Policy": "no-referrer"})
def _web_expired() -> web.Response:
    return web_page("<h1>リンクが無効です</h1><p>有効期限が切れたか、すでに使用されています。Discordの認証パネルから、もう一度ボタンを押してください。</p>", 400)
def web_disclosure(v: dict) -> str:
    items = []
    if v["block_vpn"]:
        items.append("VPN・プロキシ・データセンターの回線でないかの確認(公開されているIPの一覧と照合するだけで、IPは外部に送りません)")
    if v["block_alt_ip"]:
        items.append("同じ回線から別のアカウントが認証していないかの確認(IPアドレスはそのまま保存せず、元に戻せない値(ハッシュ)にして保存します)")
    if not items:
        return "<p class=\"sub\">・ロボットでないことの確認だけを行います。IPアドレスは保存しません。</p>"
    return "<p class=\"sub\">このサーバーでは、次の確認のために接続元のIPアドレスを一時的に使います。<br>" + "<br>".join("・" + i for i in items) + "<br>・生のIPアドレスは保存しません。</p>"
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
    resp = web_page(f"<h1>🔐 {_esc(guild.name)} の認証</h1><p>下のボタンを押すと、認証が完了します。</p>{web_disclosure(v)}"
                    f"<form method=\"POST\" action=\"/v\"><input type=\"hidden\" name=\"t\" value=\"{_esc(t)}\"><button type=\"submit\">認証する</button></form>")
    resp.set_cookie("azq_v", rec["cookie"], max_age=WEB_TTL, httponly=True, samesite="Lax")
    return resp
async def web_verify_post(request):
    ip_s = client_ip(request)
    if not _rate_ok(ip_s):
        return web_page("<h1>アクセスが多すぎます</h1><p>しばらく待ってからやり直してください。</p>", 429)
    form = await request.post()
    rec = web_nonces.pop(str(form.get("t", "")), None)
    if not rec or rec["exp"] < time.time() or request.cookies.get("azq_v") != rec["cookie"]:
        return _web_expired()
    guild = bot.get_guild(rec["g"])
    member = guild.get_member(rec["u"]) if guild else None
    if not guild or not member:
        return web_page("<h1>確認できません</h1><p>サーバーに参加しているか確認してください。</p>", 400)
    cfg = store.get(guild.id)
    v = cfg["verify"]
    if not verify_active(cfg):
        return web_page("<h1>認証は現在利用できません</h1>", 400)
    if str(member.id) not in v["pending"]:
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
            users = v["ip_hashes"].setdefault(h, [])
            others = [u for u in users if u != uid]
            if uid not in users:
                users.append(uid)
            _cap(v["ip_hashes"], 5000)
            if others:
                reason = "同じ回線から別のアカウントが認証済み(サブ垢の疑い)"
                v["suspects"][uid] = reason
                v["stats"]["denied"] += 1
                store.save()
                kick = v["suspect_action"] == "kick"
                await send_log(guild, make_embed("🛡️ " + ("サブ垢の疑いでキック" if kick else "サブ垢の疑い(認証を保留)"),
                                                 f"{member.mention} (`{member.id}`)\n同じ回線で認証済み: " + " ".join(f"<@{u}>" for u in others[:5])
                                                 + ("" if kick else "\n家族・学校など同じ回線の別人の場合は `/verify approve` で承認できます。"), YELLOW))
                if kick:
                    await kick_for_verify(member, reason)
                    return web_page("<h1>認証できませんでした</h1>", 403)
                return web_page("<h1>🛡️ 管理者の承認待ちです</h1><p>確認が必要なため、サーバー管理者の承認をお待ちください。</p>")
            store.save()
    err = await grant_verification(guild, member, "Web認証")
    if err:
        return web_page(f"<h1>認証できませんでした</h1><p>{_esc(err)}</p>", 500)
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
    reasons = []
    if v["block_default_avatar"] and is_default_avatar(member):
        reasons.append("デフォルトアイコンのまま")
    if r := v["suspects"].get(str(member.id)):
        reasons.append(r)
    return reasons
def detect_join_suspects(member: discord.Member, v: dict) -> list:
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
        view = discord.ui.View(timeout=WEB_TTL)
        view.add_item(discord.ui.Button(label="Webで認証する", emoji="🌐", style=discord.ButtonStyle.link, url=make_web_link(guild.id, member.id)))
        return await interaction.response.send_message("🌐 下のボタンを開いて、ページの指示に従ってください。\n(10分間有効・あなた専用のリンクです。他の人に共有しないでください)",
                                                       view=view, ephemeral=True)
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
    e.add_field(name="Web認証", value=("準備OK" if WEB_READY else "未設定(WEB_URL)") + f" / VPN判定 {onoff(v['block_vpn'])}(リスト{len(vpn_ranges.starts)}件) / 同一回線の判定 {onoff(v['block_alt_ip'])}", inline=False)
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
        f"
        f"
        f"
        f"
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
    await lock_ticket_channel(channel)
    data = None
    try:
        data = await build_transcript(channel, info)
    except discord.HTTPException:
        log.warning("トランスクリプト作成に失敗 guild=%s channel=%s", guild.id, channel.id)
    name = f"ticket-{info['number']:04d}"
    owner = guild.get_member(info["owner"])
    e = make_embed(f"🔒 チケット
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
            await owner.send(f"**{guild.name}** のチケット
                             file=discord.File(io.BytesIO(data), filename=f"{name}.txt"))
        except discord.HTTPException:
            pass
    ce = make_embed(f"🔒 チケット
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
                                    f"
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
    e = make_embed(f"🎫 チケット
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
    e.add_field(name="カテゴリ", value=f"<
    e.add_field(name="スタッフ", value=" ".join(f"<@&{i}>" for i in tc["staff_roles"]) or "なし")
    e.add_field(name="記録の送信先", value=f"<
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
            lines.append(f"<
        e.add_field(name=f"開いているチケット ({len(opened)})", value="\n".join(lines), inline=False)
    if closed:
        e.add_field(name=f"クローズ済み・削除待ち ({len(closed)})",
                    value="\n".join(f"<
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
        name = f"{p['title'][:55]} (
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
@web.middleware
async def cors_middleware(request, handler):
    src = DASHBOARD_PAGE or (PAGE_URL if TUNNEL_MODE else "")
    p = urlparse(src) if src else None
    origin = f"{p.scheme}://{p.netloc}" if p else ""
    hdr = {}
    if origin and request.headers.get("Origin") == origin:
        hdr = {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Requested-With",
               "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Max-Age": "600", "Vary": "Origin"}
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=hdr)
    try:
        resp = await handler(request)
    except web.HTTPException as e:
        e.headers.update(hdr)
        raise
    resp.headers.update(hdr)
    return resp
dash_sessions: dict = {}
dash_states: dict = {}
DASH_TTL = 12 * 3600
WEB_HINT_ROOTS = {"config", "verify", "ticketconfig", "rolepanel"}
def _dash_sid(request) -> str:
    auth = request.headers.get("Authorization", "")
    return auth[7:] if auth.startswith("Bearer ") else request.cookies.get("azq_sid", "")
def _dash_session(request):
    sess = dash_sessions.get(_dash_sid(request))
    if sess and sess["exp"] > time.time():
        return sess
    return None
async def _dash_guild(request):
    sess = _dash_session(request)
    if not sess:
        raise web.HTTPUnauthorized()
    try:
        gid = int(request.match_info["gid"])
    except ValueError:
        raise web.HTTPNotFound()
    guild = bot.get_guild(gid)
    perms = sess["guilds"].get(gid)
    if not guild or perms is None or not (perms & 0x8 or perms & 0x20):
        raise web.HTTPForbidden()
    return guild
async def dash_index(request):
    try:
        with open(os.path.join(BASE_DIR, "dashboard.html"), encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html")
    except OSError:
        return web.Response(text="dashboard.html が bot.py と同じフォルダにありません。", status=404)
async def dash_login(request):
    state = secrets.token_urlsafe(24)
    dash_states[state] = time.time() + 600
    q = (f"client_id={bot.application_id}&response_type=code&scope=identify%20guilds&state={state}"
         f"&redirect_uri={quote(DASHBOARD_URL + '/callback', safe='')}")
    raise web.HTTPFound("https://discord.com/oauth2/authorize?" + q)
async def dash_callback(request):
    state, code = request.query.get("state", ""), request.query.get("code", "")
    if dash_states.pop(state, 0) < time.time() or not code:
        return web.Response(text="ログインの有効期限が切れました。もう一度お試しください。", status=400)
    try:
        async with bot.session.post("https://discord.com/api/oauth2/token", data={
                "client_id": str(bot.application_id), "client_secret": CLIENT_SECRET, "grant_type": "authorization_code",
                "code": code, "redirect_uri": DASHBOARD_URL + "/callback"}) as r:
            tok = (await r.json())["access_token"]
        hd = {"Authorization": f"Bearer {tok}"}
        async with bot.session.get("https://discord.com/api/users/@me", headers=hd) as r:
            user = await r.json()
        async with bot.session.get("https://discord.com/api/users/@me/guilds", headers=hd) as r:
            guilds = await r.json()
    except Exception:
        log.exception("ダッシュボードのログインに失敗")
        return web.Response(text="ログインに失敗しました。", status=502)
    sid = secrets.token_urlsafe(32)
    dash_sessions[sid] = {"exp": time.time() + DASH_TTL, "user": {"id": user["id"], "name": user.get("global_name") or user["username"]},
                          "guilds": {int(g["id"]): int(g["permissions"]) for g in guilds}}
    if DASHBOARD_PAGE:
        raise web.HTTPFound(DASHBOARD_PAGE + "
    resp = web.HTTPFound("/")
    resp.set_cookie("azq_sid", sid, max_age=DASH_TTL, httponly=True, samesite="Lax", secure=DASHBOARD_URL.startswith("https"))
    raise resp
async def dash_logout(request):
    dash_sessions.pop(_dash_sid(request), None)
    if request.method == "POST":
        return web.json_response({"ok": True})
    raise web.HTTPFound(PAGE_URL or "/")
async def dash_me(request):
    sess = _dash_session(request)
    if not sess:
        return web.json_response({"user": None})
    gs = [{"id": str(g.id), "name": g.name} for g in bot.guilds
          if (p := sess["guilds"].get(g.id)) is not None and (p & 0x8 or p & 0x20)]
    return web.json_response({"user": sess["user"], "guilds": gs})
TUNNEL_URL = ""
TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
MAGIC_TTL = 3 * 3600
_tunnel_proc = None
def tunnel_url_from_line(line: str) -> str:
    for m in TUNNEL_RE.finditer(line):
        if m.group(0) != "https://api.trycloudflare.com":
            return m.group(0)
    return ""
async def _ensure_cloudflared() -> Optional[str]:
    arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower())
    if not arch:
        return None
    path = os.path.join(DATA_DIR, "cloudflared")
    if os.path.exists(path) and os.path.getsize(path) > 10_000_000:
        return path
    log.info("cloudflared をダウンロードします(初回のみ)")
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}"
    async with bot.session.get(url, timeout=aiohttp.ClientTimeout(total=600)) as r:
        if r.status != 200:
            raise RuntimeError(f"ダウンロード失敗 HTTP {r.status}")
        with open(path + ".part", "wb") as f:
            async for chunk in r.content.iter_chunked(1 << 20):
                f.write(chunk)
    os.chmod(path + ".part", 0o755)
    os.replace(path + ".part", path)
    return path
async def tunnel_supervisor(port: int) -> None:
    global TUNNEL_URL, _tunnel_proc
    delay = 5
    while True:
        try:
            path = await _ensure_cloudflared()
            if not path:
                log.info("この環境ではトンネルの自動起動に対応していません(/web はコード方式になります)")
                return
            _tunnel_proc = await asyncio.create_subprocess_exec(
                path, "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
            tail = deque(maxlen=12)
            async for raw in _tunnel_proc.stderr:
                line = raw.decode("utf-8", "replace").strip()
                tail.append(line[:300])
                url = tunnel_url_from_line(line)
                if url and url != TUNNEL_URL:
                    TUNNEL_URL, delay = url, 5
                    log.info("Webダッシュボードの接続先: %s", url)
            await _tunnel_proc.wait()
            log.warning("cloudflared が終了しました(コード %s)。%s秒後に再起動します。最後の出力:\n%s",
                        _tunnel_proc.returncode, delay, "\n".join(tail) or "(出力なし)")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("トンネルの起動に失敗しました。%s秒後にやり直します", delay)
        TUNNEL_URL = ""
        await asyncio.sleep(delay)
        delay = min(delay * 2, 300)
def dash_snapshot(g: discord.Guild) -> dict:
    c = store.get(g.id)
    return {
        "v": 1, "gid": str(g.id),
        "channels": [{"id": str(x.id), "name": x.name} for x in g.text_channels],
        "roles": [{"id": str(r.id), "name": r.name} for r in g.roles if not r.is_default() and not r.managed],
        "cfg": {"log_channel": c["log_channel"], "welcome_channel": c["welcome"]["channel"], "welcome_message": c["welcome"]["message"],
                "autorole": c["autorole"], "automod_enabled": c["automod"]["enabled"], "block_invites": c["automod"]["block_invites"],
                "ng_words": c["automod"]["ng_words"], "kaso_enabled": c["kaso"]["enabled"], "kaso_channel": c["kaso"]["channel"],
                "kaso_threshold": c["kaso"]["threshold"], "meigen_enabled": c["meigen"]["enabled"]}}
class SettingsError(Exception):
    pass
def apply_settings(g: discord.Guild, d: dict) -> None:
    c = store.get(g.id)
    def chan(v):
        if v in (None, "", 0):
            return None
        v = int(v)
        if not g.get_channel(v):
            raise SettingsError("存在しないチャンネルです")
        return v
    try:
        role = None
        if d.get("autorole"):
            role = g.get_role(int(d["autorole"]))
            if (not role or role.managed or role >= g.me.top_role or any(getattr(role.permissions, n) for n in DANGEROUS_PERMS)):
                raise SettingsError("このロールは自動ロールに設定できません(権限が強い/BOTより上/管理ロール)")
        new = {
            "log": chan(d.get("log_channel")), "wch": chan(d.get("welcome_channel")), "kch": chan(d.get("kaso_channel")),
            "wmsg": str(d.get("welcome_message", c["welcome"]["message"]))[:1500],
            "ng": [str(w)[:50] for w in d.get("ng_words", []) if str(w).strip()][:100],
            "th": max(1, min(100000, int(d.get("kaso_threshold") or c["kaso"]["threshold"]))),
        }
    except (ValueError, TypeError, AttributeError):
        raise SettingsError("入力が正しくありません")
    c["log_channel"] = new["log"]
    c["welcome"]["channel"], c["welcome"]["message"] = new["wch"], new["wmsg"]
    c["autorole"] = role.id if role else None
    c["automod"]["enabled"], c["automod"]["block_invites"] = bool(d.get("automod_enabled")), bool(d.get("block_invites"))
    c["automod"]["ng_words"] = new["ng"]
    c["kaso"]["enabled"], c["kaso"]["channel"], c["kaso"]["threshold"] = bool(d.get("kaso_enabled")), new["kch"], new["th"]
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
def _b64e(d: dict) -> str:
    raw = zlib.compress(json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")
def _b64d(code: str) -> dict:
    raw = base64.urlsafe_b64decode(code.strip() + "=" * (-len(code.strip()) % 4))
    dec = zlib.decompressobj()
    out = dec.decompress(raw, 300_000)
    if dec.unconsumed_tail:
        raise SettingsError("コードが大きすぎます")
    return json.loads(out.decode("utf-8"))
def _is_dash_admin(member) -> bool:
    return isinstance(member, discord.Member) and (member.guild_permissions.administrator or member.guild_permissions.manage_guild)
class ApplyModal(discord.ui.Modal, title="適用コードを貼り付け"):
    code = discord.ui.TextInput(label="Webで作った適用コード", style=discord.TextStyle.paragraph, max_length=4000)
    async def on_submit(self, interaction: discord.Interaction):
        if not _is_dash_admin(interaction.user):
            return await interaction.response.send_message("❌ 管理者のみ実行できます。", ephemeral=True)
        try:
            data = _b64d(str(self.code))
            if data.get("v") != 1 or str(data.get("gid")) != str(interaction.guild.id):
                raise SettingsError("このサーバー用のコードではありません。このサーバーで /web を実行して作り直してください。")
            apply_settings(interaction.guild, data["cfg"])
        except SettingsError as e:
            return await interaction.response.send_message(f"⚠️ {e}", ephemeral=True)
        except Exception:
            return await interaction.response.send_message("⚠️ コードを読み取れませんでした。コピーし直してください。", ephemeral=True)
        await interaction.response.send_message("✅ 設定を反映しました。", ephemeral=True)
class WebCodeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=900)
        self.add_item(discord.ui.Button(label="編集ページを開く", emoji="🌐", style=discord.ButtonStyle.link, url=PAGE_URL))
    @discord.ui.button(label="適用コードを貼り付ける", emoji="📥", style=discord.ButtonStyle.primary)
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _is_dash_admin(interaction.user):
            return await interaction.response.send_message("❌ 管理者のみ実行できます。", ephemeral=True)
        await interaction.response.send_modal(ApplyModal())
def add_dashboard_routes(app: web.Application, oauth: bool = True) -> None:
    if oauth:
        if not DASHBOARD_PAGE:
            app.router.add_get("/", dash_index)
        app.router.add_get("/login", dash_login)
        app.router.add_get("/callback", dash_callback)
        app.router.add_get("/logout", dash_logout)
    app.router.add_post("/api/logout", dash_logout)
    app.router.add_get("/api/me", dash_me)
    app.router.add_get("/api/guild/{gid}", dash_get)
    app.router.add_post("/api/guild/{gid}", dash_save)
@bot.tree.command(name="web", description="Webで設定を編集します(設定不要・管理者のみ)")
@app_commands.guild_only()
async def web_cmd(interaction: discord.Interaction):
    if not _is_dash_admin(interaction.user):
        return await interaction.response.send_message("❌ サーバー管理者のみ使えます。", ephemeral=True)
    if DASHBOARD_URL and CLIENT_SECRET:
        v = discord.ui.View()
        v.add_item(discord.ui.Button(label="ダッシュボードを開く", emoji="🌐", style=discord.ButtonStyle.link, url=PAGE_URL))
        return await interaction.response.send_message("🌐 Discordでログインすると、設定をブラウザから変更できます。", view=v, ephemeral=True)
    if TUNNEL_URL:
        now = time.time()
        for k in [k for k, v in dash_sessions.items() if v["exp"] < now]:
            dash_sessions.pop(k, None)
        sid = secrets.token_urlsafe(32)
        dash_sessions[sid] = {"exp": now + MAGIC_TTL, "user": {"id": str(interaction.user.id), "name": interaction.user.display_name},
                              "guilds": {interaction.guild.id: interaction.user.guild_permissions.value}}
        v = discord.ui.View()
        v.add_item(discord.ui.Button(label="ダッシュボードを開く", emoji="🌐", style=discord.ButtonStyle.link,
                                     url=f"{PAGE_URL}
        return await interaction.response.send_message(
            "🌐 下のボタンから、このサーバーの設定をブラウザで編集できます。\n"
            "※ このリンクは**あなた専用**です。他の人に共有しないでください。(3時間有効 / BOTの再起動で無効になります)",
            view=v, ephemeral=True)
    code = _b64e(dash_snapshot(interaction.guild))
    steps = (("⏳ 自動接続を準備中のため、今回はコード方式で案内します。(しばらくしてからもう一度 `/web` を実行するとボタンだけで開けます)\n\n" if TUNNEL_MODE else "")
             + "🌐 **Webで設定を編集する手順**\n"
             "1️⃣ 「編集ページを開く」を押し、下の**読み込みコード**を貼り付けます\n"
             "2️⃣ 設定を編集して「適用コードを作る」→ コピー\n"
             "3️⃣ 「適用コードを貼り付ける」を押して貼り付けると反映されます\n"
             "※ コードにはこのサーバーの設定が入っています。他の人に見せないでください。(15分で操作が無効になります)")
    if len(code) <= 1500:
        await interaction.response.send_message(f"{steps}\n```{code}```", view=WebCodeView(), ephemeral=True)
    else:
        await interaction.response.send_message(steps, view=WebCodeView(), ephemeral=True,
                                                file=discord.File(io.BytesIO(code.encode()), filename="azq-code.txt"))
async def _web_hint_check(interaction: discord.Interaction) -> bool:
    try:
        cmd = interaction.command
        root = (getattr(cmd, "root_parent", None) or cmd)
        if (root and root.name in WEB_HINT_ROOTS
                and not user_prefs.rec(interaction.user.id).get("web_hint")):
            user_prefs.rec(interaction.user.id)["web_hint"] = True
            user_prefs.save()
            async def hint():
                await asyncio.sleep(2)
                v = discord.ui.View()
                v.add_item(discord.ui.Button(label="Webで操作する", emoji="🌐", style=discord.ButtonStyle.link, url=PAGE_URL))
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
    e.add_field(name="🏓 ping", value="`/ping` BOT速度 / `/ping target:example.com` Webサイト", inline=False)
    e.add_field(name="🔐 認証", value="`/verify setup` 設置 / `/verify set` 詳細設定 / `/verify text` パネルの文面を編集 / `/verify status` 状態\n`/verify approve` `/verify revoke` `/verify bulk_approve` `/verify raid` `/verify panel` `/verify disable`\n方式: ボタン・計算・画像CAPTCHA・Web認証(VPN/サブ垢の判定つき)、未認証ロール、アカウント年齢制限、未認証キック、レイド時の自動強化\nロボット確認の強化、疑わしいアカウント対策(デフォルトアイコン・再参加・集団参加 → 承認待ち/キック)は `/verify set` から", inline=False)
    e.add_field(name="🎫 チケット", value="`/ticketconfig setup` 設置 / `/ticketconfig set` `staff` `panel` `block` `unblock` `status` `disable`\nチケット内: `/ticket close` `/ticket add` `/ticket remove` `/ticket rename` `/ticket delete`\nクローズは作成者・スタッフ・管理者、**削除は管理者のみ**(クローズ後は閲覧のみ)\n機能: 非公開chの自動作成、担当者、記録(.txt)の保存/DM、無操作の自動クローズ、認証連携", inline=False)
    e.add_field(name="🌐 Webダッシュボード", value="`/web` でブラウザから設定を編集(設定不要・管理者のみ)", inline=False)
    e.add_field(name="🎭 ロールパネル", value="`/rolepanel create` 作成 / `/rolepanel text` 文面を編集 / `/rolepanel add` `remove` `delete` `list`\nボタンを押すとロールを付与・もう一度押すと解除。「1つだけ選択」モードあり\n(管理者のみ設定可)", inline=False)
    e.add_field(name="🔨 モデレーション", value="`/kick` `/ban` `/unban` `/timeout` `/untimeout` `/warn` `/warnings` `/unwarn` `/clearwarns` `/purge` `/slowmode` `/lock` `/unlock` `/role_add` `/role_remove`", inline=False)
    e.add_field(name="⚙️ 設定", value="`/config log_channel` `/config welcome` `/config autorole` `/config warn_limit` `/config automod_ignore` `/config show`", inline=False)
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
        f"✅ ウェルカム: {channel.mention if channel else '無効'}\n{wc['message']}", ephemeral=True,
        allowed_mentions=discord.AllowedMentions.none())
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
        f"✅ 過疎アラート: {'ON' if enabled else 'OFF'} / しきい値 {k['threshold']}件 / 通知先 <
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
        chs = " ".join(f"<
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
    ch = lambda i: f"<
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
