"""Embeds for the shop cog."""
import discord
from discord.ext.commands import Context

from utils.currency import CURRENCY_UNIT


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
    if page == 1:
        title = "Sklep z rolami - ceny miesięczne"
        description = (
            "Aby zakupić rangę, kliknij przycisk odpowiadający jej nazwie.\n"
            "Za każde 10 zł jest 10G.\n"
            "Zakup lub przedłużenie dowolnej rangi zdejmuje wszystkie muty na serwerze.\n\n"
            f"**Twoje ID: {viewer.id}**\n"
            "Pamiętaj, aby podczas wpłaty wpisać swoje ID w polu 'Wpisz swój nick'"
        )
    else:
        title = "Sklep z rolami - ceny roczne"
        description = (
            "Za zakup na rok płacisz za 10 miesięcy (2 miesiące gratis).\n"
            "Za każde 10 zł jest 10G.\n"
            "Zakup lub przedłużenie dowolnej rangi zdejmuje wszystkie muty na serwerze.\n\n"
            f"**Twoje ID: {viewer.id}**\n"
            "Pamiętaj, aby podczas wpłaty wpisać swoje ID w polu 'Wpisz swój nick'"
        )

    embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
    avatar_url = get_user_avatar_url(viewer, ctx.bot)
    embed.set_author(name=f"{viewer.display_name}", icon_url=avatar_url)
    embed.set_thumbnail(url=avatar_url)
    embed.add_field(name="Twoje środki", value=f"{balance}{CURRENCY_UNIT}", inline=False)

    # Wyświetlanie aktualnych ról
    if premium_roles:
        current_role, role_obj = premium_roles[0]
        expiration_date = discord.utils.format_dt(current_role.expiration_date, "R")
        embed.add_field(
            name="Aktualna rola", value=f"{role_obj.name}\nWygasa: {expiration_date}", inline=False
        )

    # Wyświetlanie dostępnych ról
    for role_name, price in role_price_map.items():
        embed.add_field(name=role_name, value=f"Cena: {price}{CURRENCY_UNIT}", inline=True)

    embed.set_footer(text="Użyj przycisku 'Opis ról' aby zobaczyć szczegółowe informacje o rangach")
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

    embed = discord.Embed(
        title=f"Opis roli {role_name}",
        description="\n".join([f"• {feature}" for feature in role["features"]]),
        color=discord.Color.blurple(),
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
            name="Drużyna", value=f"Maksymalna liczba osób: {role['team_size']}", inline=True
        )
    if role.get("moderator_count", 0) > 0:
        embed.add_field(
            name="Moderatorzy", value=f"Liczba moderatorów: {role['moderator_count']}", inline=True
        )
    if role.get("points_multiplier", 0) > 0:
        embed.add_field(name="Bonus punktów", value=f"+{role['points_multiplier']}%", inline=True)

    return embed
