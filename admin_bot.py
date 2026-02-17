import asyncio
import html
import logging
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, List

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    FSInputFile,
)
from dotenv import load_dotenv

# =========================
# CONFIG
# =========================
load_dotenv()

TOKEN = os.getenv("ADMIN_BOT_TOKEN")
ADMIN_ID_STR = os.getenv("ADMIN_BOT_ADMIN_ID")
SELF_SERVICE_NAME = os.getenv("ADMIN_BOT_SELF_SERVICE", "admin_bot")
TARGETS_STR = os.getenv("ADMIN_TARGETS", "").strip()

if not TOKEN:
    raise RuntimeError("ADMIN_BOT_TOKEN is not set in environment")
if not ADMIN_ID_STR:
    raise RuntimeError("ADMIN_BOT_ADMIN_ID is not set in environment")

try:
    ADMIN_ID = int(ADMIN_ID_STR)
except ValueError as e:
    raise RuntimeError(f"ADMIN_BOT_ADMIN_ID must be integer, got: {ADMIN_ID_STR}") from e

MAX_OUTPUT_SIZE = 4000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("admin_bot")


@dataclass(frozen=True)
class Target:
    key: str
    service: str
    path: Path
    repo: Optional[str] = None
    python_exe: Optional[Path] = None
    env_file: Optional[Path] = None
    req_file: Optional[Path] = None
    log_file: Optional[Path] = None

    def resolved_env_file(self) -> Path:
        return self.env_file or (self.path / ".env")

    def resolved_req_file(self) -> Path:
        return self.req_file or (self.path / "requirements.txt")

    def resolved_log_file(self) -> Path:
        return self.log_file or (self.path / "bot.log")


def _truthy(val: Optional[str]) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on", "y"}


def safe_html(text: str) -> str:
    if text is None:
        text = ""
    if len(text) > MAX_OUTPUT_SIZE:
        text = text[:MAX_OUTPUT_SIZE] + "\n\n... (обрізано)"
    return html.escape(text)


def run_command(
    args: List[str],
    *,
    cwd: Optional[Path] = None,
    timeout: int = 30,
    env: Optional[Dict[str, str]] = None,
) -> str:
    """Run a command safely (no shell), capture stdout+stderr."""
    try:
        res = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True,
        )
        out = (res.stdout or "").strip()
        if len(out) > MAX_OUTPUT_SIZE:
            out = out[:MAX_OUTPUT_SIZE] + "\n\n... (обрізано, занадто довгий вивід)"
        if res.returncode != 0:
            return f"❌ Error (exit code {res.returncode}):\n{out}"
        return out
    except subprocess.TimeoutExpired:
        return f"⏱ Timeout ({timeout}s)"
    except Exception as e:
        return f"❌ Exception: {e}"


