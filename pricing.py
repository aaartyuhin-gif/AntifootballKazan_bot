from database import get_pricing_tiers, calc_price, next_tier


async def price_table_text() -> str:
    tiers = await get_pricing_tiers()
    lines = ["📊 <b>Шкала цен (₽ за игру):</b>\n"]
    for i, t in enumerate(sorted(tiers, key=lambda x: x["min_players"])):
        nxt = tiers[i + 1]["min_players"] if i + 1 < len(tiers) else None
        if nxt:
            lines.append(f"  👥 {t['min_players']}–{nxt - 1} игроков → <b>{int(t['price'])} ₽</b>")
        else:
            lines.append(f"  👥 {t['min_players']}+ игроков → <b>{int(t['price'])} ₽</b>")
    return "\n".join(lines)


async def price_for(player_count: int) -> float:
    tiers = await get_pricing_tiers()
    return calc_price(player_count, tiers)


async def price_hint(player_count: int) -> str:
    tiers = await get_pricing_tiers()
    current = calc_price(player_count, tiers)
    nxt = next_tier(player_count, tiers)
    hint = f"Текущая цена: <b>{int(current)} ₽</b>"
    if nxt:
        need = nxt[0] - player_count
        hint += f"\n💡 Ещё {need} чел. → цена снизится до <b>{int(nxt[1])} ₽</b>"
    return hint
