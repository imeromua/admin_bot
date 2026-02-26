from aiogram import Router, F, types

from app.context import Context
from app.core.exec import safe_html
from app.services.backup import backup_postgres
from aiogram.types import FSInputFile


router = Router()


@router.message(F.text == "💾 Бекап БД")
async def backup_db(message: types.Message, ctx: Context):
    target = ctx.get_active_target(message.chat.id)
    msg = await message.answer("⏳ <i>Створюю бекап...</i>", parse_mode="HTML")

    ok, info, filename = backup_postgres(target, ctx=ctx)
    if not ok:
        await msg.edit_text(f"❌ {safe_html(info, max_len=ctx.config.max_output_size)}", parse_mode="HTML")
        return

    assert filename is not None
    size_mb = filename.stat().st_size / 1024 / 1024
    await message.answer_document(
        FSInputFile(str(filename)),
        caption=(
            f"📦 <b>Бекап створено</b>\n"
            f"🎯 Ціль: <code>{target.key}</code>\n"
            f"💾 Розмір: {size_mb:.2f} МБ"
        ),
        parse_mode="HTML",
    )

    filename.unlink(missing_ok=True)
    await msg.delete()