def read_file(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("Failed to read %s: %s", path, e)
        return f"Error reading file: {e}"


def write_file(path: Path, content: str) -> bool:
    try:
        path.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        logger.error("Failed to write %s: %s", path, e)
        return False


def parse_env_file(path: Path) -> Dict[str, str]:
    env_vars: Dict[str, str] = {}
    content = read_file(path)
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()
    return env_vars


def write_env_file(path: Path, env_vars: Dict[str, str]) -> bool:
    content = "".join(f"{k}={v}\n" for k, v in sorted(env_vars.items()))
    return write_file(path, content)


def load_targets() -> Dict[str, Target]:
    if not TARGETS_STR:
        raise RuntimeError("ADMIN_TARGETS is empty. Define at least one target.")

    keys = [k.strip() for k in TARGETS_STR.split(",") if k.strip()]
    targets: Dict[str, Target] = {}

    for key in keys:
        prefix = f"ADMIN_TARGET_{key.upper()}_"
        service = os.getenv(prefix + "SERVICE")
        path = os.getenv(prefix + "PATH")
        if not service or not path:
            raise RuntimeError(f"Target '{key}' requires {prefix}SERVICE and {prefix}PATH")

        repo = os.getenv(prefix + "REPO")
        python_exe = os.getenv(prefix + "PYTHON")

        env_file = os.getenv(prefix + "ENV_FILE")
        req_file = os.getenv(prefix + "REQ_FILE")
        log_file = os.getenv(prefix + "LOG_FILE")

        t = Target(
            key=key,
            service=service,
            path=Path(path),
            repo=repo,
            python_exe=Path(python_exe) if python_exe else None,
            env_file=Path(env_file) if env_file else None,
            req_file=Path(req_file) if req_file else None,
            log_file=Path(log_file) if log_file else None,
        )
        targets[key] = t

    return targets


TARGETS = load_targets()

# Single admin – per chat selection
ACTIVE_TARGET_BY_CHAT: Dict[int, str] = {}


def get_active_target(chat_id: int) -> Target:
    key = ACTIVE_TARGET_BY_CHAT.get(chat_id)
    if key and key in TARGETS:
        return TARGETS[key]
    # default to first target
    first_key = next(iter(TARGETS.keys()))
    ACTIVE_TARGET_BY_CHAT[chat_id] = first_key
    return TARGETS[first_key]


def set_active_target(chat_id: int, key: str) -> None:
    if key not in TARGETS:
        raise KeyError(key)
    ACTIVE_TARGET_BY_CHAT[chat_id] = key


def journalctl_lines(service: str, n: int = 100, since: Optional[str] = None) -> str:
    args = ["journalctl", "-u", service, "--no-pager"]
    if since:
        args += ["--since", since]
    else:
        args += ["-n", str(n)]
    return run_command(args, timeout=20)


def systemctl_status(service: str) -> str:
    return run_command(["systemctl", "status", service], timeout=15)


def systemctl_is_active(service: str) -> str:
    return run_command(["systemctl", "is-active", service], timeout=10)


def sudo_systemctl_restart(service: str) -> str:
    return run_command(["sudo", "systemctl", "restart", service], timeout=30)


def git_pull(target: Target) -> Tuple[str, str]:
    pull = run_command(["git", "pull"], cwd=target.path, timeout=60)
    log1 = run_command(["git", "log", "-1", "--format=%h - %s (%cr) <%an>"], cwd=target.path, timeout=30)
    return pull, log1


def python_for_target(target: Target) -> Path:
    if target.python_exe and target.python_exe.exists():
        return target.python_exe
    # Fallback: admin bot python
    return Path(sys.executable)


def pip_install(target: Target) -> str:
    py = python_for_target(target)
    req = target.resolved_req_file()
    return run_command([str(py), "-m", "pip", "install", "-r", str(req)], timeout=300)


def pip_freeze(target: Target) -> str:
    py = python_for_target(target)
    return run_command([str(py), "-m", "pip", "freeze"], timeout=60)


def pip_outdated(target: Target) -> str:
    py = python_for_target(target)
    return run_command([str(py), "-m", "pip", "list", "--outdated"], timeout=90)


def parse_postgres_from_env(env: Dict[str, str]) -> Optional[Tuple[str, str, str, str]]:
    """Return (host, port, user, dbname) if possible."""
    dsn = env.get("POSTGRES_DSN", "").strip()
    if dsn:
        m = re.match(r"postgresql://(.*?):(.*?)@(.*?):(.*?)/(.*)", dsn)
        if m:
            user, _pw, host, port, dbname = m.groups()
            return host, port, user, dbname

    # inventory style
    host = env.get("DB_HOST")
    port = env.get("DB_PORT")
    user = env.get("DB_USER")
    dbname = env.get("DB_NAME")
    if host and port and user and dbname:
        return host, port, user, dbname

    return None


def get_db_status(target: Target) -> str:
    env = parse_env_file(target.resolved_env_file())
    parsed = parse_postgres_from_env(env)
    if not parsed:
        return "ℹ️ PostgreSQL: немає налаштувань (POSTGRES_DSN або DB_HOST/DB_USER/DB_NAME)"

    host, port, user, dbname = parsed
    out = run_command(["pg_isready", "-h", host, "-p", str(port), "-U", user, "-d", dbname], timeout=10)
    healthy = "accepting connections" in out
    icon = "🟢" if healthy else "🔴"
    return (
        f"{icon} <b>PostgreSQL</b>\n"
        f"Target: <code>{target.key}</code>\n"
        f"DSN: <code>{host}:{port}/{dbname}</code>\n\n"
        f"<blockquote expandable>{safe_html(out)}</blockquote>"
    )


def build_redis_url(env: Dict[str, str]) -> Optional[str]:
    url = env.get("REDIS_URL")
    if url:
        return url

    host = env.get("REDIS_HOST")
    port = env.get("REDIS_PORT")
    db = env.get("REDIS_DB")
    password = env.get("REDIS_PASSWORD", "")

    if host and port and db is not None:
        if password:
            return f"redis://:{password}@{host}:{port}/{db}"
        return f"redis://{host}:{port}/{db}"

    return None


def is_redis_enabled(env: Dict[str, str]) -> bool:
    # generator style
    if _truthy(env.get("REDIS_ENABLED")):
        return True
    # inventory style hint
    if _truthy(env.get("ENABLE_REDIS_CACHE")):
        return True
    return False


def get_redis_status(target: Target) -> str:
    env = parse_env_file(target.resolved_env_file())
    if not is_redis_enabled(env):
        return "ℹ️ Redis вимкнено"

    url = build_redis_url(env)
    if not url:
        return "⚠️ Redis увімкнено, але немає REDIS_URL або REDIS_HOST/REDIS_PORT/REDIS_DB"

    out = run_command(["redis-cli", "-u", url, "PING"], timeout=5)
    healthy = "PONG" in out
    icon = "🟢" if healthy else "🔴"
    return (
        f"{icon} <b>Redis</b>\n"
        f"Target: <code>{target.key}</code>\n"
        f"URL: <code>{safe_html(url)}</code>\n\n"
        f"<blockquote expandable>{safe_html(out)}</blockquote>"
    )


def backup_postgres(target: Target) -> Tuple[bool, str, Optional[Path]]:
    env = parse_env_file(target.resolved_env_file())
    dsn = env.get("POSTGRES_DSN", "").strip()
    if not dsn:
        return False, "POSTGRES_DSN не знайдено (для backup потрібен саме DSN)", None

    m = re.match(r"postgresql://(.*?):(.*?)@(.*?):(.*?)/(.*)", dsn)
    if not m:
        return False, "Неправильний формат POSTGRES_DSN", None

    user, password, host, port, dbname = m.groups()
    filename = Path(f"backup_{target.key}_{dbname}_{datetime.now().strftime('%Y%m%d_%H%M')}.sql")

    cmd = ["pg_dump", "-U", user, "-h", host, "-p", str(port), dbname]
    env2 = os.environ.copy()
    env2["PGPASSWORD"] = password

    try:
        with filename.open("w", encoding="utf-8") as f:
            res = subprocess.run(cmd, env=env2, stdout=f, stderr=subprocess.PIPE, timeout=180, text=True)
        if res.returncode != 0:
            filename.unlink(missing_ok=True)
            err = (res.stderr or "").strip()
            if len(err) > MAX_OUTPUT_SIZE:
                err = err[:MAX_OUTPUT_SIZE] + "\n\n... (обрізано)"
            return False, f"pg_dump error (exit {res.returncode}):\n{err}", None

        return True, "OK", filename
    except subprocess.TimeoutExpired:
        filename.unlink(missing_ok=True)
        return False, "Timeout (180s)", None
    except Exception as e:
        filename.unlink(missing_ok=True)
        return False, str(e), None


# =========================
# AIROGRAM
# =========================
bot = Bot(token=TOKEN)
dp = Dispatcher()


class EnvState(StatesGroup):
    waiting_for_value = State()
    waiting_for_new_key = State()
    waiting_for_new_value = State()


class PipState(StatesGroup):
    waiting_for_new_reqs = State()


def main_keyboard(target: Target) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Бот"), KeyboardButton(text="📊 Статус"), KeyboardButton(text="📜 Логи")],
            [KeyboardButton(text="📦 PIP"), KeyboardButton(text="🔧 ENV"), KeyboardButton(text="🚀 GIT PULL")],
            [KeyboardButton(text="🔄 RESTART"), KeyboardButton(text="💾 Бекап БД"), KeyboardButton(text="⚙️ Системна інфо")],
        ],
        resize_keyboard=True,
        input_field_placeholder=f"Target: {target.key}",
    )


