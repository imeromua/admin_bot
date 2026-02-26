from app.context import Context
from app.core.exec import run_command, safe_html
from app.core.targets import Target


def collect_system_info(target: Target, *, ctx: Context) -> str:
    uptime = run_command(["uptime", "-p"], timeout=10, max_output_size=ctx.config.max_output_size)

    df_out = run_command(["df", "-h", "/"], timeout=10, max_output_size=ctx.config.max_output_size)
    disk = "N/A"
    disk_warning = ""
    lines = [ln for ln in df_out.splitlines() if ln.strip()]
    if len(lines) >= 2:
        cols = lines[-1].split()
        if len(cols) >= 5:
            disk = cols[4]
            # Перевірка критичного рівня заповнення
            try:
                disk_percent = int(disk.rstrip("%"))
                if disk_percent >= 90:
                    disk_warning = " 🔴 CRITICAL"
                elif disk_percent >= 80:
                    disk_warning = " 🟡 WARNING"
            except ValueError:
                pass

    # Перевірка вільного місця в GB
    df_gb = run_command(["df", "-BG", "/"], timeout=10, max_output_size=ctx.config.max_output_size)
    free_gb_str = ""
    lines_gb = [ln for ln in df_gb.splitlines() if ln.strip()]
    if len(lines_gb) >= 2:
        cols = lines_gb[-1].split()
        if len(cols) >= 4:
            free_gb = cols[3].rstrip("G")
            try:
                if int(free_gb) < 2:
                    disk_warning = " 🔴 CRITICAL (< 2GB)"
                free_gb_str = f" ({free_gb}GB вільно)"
            except ValueError:
                pass

    free_out = run_command(["free", "-h"], timeout=10, max_output_size=ctx.config.max_output_size)
    mem = "N/A"
    for ln in free_out.splitlines():
        if ln.startswith("Mem:"):
            cols = ln.split()
            if len(cols) >= 3:
                mem = f"{cols[2]}/{cols[1]}"

    loadavg = run_command(["cat", "/proc/loadavg"], timeout=5, max_output_size=ctx.config.max_output_size)
    loadavg_short = " ".join(loadavg.split()[:3]) if loadavg and not loadavg.startswith("❌") else "N/A"

    service_uptime = run_command(
        ["systemctl", "show", target.service, "--property=ActiveEnterTimestamp", "--value"],
        timeout=10,
        max_output_size=ctx.config.max_output_size,
    )
    service_memory = run_command(
        ["systemctl", "show", target.service, "--property=MemoryCurrent", "--value"],
        timeout=10,
        max_output_size=ctx.config.max_output_size,
    )

    try:
        mem_mb = int(service_memory) / 1024 / 1024
        service_memory_str = f"{mem_mb:.1f} MB"
    except Exception:
        service_memory_str = "N/A"

    return (
        "⚙️ <b>Системна інформація</b>\n"
        f"🎯 Ціль: <code>{target.key}</code>\n"
        f"💾 RAM: <code>{safe_html(mem, max_len=ctx.config.max_output_size)}</code>\n"
        f"💿 Диск: <code>{safe_html(disk, max_len=ctx.config.max_output_size)}{safe_html(free_gb_str, max_len=ctx.config.max_output_size)}</code>{disk_warning}\n"
        f"⏰ Час роботи: <code>{safe_html(uptime, max_len=ctx.config.max_output_size)}</code>\n"
        f"📈 Навантаження: <code>{safe_html(loadavg_short, max_len=ctx.config.max_output_size)}</code>\n\n"
        f"📦 <b>Сервіс: {safe_html(target.service, max_len=ctx.config.max_output_size)}</b>\n"
        f"🔄 Запущено: <code>{safe_html(service_uptime, max_len=ctx.config.max_output_size)}</code>\n"
        f"💾 Пам'ять: <code>{safe_html(service_memory_str, max_len=ctx.config.max_output_size)}</code>"
    )
