import asyncio
import copy
import io
import ipaddress
import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from datetime import timedelta
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
from PIL import Image, ImageDraw, ImageFont, ImageOps

import aiohttp
from aiohttp import web
from discord import app_commands
from discord.ext import commands, tasks


TOKEN = "YOUR-TOKEN"
DEV_GUILD_ID = "YOUR-SERVER"   
DATA_DIR = "data"
PORT = int(os.getenv("PORT", "8080"))

BLUE, RED, GREEN, YELLOW, GRAY = 0x5865F2, 0xED4245, 0x57F287, 0xFEE75C, 0x99AAB5
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
    },
    "kaso": {"enabled": False, "channel": None, "threshold": 20, "last_alert": 0},
}


def deep_merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


class Store:
    def __init__(self, directory: str):
        os.makedirs(directory, exist_ok=True)
        self.path = os.path.join(directory, "guilds.json")
        self.data: dict = {}
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
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


store = Store(DATA_DIR)

intents = discord.Intents.default()
intents.message_content = True  # 要: Developer Portal で Message Content Intent を ON
intents.members = True          # 要: Developer Portal で Server Members Intent を ON


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
        if DEV_GUILD_ID:
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

    async def close(self):
        if self.session:
            await self.session.close()
        if self.web_runner:
            await self.web_runner.cleanup()
        await super().close()


bot = AzqBot()


async def start_web():
    """SnapDeploy等のコンテナ環境向けヘルスチェック用の簡易HTTPサーバー"""

    async def health(_request):
        lat = bot.latency
        return web.json_response({
            "status": "ok",
            "guilds": len(bot.guilds),
            "latency_ms": None if lat != lat else round(lat * 1000),
        })

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    bot.web_runner = runner
    log.info("ヘルスチェックサーバー起動: 0.0.0.0:%s", PORT)


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
    else:
        log.exception("コマンドエラー", exc_info=error)
        msg = "⚠️ エラーが発生しました。しばらくしてからもう一度お試しください。"
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)

recent_msgs = defaultdict(lambda: deque(maxlen=30))  # (guild,user) -> (time, message)
recent_dups = defaultdict(lambda: deque(maxlen=10))  # (guild,user) -> (time, content)
strikes = defaultdict(deque)                          # (guild,user) -> times
join_times = defaultdict(deque)                       # guild -> times
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


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    cfg = store.get(guild.id)

    if cfg["autorole"]:
        role = guild.get_role(cfg["autorole"])
        if role:
            try:
                await member.add_roles(role, reason="AZQ BOT 自動ロール")
            except discord.HTTPException:
                pass

    wc = cfg["welcome"]
    ch = guild.get_channel(wc["channel"]) if wc["channel"] else None
    if ch:
        text = (wc["message"].replace("{user}", member.mention)
                .replace("{server}", guild.name).replace("{count}", str(guild.member_count)))
        try:
            await ch.send(text)
        except discord.HTTPException:
            pass

    age_days = (discord.utils.utcnow() - member.created_at).days
    e = make_embed("📥 メンバー参加", f"{member.mention} (`{member.id}`)", GREEN)
    e.add_field(name="アカウント作成", value=discord.utils.format_dt(member.created_at, "R"))
    if age_days < 3:
        e.add_field(name="⚠️ 新規アカウント", value=f"作成から{age_days}日", inline=False)
        e.color = YELLOW
    await send_log(guild, e)

    # レイド検知
    am = cfg["automod"]
    now = time.time()
    dq = join_times[guild.id]
    dq.append(now)
    while dq and now - dq[0] > am["raid_seconds"]:
        dq.popleft()
    if am["enabled"] and len(dq) >= am["raid_joins"] and now - last_raid_alert.get(guild.id, 0) > 60:
        last_raid_alert[guild.id] = now
        alert = make_embed(
            "🚨 レイドの疑い",
            f"{am['raid_seconds']}秒以内に **{len(dq)}人** が参加しました。\n"
            "`/lock` でチャンネルを閉じる、`/ban` 等で対処してください。",
            RED,
        )
        await send_log(guild, alert)