@dp.message.middleware()
async def admin_check_middleware(handler, event, data):
    if hasattr(event, "from_user") and event.from_user and event.from_user.id != ADMIN_ID:
        logger.warning("Unauthorized access attempt from %s", event.from_user.id)
        return
    return await handler(event, data)


@dp.callback_query.middleware()
async def admin_check_cb_middleware(handler, event, data):
    if event.from_user.id != ADMIN_ID:
        await event.answer("❌ Access denied", show_alert=True)
        return
    return await handler(event, data)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    target = get_active_target(message.chat.id)
    repo_line = f"\n🔗 Repo: <code>{safe_html(target.repo)}</code>" if target.repo else ""
    await message.answer(
        "👋 <b>Admin Bot</b>\n\n"
        f"🎯 Target: <code>{target.key}</code>\n"
        f"📦 Service: <code>{target.service}</code>\n"
        f"📁 Path: <code>{safe_html(str(target.path))}</code>"
        f"{repo_line}\n"
        f"🤖 Self service: <code>{SELF_SERVICE_NAME}</code>\n\n"
        "Оберіть команду з меню:",
        reply_markup=main_keyboard(target),
        parse_mode="HTML",
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "ℹ️ <b>Help</b>\n"
        "- 🎯 Бот: обрати ціль (generator/inventory).\n"
        "- 🚀 GIT PULL: оновити код цілі, потім перезапуск.\n"
        "- 🤖 Self-restart доступний після pull (кнопка).",
        parse_mode="HTML",
    )


