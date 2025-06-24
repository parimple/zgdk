"""Embeds for the shop cog."""
import discord
from discord.ext.commands import Context

from datasources.queries import RoleQueries
from utils.currency import CURRENCY_UNIT


async def get_premium_users_count(ctx: Context) -> int:
    """Get total count of users with any premium role for social proof."""
    try:
        async with ctx.bot.get_db() as session:
            # Count unique members with any premium role
            premium_users_count = await RoleQueries.count_unique_premium_users(session)
            return premium_users_count
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

    # Build the main description with social proof
    social_proof = f"📌 **Łącznie już {premium_count} użytkowników wybrało dodatkowe możliwości na naszym serwerze.**"

    # User's current balance and ID (personalized)
    user_info = (
        f"💠 **Twoje saldo:** {balance}{CURRENCY_UNIT}\n"
        f"🆔 **Twoje Discord ID:** {viewer.id}"
    )

    # Current role information
    current_role_info = ""
    if premium_roles:
        current_role, role_obj = premium_roles[0]
        expiration_date = discord.utils.format_dt(current_role.expiration_date, "D")
        current_role_info = (
            f"🗓 **Aktualna rola:** {role_obj.name} (ważna do {expiration_date})"
        )
    else:
        current_role_info = (
            "🗓 **Aktualna rola:** Brak – pomyśl, czy nie warto dołączyć?"
        )

    # Available roles section with Cialdini techniques
    roles_section = "🔸 **Dostępne rangi:**"
    for role_name, price in role_price_map.items():
        if role_name == "zG100":
            roles_section += (
                f"\n• **{role_name}** – {price}{CURRENCY_UNIT} (najczęściej wybierana)"
            )
        elif role_name == "zG1000":
            roles_section += f"\n• **{role_name}** – {price}{CURRENCY_UNIT} (wyjątkowe przywileje dla wymagających)"
        else:
            roles_section += f"\n• **{role_name}** – {price}{CURRENCY_UNIT}"

    # Benefits and instructions
    benefits = "🎁 **Przy zakupie lub przedłużeniu rangi – automatycznie zdejmujemy wszystkie blokady.**"
    duration_info = (
        "⏳ **Każda ranga trwa 30 dni – możesz w każdej chwili ją przedłużyć.**"
    )
    payment_instructions = f"📌 **Podczas wpłaty pamiętaj:** Wpisz swoje Discord ID ({viewer.id}) w polu 'Wpisz swój nick'"
    auto_payment_info = (
        "💳 **Wpłata 50zł = 50G** – automatycznie nadaje odpowiednią rangę!"
    )
    thanks = "🤝 **Dziękujemy, że wspierasz rozwój społeczności zaGadki!**"

    # Combine all sections
    if page == 1:
        title = "✨ SKLEP Z RANGAMI – dołącz do elitarnego grona zaGadki!"
        description = f"{social_proof}\n\n{user_info}\n{current_role_info}\n\n{roles_section}\n\n{benefits}\n{duration_info}\n\n{payment_instructions}\n\n{auto_payment_info}\n\n{thanks}"
    else:
        title = "✨ SKLEP Z RANGAMI – dołącz do elitarnego grona zaGadki!"
        duration_info_yearly = "⏳ **Za zakup na rok płacisz za 10 miesięcy (2 miesiące gratis) – możesz w każdej chwili przedłużyć.**"
        description = f"{social_proof}\n\n{user_info}\n{current_role_info}\n\n{roles_section}\n\n{benefits}\n{duration_info_yearly}\n\n{payment_instructions}\n\n{auto_payment_info}\n\n{thanks}"

    embed = discord.Embed(
        title=title,
        description=description,
        color=viewer.color if viewer.color.value != 0 else discord.Color.blurple(),
    )

    # Set avatar
    avatar_url = get_user_avatar_url(viewer, ctx.bot)
    embed.set_thumbnail(url=avatar_url)

    # Add footer with helpful tip
    embed.set_footer(
        text="💡 Kliknij przycisk rangi, aby ją zakupić • Użyj 'Opis ról' dla szczegółów",
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

    mastercard_emoji = ctx.bot.config.get("emojis", {}).get("mastercard", "💳")
    embed = discord.Embed(
        title=f"Opis roli {role_name} {mastercard_emoji}",
        description="\n".join([f"• {feature}" for feature in role["features"]]),
        color=viewer.color if viewer.color.value != 0 else discord.Color.blurple(),
    )
    avatar_url = get_user_avatar_url(viewer, ctx.bot)
    embed.set_author(name=f"{viewer.display_name}", icon_url=avatar_url)
    embed.set_thumbnail(url=avatar_url)

    # Dodanie informacji o cenie
    price = role["price"]
    annual_price = price * 10  # Usunięto dodawanie 9
    embed.add_field(
        name="Ceny",
        value=(
            f"Miesięcznie: {price}{CURRENCY_UNIT}\n"
            f"Rocznie: {annual_price}{CURRENCY_UNIT} (2 miesiące gratis)"
        ),
        inline=False,
    )

    # Dodanie informacji o koncie
    embed.add_field(name="Stan konta", value=f"{balance}{CURRENCY_UNIT}", inline=False)

    # Dodatkowe informacje o roli
    if role.get("team_size", 0) > 0:
        embed.add_field(
            name="Drużyna",
            value=f"Maksymalna liczba osób: {role['team_size']}",
            inline=True,
        )
    if role.get("moderator_count", 0) > 0:
        embed.add_field(
            name="Moderatorzy",
            value=f"Liczba moderatorów: {role['moderator_count']}",
            inline=True,
        )
    if role.get("points_multiplier", 0) > 0:
        embed.add_field(
            name="Bonus punktów", value=f"+{role['points_multiplier']}%", inline=True
        )

    return embed