@bot.event
async def on_member_remove(member: discord.Member):
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


@tasks.loop(minutes=10)
async def cleanup_trackers():
    now = time.time()
    for tracker in (recent_msgs, recent_dups):
        for k in [k for k, dq in tracker.items() if not dq or now - dq[-1][0] > 120]:
            tracker.pop(k, None)
    for k in [k for k, dq in strikes.items() if not dq or now - dq[-1] > 300]:
        strikes.pop(k, None)


async def measure_activity(guild: discord.Guild, hours: int = 24, per_channel: int = 500, max_channels: int = 50):
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


FONT_URL = "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf"
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\meiryob.ttc", r"C:\Windows\Fonts\YuGothB.ttc",
    r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\msgothic.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
]
KINSOKU = set("、。，．・」』）】！？!?,.)")
_font_path: Optional[str] = None


async def ensure_font() -> str:
    """日本語フォントを探す。無ければ Noto Sans JP を自動ダウンロードして保存する"""
    global _font_path
    if _font_path:
        return _font_path
    cached = os.path.join(DATA_DIR, "NotoSansJP-Bold.otf")
    for p in [cached, *FONT_CANDIDATES]:
        if os.path.exists(p):
            try:
                ImageFont.truetype(p, 20)
                _font_path = p
                return p
            except OSError:
                continue
    async with bot.session.get(FONT_URL, timeout=aiohttp.ClientTimeout(total=120)) as resp:
        resp.raise_for_status()
        data = await resp.read()
    if len(data) < 100_000:
        raise RuntimeError("フォントのダウンロードに失敗しました")
    with open(cached, "wb") as f:
        f.write(data)
    _font_path = cached
    return cached


def _wrap(text: str, font, max_w: int) -> list:
    lines = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            if cur and font.getlength(cur + ch) > max_w and ch not in KINSOKU:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
    return lines