# =========================
# TARGET SELECT
# =========================
@dp.message(F.text == "🎯 Бот")
async def target_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{t.key} ({t.service})", callback_data=f"target:{t.key}")]
            for t in TARGETS.values()
        ]
    )
    await message.answer("🎯 <b>Оберіть бота</b>", reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("target:"))
async def target_set(cb: CallbackQuery):
    key = cb.data.split(":", 1)[1]
    set_active_target(cb.message.chat.id, key)
    target = get_active_target(cb.message.chat.id)
    await cb.message.answer(
        f"✅ Активна ціль: <code>{target.key}</code>",
        reply_markup=main_keyboard(target),
        parse_mode="HTML",
    )
    await cb.answer()


# =========================
# LOGS
# =========================
@dp.message(F.text == "📜 Логи")
async def logs_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 50", callback_data="logs:50"),
                InlineKeyboardButton(text="📋 100", callback_data="logs:100"),
                InlineKeyboardButton(text="📋 200", callback_data="logs:200"),
            ],
            [InlineKeyboardButton(text="📅 Сьогодні", callback_data="logs:today")],
            [
                InlineKeyboardButton(text="🚨 Помилки (50)", callback_data="logs:errors:50"),
                InlineKeyboardButton(text="⚠️ Warnings (50)", callback_data="logs:warnings:50"),
            ],
            [InlineKeyboardButton(text="💾 Завантажити файл", callback_data="logs:download")],
        ]
    )
    await message.answer("📜 <b>Логи (journalctl)</b>", reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("logs:"))
