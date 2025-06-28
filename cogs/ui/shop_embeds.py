"""Embeds for the shop cog."""
import discord
from discord.ext.commands import Context

from core.interfaces.currency_interfaces import ICurrencyService
from core.interfaces.premium_interfaces import IPremiumService


async def get_premium_users_count(ctx: Context) -> int:
    """Get total count of users with any premium role for social proof."""
    try:
        async with ctx.bot.get_db() as session:
            # Use new service architecture
            premium_service = await ctx.bot.get_service(IPremiumService, session)

            # Get actual count from the premium service
            return await premium_service.count_unique_premium_users()
    except Exception:
        # Return fallback number if database query fails
        return 200  # Fallback social proof number


def get_user_avatar_url(member: discord.Member, bot) -> str:
    """Get user's avatar URL based on their roles."""
    # Sprawdzamy czy użytkownik ma rolę blokującą avatary
    attach_files_off_role_id = bot.config["mute_roles"][2]["id"]  # Rola "☢︎"
    if any(role.id == attach_files_off_role_id for role in member.roles):
        return discord.Member.default_avatar.url
    return member.display_avatar.url


async def create_shop_embed(
    ctx: Context,
    balance: int,
    role_price_map: dict,
    premium_roles: list,
    page: int,
    viewer: discord.Member,
    member: discord.Member,
):
    """Create the new, more persuasive shop embed according to zaGadka requirements."""

    # Get social proof data
    premium_count = await get_premium_users_count(ctx)

    # Get currency service for unit
    async with ctx.bot.get_db() as session:
        currency_service = await ctx.bot.get_service(ICurrencyService, session)
        currency_unit = currency_service.get_currency_unit()

    # Current role information
    current_role_info = ""
    if premium_roles:
        role_data = premium_roles[0]
        role_name = role_data.get("role_name", "Unknown Role")
        expiration_date = role_data.get("expiration_date")
        if expiration_date:
            formatted_date = discord.utils.format_dt(expiration_date, "D")
            current_role_info = f"🗓 `Aktualna rola:` {role_name} (do {formatted_date})"
        else:
            current_role_info = f"🗓 `Aktualna rola:` {role_name}"
    else:
        current_role_info = "🗓 `Aktualna rola:` Brak"

    # Available roles section
    roles_lines = []
    for role_name, price in role_price_map.items():
        if role_name == "zG100":
            roles_lines.append(f"• `{role_name}` – {price}{currency_unit} (popularna)")
        elif role_name == "zG1000":
            roles_lines.append(f"• `{role_name}` – {price}{currency_unit} (premium)")
        else:
            roles_lines.append(f"• `{role_name}` – {price}{currency_unit}")

    # Build compact description
    lines = [
        f"📌 {premium_count} użytkowników wybrało premium",
        "",
        f"💠 `Saldo:` {balance}{currency_unit}",
        f"🆔 `ID:` {viewer.id}",
        current_role_info,
        "",
        "🔸 `Dostępne rangi:`",
        *roles_lines,
        "",
        "🎁 Zakup usuwa wszystkie blokady",
        f"⏳ {'30 dni' if page == 1 else '1 rok (10 miesięcy + 2 gratis)'}",
        "",
        f"📌 `Wpłata:` ID ({viewer.id}) w polu nick",
        "💳 50zł = 50G = automatyczna ranga",
        "",
        "🤝 Dziękujemy za wsparcie!",
    ]

    embed = discord.Embed(
        title="✨ SKLEP PREMIUM",
        description="\n".join(lines),
        color=viewer.color if viewer.color.value != 0 else discord.Color.blurple(),
    )

    # Set avatar
    avatar_url = get_user_avatar_url(viewer, ctx.bot)
    embed.set_thumbnail(url=avatar_url)

    # Add footer with helpful tip
    embed.set_footer(
        text="💡 Kliknij rangę aby kupić • 'Opis ról' = szczegóły",
        icon_url=ctx.bot.user.display_avatar.url,
    )

    return embed


async def create_role_description_embed(
    ctx: Context,
    page: int,
    premium_roles: list,
    balance: int,
    viewer: discord.Member,
    member: discord.Member,
):
    role = premium_roles[page - 1]
    role_name = role["name"]

    # Get currency service for unit
    async with ctx.bot.get_db() as session:
        currency_service = await ctx.bot.get_service(ICurrencyService, session)
        currency_unit = currency_service.get_currency_unit()

    mastercard_emoji = ctx.bot.config.get("emojis", {}).get("mastercard", "💳")

    # Build compact description
    lines = [f"• {feature}" for feature in role["features"]]
    lines.append("")

    # Price info
    price = role["price"]
    annual_price = price * 10
    lines.append(f"💰 `Cena:` {price}{currency_unit}/mies. lub {annual_price}{currency_unit}/rok")
    lines.append(f"💠 `Saldo:` {balance}{currency_unit}")

    # Additional info
    extra_info = []
    if role.get("team_size", 0) > 0:
        extra_info.append(f"Drużyna: {role['team_size']} osób")
    if role.get("moderator_count", 0) > 0:
        extra_info.append(f"Moderatorzy: {role['moderator_count']}")
    if role.get("points_multiplier", 0) > 0:
        extra_info.append(f"Bonus: +{role['points_multiplier']}%")

    if extra_info:
        lines.append("")
        lines.append(f"📊 `Info:` {' • '.join(extra_info)}")

    embed = discord.Embed(
        title=f"{role_name} {mastercard_emoji}",
        description="\n".join(lines),
        color=viewer.color if viewer.color.value != 0 else discord.Color.blurple(),
    )

    avatar_url = get_user_avatar_url(viewer, ctx.bot)
    embed.set_thumbnail(url=avatar_url)

    return embed