def render_meigen(avatar_bytes: bytes, text: str, author: str, style: str, color: bool, font_path: str) -> io.BytesIO:
    W, H = 1200, 630
    dark = style == "black"
    bg = (0, 0, 0) if dark else (245, 245, 245)
    fg = (255, 255, 255) if dark else (20, 20, 20)
    sub = (175, 175, 175) if dark else (90, 90, 90)

    img = Image.new("RGB", (W, H), bg)
    av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    flat = Image.new("RGBA", av.size, bg + (255,))
    flat.alpha_composite(av)
    av = ImageOps.fit(flat.convert("RGB"), (H, H), Image.Resampling.LANCZOS)
    if not color:
        av = ImageOps.grayscale(av).convert("RGB")
    mask = Image.new("L", (H, H), 255)
    md = ImageDraw.Draw(mask)
    start = int(H * 0.45)
    for x in range(start, H):
        md.line([(x, 0), (x, H)], fill=int(255 * (1 - (x - start) / (H - start))))
    img.paste(av, (0, 0), mask)

    area_x, area_w = 560, 590
    max_text_h = H - 230
    for size in range(68, 23, -2):
        font = ImageFont.truetype(font_path, size)
        lines = _wrap(text, font, area_w)
        lh = int(size * 1.45)
        if len(lines) * lh <= max_text_h:
            break
    else:
        lines = lines[: max(1, max_text_h // lh)]
        lines[-1] = lines[-1].rstrip()[:-1] + "…"

    draw = ImageDraw.Draw(img)
    author_font = ImageFont.truetype(font_path, 30)
    author_text = "― " + (author if len(author) <= 24 else author[:23] + "…")
    block_h = len(lines) * lh + 24 + 40
    y = (H - block_h) / 2
    for line in lines:
        w = font.getlength(line)
        draw.text((area_x + (area_w - w) / 2, y), line, font=font, fill=fg)
        y += lh
    y += 24
    aw = author_font.getlength(author_text)
    draw.text((area_x + (area_w - aw) / 2, y), author_text, font=author_font, fill=sub)

    mark_font = ImageFont.truetype(font_path, 20)
    draw.text((W - 130, H - 40), "AZQ BOT", font=mark_font, fill=sub)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


async def make_meigen_file(user: discord.abc.User, text: str, author: Optional[str], style: str, color: bool) -> discord.File:
    font_path = await ensure_font()
    avatar = await user.display_avatar.replace(size=512, format="png").read()
    buf = await asyncio.to_thread(render_meigen, avatar, text, author or user.display_name, style, color, font_path)
    return discord.File(buf, filename="meigen.png")


@bot.tree.command(name="meigen", description="名言画像を作ります")
@app_commands.describe(
    text="名言の内容(改行は \\n と入力)", user="発言者のアイコンを使うユーザー(省略すると自分)",
    author="表示する名前(省略するとユーザー名)", style="背景の色", color="アイコンをカラーにする(既定はモノクロ)",
)
@app_commands.choices(style=[
    app_commands.Choice(name="ブラック", value="black"),
    app_commands.Choice(name="ホワイト", value="white"),
])
@app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
async def meigen(interaction: discord.Interaction, text: app_commands.Range[str, 1, 200],
                 user: Optional[discord.User] = None, author: Optional[app_commands.Range[str, 1, 30]] = None,
                 style: Optional[app_commands.Choice[str]] = None, color: bool = False):
    await interaction.response.defer()
    try:
        file = await make_meigen_file(user or interaction.user, text.replace("\\n", "\n"), author,
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
    await interaction.response.defer()
    try:
        file = await make_meigen_file(message.author, text[:200], None, "black", False)
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
    lines = [f"`{i}.` <t:{w['time']}:d> {w['reason']} (by <@{w['mod']}>)" for i, w in enumerate(lst[-15:], 1)]
    await interaction.response.send_message(embed=make_embed(f"⚠️ {member} の警告 ({len(lst)}件)", "\n".join(lines), YELLOW), ephemeral=True)


@bot.tree.command(name="clearwarns", description="メンバーの警告をすべて消去します")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def clearwarns(interaction: discord.Interaction, member: discord.Member):
    store.get(interaction.guild.id)["warns"].pop(str(member.id), None)
    store.save()
    await interaction.response.send_message(f"🧹 {member} の警告を消去しました。")


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


@bot.tree.command(name="help", description="AZQ BOTのコマンド一覧")
async def help_cmd(interaction: discord.Interaction):
    e = make_embed("🤖 AZQ BOT コマンド一覧")
    e.add_field(name="🛡️ 荒らし対策", value="自動で動作 (連投/同一投稿/メンション爆撃/招待リンク/NGワード/レイド検知)\n設定: `/config automod_set` `/config ngword` `/config show`", inline=False)
    e.add_field(name="📊 過疎検出", value="`/kaso` 診断 / `/config kaso` 自動アラート設定", inline=False)
    e.add_field(name="🧠 脳内メーカー", value="`/nounai [name]` / ユーザーを右クリック→アプリ→脳内メーカー", inline=False)
    e.add_field(name="🖼️ 名言画像", value="`/meigen text:名言` / メッセージを右クリック→アプリ→名言画像にする", inline=False)
    e.add_field(name="🏓 ping", value="`/ping` BOT速度 / `/ping target:example.com` Webサイト", inline=False)
    e.add_field(name="🔨 モデレーション", value="`/kick` `/ban` `/unban` `/timeout` `/untimeout` `/warn` `/warnings` `/clearwarns` `/purge` `/slowmode` `/lock` `/unlock` `/role_add` `/role_remove`", inline=False)
    e.add_field(name="⚙️ 設定", value="`/config log_channel` `/config welcome` `/config autorole` `/config show`", inline=False)
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
    e.add_field(
        name="AutoMod",
        value="\n".join(f"`{k}`: {v}" for k, v in am.items() if k != "ng_words") + f"\n`ng_words`: {len(am['ng_words'])}件",
        inline=False,
    )
    await interaction.response.send_message(embed=e, ephemeral=True)

if __name__ == "__main__":
    if not TOKEN or TOKEN.startswith("ここに"):
        raise SystemExit("bot.py 上部の TOKEN にBOTトークンを貼り付けてください。")
    bot.run(TOKEN, log_handler=None)