async def logs_view(cb: CallbackQuery):
    target = get_active_target(cb.message.chat.id)
    parts = cb.data.split(":")

    if cb.data == "logs:today":
        out = journalctl_lines(target.service, since="today")
        title = f"📅 Логи за сьогодні ({target.key})"
    elif cb.data == "logs:download":
        await cb.answer("⏳ Генерую файл...", show_alert=True)
        out = journalctl_lines(target.service, n=500)
        filename = Path(f"logs_{target.key}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
        filename.write_text(out + "\n", encoding="utf-8")
        await cb.message.answer_document(FSInputFile(str(filename)))
        filename.unlink(missing_ok=True)
        return
    elif len(parts) == 2 and parts[1].isdigit():
        n = int(parts[1])
        out = journalctl_lines(target.service, n=n)
        title = f"📋 Останні {n} ({target.key})"
    elif len(parts) == 3 and parts[1] in {"errors", "warnings"} and parts[2].isdigit():
        level = parts[1]
        n = int(parts[2])
        raw = journalctl_lines(target.service, n=500)
        lines = raw.splitlines()
        if level == "errors":
            pattern = re.compile(r"ERROR|CRITICAL|Exception|Traceback", re.IGNORECASE)
            filtered = [ln for ln in lines if pattern.search(ln)]
            title = f"🚨 Помилки (останні {n}) ({target.key})"
        else:
            pattern = re.compile(r"warning", re.IGNORECASE)
            filtered = [ln for ln in lines if pattern.search(ln)]
            title = f"⚠️ Warnings (останні {n}) ({target.key})"
        out = "\n".join(filtered[-n:])
        if not out.strip():
            out = "(немає збігів)"
    else:
        await cb.answer()
        return

    if not out or out.startswith("❌"):
        await cb.message.answer(f"{title}\n\n❌ Логи недоступні або порожні")
        await cb.answer()
        return

    # chunk output
    chunks: List[str] = []
    cur = ""
    for line in out.split("\n"):
        if len(cur) + len(line) + 1 > 3800:
            chunks.append(cur)
            cur = line
        else:
            cur += line + "\n"
    if cur:
        chunks.append(cur)

    await cb.message.answer(
        f"{title}\n<blockquote expandable>{safe_html(chunks[0])}</blockquote>",
        parse_mode="HTML",
    )
    for ch in chunks[1:]:
        await cb.message.answer(f"<blockquote expandable>{safe_html(ch)}</blockquote>", parse_mode="HTML")

    await cb.answer()


# =========================
# STATUS
# =========================
@dp.message(F.text == "📊 Статус")
async def status_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Сервіс", callback_data="status:service")],
            [InlineKeyboardButton(text="🗄 PostgreSQL", callback_data="status:db")],
            [InlineKeyboardButton(text="🧠 Redis", callback_data="status:redis")],
        ]
    )
    await message.answer("📊 <b>Статус</b>", reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("status:"))
async def status_view(cb: CallbackQuery):
    target = get_active_target(cb.message.chat.id)
    _, what = cb.data.split(":", 1)

    if what == "service":
        raw = systemctl_status(target.service)
        is_active = "active (running)" in raw
        icon = "🟢" if is_active else "🔴"
        await cb.message.answer(
            f"{icon} <b>Service</b> (<code>{target.service}</code>)\n"
            f"Target: <code>{target.key}</code>\n"
            f"<blockquote expandable>{safe_html(raw[:3000])}</blockquote>",
            parse_mode="HTML",
        )
    elif what == "db":
        await cb.message.answer(get_db_status(target), parse_mode="HTML")
    elif what == "redis":
        await cb.message.answer(get_redis_status(target), parse_mode="HTML")

    await cb.answer()


# =========================
# SYSTEM INFO
# =========================
@dp.message(F.text == "⚙️ Системна інфо")
async def system_info(message: types.Message):
    target = get_active_target(message.chat.id)
    msg = await message.answer("⏳ <i>Збираю інформацію...</i>", parse_mode="HTML")

    uptime = run_command(["uptime", "-p"], timeout=10)
    disk = run_command(["bash", "-lc", "df -h / | tail -1 | awk '{print $5}'"], timeout=10)
    mem = run_command(["bash", "-lc", "free -h | grep Mem | awk '{print $3"/"$2}'"], timeout=10)
    cpu = run_command(["bash", "-lc", "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"], timeout=10)

    service_uptime = run_command(
        ["systemctl", "show", target.service, "--property=ActiveEnterTimestamp", "--value"],
        timeout=10,
    )
    service_memory = run_command(
        ["systemctl", "show", target.service, "--property=MemoryCurrent", "--value"],
        timeout=10,
    )

    try:
        mem_mb = int(service_memory) / 1024 / 1024
        service_memory_str = f"{mem_mb:.1f} MB"
    except Exception:
        service_memory_str = "N/A"

    text = (
        "⚙️ <b>Системна інформація</b>\n"
        f"🎯 Target: <code>{target.key}</code>\n"
        f"🖥 CPU: <code>{safe_html(cpu)}%</code>\n"
        f"💾 RAM: <code>{safe_html(mem)}</code>\n"
        f"💿 Disk: <code>{safe_html(disk)}</code>\n"
        f"⏰ Uptime: <code>{safe_html(uptime)}</code>\n\n"
        f"📦 <b>Service: {safe_html(target.service)}</b>\n"
        f"🔄 Started: <code>{safe_html(service_uptime)}</code>\n"
        f"💾 Memory: <code>{safe_html(service_memory_str)}</code>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Оновити", callback_data="sysinfo_refresh")]])
    await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data == "sysinfo_refresh")
async def sysinfo_refresh(cb: CallbackQuery):
    await system_info(cb.message)
    await cb.answer("✅ Оновлено")


# =========================
# PIP
# =========================
@dp.message(F.text == "📦 PIP")
async def pip_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 requirements.txt", callback_data="pip_view"),
                InlineKeyboardButton(text="✏️ Редагувати", callback_data="pip_edit"),
            ],
            [InlineKeyboardButton(text="🔄 ВСТАНОВИТИ", callback_data="pip_install")],
            [
                InlineKeyboardButton(text="📦 freeze", callback_data="pip_freeze"),
                InlineKeyboardButton(text="🔍 outdated", callback_data="pip_outdated"),
            ],
        ]
    )
    await message.answer("📦 <b>PIP</b>", reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data == "pip_view")
async def pip_view(cb: CallbackQuery):
    target = get_active_target(cb.message.chat.id)
    content = read_file(target.resolved_req_file()) or "(порожньо)"
    await cb.message.answer(f"📄 <b>requirements.txt</b> ({target.key})\n<pre>{safe_html(content)}</pre>", parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "pip_edit")
async def pip_edit_start(cb: CallbackQuery, state: FSMContext):
    target = get_active_target(cb.message.chat.id)
    content = read_file(target.resolved_req_file())
    await state.set_state(PipState.waiting_for_new_reqs)
    await cb.message.answer(
        f"✏️ Надішліть НОВИЙ вміст requirements.txt для <code>{target.key}</code>. Він замінить старий.",
        parse_mode="HTML",
    )
    if content:
        await cb.message.answer(f"<code>{safe_html(content)}</code>", parse_mode="HTML")
    await cb.answer()


@dp.message(PipState.waiting_for_new_reqs)
async def pip_edit_save(message: types.Message, state: FSMContext):
    target = get_active_target(message.chat.id)
    if write_file(target.resolved_req_file(), message.text):
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Запустити встановлення", callback_data="pip_install")]])
        await message.answer("✅ <b>Файл збережено!</b>", reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer("❌ Помилка збереження файлу")


@dp.callback_query(F.data == "pip_install")
async def pip_install_cb(cb: CallbackQuery):
    target = get_active_target(cb.message.chat.id)
    msg = await cb.message.answer("⏳ <i>pip install...</i>", parse_mode="HTML")
    out = pip_install(target)
    await msg.edit_text(f"📦 <b>pip install</b> ({target.key})\n<blockquote expandable>{safe_html(out)}</blockquote>", parse_mode="HTML")

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Перезапустити сервіс", callback_data="confirm_restart")]])
    await cb.message.answer("Рекомендується перезапустити сервіс.", reply_markup=kb)
    await cb.answer()


@dp.callback_query(F.data == "pip_freeze")
async def pip_freeze_cb(cb: CallbackQuery):
    target = get_active_target(cb.message.chat.id)
    msg = await cb.message.answer("⏳", parse_mode="HTML")
    out = pip_freeze(target)
    await msg.edit_text(f"📦 <b>pip freeze</b> ({target.key})\n<blockquote expandable>{safe_html(out)}</blockquote>", parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "pip_outdated")
async def pip_outdated_cb(cb: CallbackQuery):
    target = get_active_target(cb.message.chat.id)
    msg = await cb.message.answer("⏳ <i>Перевіряю...</i>", parse_mode="HTML")
    out = pip_outdated(target)
    text = (
        f"✅ Всі пакети актуальні ({target.key})"
        if "Package" not in out
        else f"🔍 <b>Outdated</b> ({target.key})\n<blockquote expandable>{safe_html(out)}</blockquote>"
    )
    await msg.edit_text(text, parse_mode="HTML")
    await cb.answer()


# =========================
# GIT + RESTART (self-restart)
# =========================
@dp.message(F.text == "🚀 GIT PULL")
async def git_pull_msg(message: types.Message):
    target = get_active_target(message.chat.id)
    msg = await message.answer("⏳ <i>Git Pull...</i>", parse_mode="HTML")

    pull_res, log1 = git_pull(target)
    updated = ("Updating" in pull_res) or ("Fast-forward" in pull_res)
    icon = "✅" if (updated or "Already up to date" in pull_res) else "⚠️"

    text = (
        f"{icon} <b>GIT UPDATE</b> ({target.key})\n"
        f"🔖 {safe_html(log1)}\n"
        f"<blockquote expandable>{safe_html(pull_res)}</blockquote>"
    )
    await msg.edit_text(text, parse_mode="HTML")

    if updated:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=f"🔄 Restart {target.service}", callback_data="confirm_restart"),
                    InlineKeyboardButton(text=f"🤖 Restart {SELF_SERVICE_NAME}", callback_data="restart_self"),
                ]
            ]
        )
        await message.answer("✅ Код оновився. Який сервіс перезапустити?", reply_markup=kb)


@dp.message(F.text == "🔄 RESTART")
async def restart_btn(message: types.Message):
    target = get_active_target(message.chat.id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm_restart"),
                InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_restart"),
            ]
        ]
    )
    await message.answer(
        f"⚠️ <b>Підтвердіть перезапуск</b>\nСервіс <code>{target.service}</code> буде перезапущено.",
        reply_markup=kb,
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "confirm_restart")
async def confirm_restart(cb: CallbackQuery):
    target = get_active_target(cb.message.chat.id)
    msg = await cb.message.edit_text(f"🔄 Перезапускаю <code>{target.service}</code>...", parse_mode="HTML")

    sudo_systemctl_restart(target.service)
    await asyncio.sleep(3)

    status = systemctl_is_active(target.service)
    text = "✅ <b>Перезапуск успішний!</b>" if status.strip() == "active" else f"⚠️ Status: <code>{safe_html(status)}</code>"
    await msg.edit_text(text, parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "cancel_restart")
async def cancel_restart(cb: CallbackQuery):
    await cb.message.delete()
    await cb.answer("Скасовано")


@dp.callback_query(F.data == "restart_self")
async def restart_self_handler(cb: CallbackQuery):
    await cb.answer("🔄 Перезапускаю Admin Bot...", show_alert=True)
    await cb.message.answer(
        f"🤖 <b>Ініційовано перезапуск {SELF_SERVICE_NAME}</b>\n"
        "Бот тимчасово недоступний. Зачекайте 10-15 секунд і натисніть /start.",
        parse_mode="HTML",
    )
    asyncio.create_task(_run_self_restart())


async def _run_self_restart():
    await asyncio.sleep(1)
    logger.warning("Self-restart initiated for service: %s", SELF_SERVICE_NAME)
    subprocess.run(["sudo", "systemctl", "restart", SELF_SERVICE_NAME])


# =========================
# ENV
# =========================
async def show_env_menu(message_obj, *, edit: bool = False):
    target = get_active_target(message_obj.chat.id)
    env_path = target.resolved_env_file()

    env_vars = parse_env_file(env_path)
    kb_rows = []
    for k, v in sorted(env_vars.items()):
        display_val = (v[:8] + "..") if len(v) > 10 else v
        kb_rows.append([InlineKeyboardButton(text=f"{k}={display_val}", callback_data=f"edit_env:{k}")])

    kb_rows.append([InlineKeyboardButton(text="➕ Нова змінна", callback_data="add_new_env")])
    kb_rows.append([InlineKeyboardButton(text="💾 Зберегти", callback_data="env_saved")])

    markup = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    title = f"🔧 <b>.env</b> ({target.key})\n<code>{safe_html(str(env_path))}</code>"

    if edit:
        await message_obj.edit_text(title, reply_markup=markup, parse_mode="HTML")
    else:
        await message_obj.answer(title, reply_markup=markup, parse_mode="HTML")


@dp.message(F.text == "🔧 ENV")
async def env_menu(message: types.Message):
    await show_env_menu(message)


@dp.callback_query(F.data.startswith("edit_env:"))
async def edit_env_var(cb: CallbackQuery, state: FSMContext):
    target = get_active_target(cb.message.chat.id)
    env_vars = parse_env_file(target.resolved_env_file())

    key = cb.data.split(":", 1)[1]
    await state.update_data(editing_key=key)
    await state.set_state(EnvState.waiting_for_value)

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Скасувати", callback_data="cancel_env")]])
    await cb.message.edit_text(
        f"✏️ <b>{safe_html(key)}</b> ({target.key})\nЗараз: <code>{safe_html(env_vars.get(key, ''))}</code>\n\nНадішліть нове значення:",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await cb.answer()


@dp.message(EnvState.waiting_for_value)
async def set_env_value(message: types.Message, state: FSMContext):
    target = get_active_target(message.chat.id)
    data = await state.get_data()
    key = data.get("editing_key")

    env_path = target.resolved_env_file()
    env_vars = parse_env_file(env_path)
    env_vars[str(key)] = message.text.strip()
    write_env_file(env_path, env_vars)

    await state.clear()
    await show_env_menu(message)


@dp.callback_query(F.data == "add_new_env")
async def add_new_env_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(EnvState.waiting_for_new_key)
    await cb.message.edit_text(
        "➕ Назва нової змінної:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Скасувати", callback_data="cancel_env")]]),
    )
    await cb.answer()


@dp.message(EnvState.waiting_for_new_key)
async def add_new_env_key(message: types.Message, state: FSMContext):
    key = message.text.strip().upper().replace(" ", "_")
    await state.update_data(new_key=key)
    await state.set_state(EnvState.waiting_for_new_value)
    await message.answer(f"Введіть значення для <code>{safe_html(key)}</code>:", parse_mode="HTML")


@dp.message(EnvState.waiting_for_new_value)
async def add_new_env_value(message: types.Message, state: FSMContext):
    target = get_active_target(message.chat.id)
    data = await state.get_data()
    key = data.get("new_key")

    env_path = target.resolved_env_file()
    env_vars = parse_env_file(env_path)
    env_vars[str(key)] = message.text.strip()
    write_env_file(env_path, env_vars)

    await state.clear()
    await message.answer("✅ Змінну додано!", parse_mode="HTML")
    await show_env_menu(message)


@dp.callback_query(F.data == "cancel_env")
async def cancel_env(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_env_menu(cb.message, edit=True)
    await cb.answer()


@dp.callback_query(F.data == "env_saved")
async def env_saved(cb: CallbackQuery):
    await cb.answer("✅ Збережено")


# =========================
# BACKUP
# =========================
@dp.message(F.text == "💾 Бекап БД")
async def backup_db(message: types.Message):
    target = get_active_target(message.chat.id)
    msg = await message.answer("⏳ <i>Створюю бекап...</i>", parse_mode="HTML")

    ok, info, filename = backup_postgres(target)
    if not ok:
        await msg.edit_text(f"❌ {safe_html(info)}", parse_mode="HTML")
        return

    assert filename is not None
    size_mb = filename.stat().st_size / 1024 / 1024
    await message.answer_document(
        FSInputFile(str(filename)),
        caption=(
            f"📦 <b>Backup created</b>\n"
            f"🎯 Target: <code>{target.key}</code>\n"
            f"💾 Size: {size_mb:.2f} MB\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ),
        parse_mode="HTML",
    )
    filename.unlink(missing_ok=True)
    await msg.delete()


# =========================
# MAIN
# =========================
async def on_shutdown():
    logger.info("Shutting down admin bot...")
    await bot.session.close()


async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Admin Bot started. Targets: %s", ",".join(TARGETS.keys()))
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
