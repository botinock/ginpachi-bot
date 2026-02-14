from os import getenv
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandObject

from db.client import get_db_client
from bot.filters import IsAdmin
from mahjong.service import MahjongService
from mahjong.models import GameType

ADMIN_ID = getenv("ADMIN_ID")
db_client = get_db_client()
mahjong_service = MahjongService(db_client)

router = Router()


@router.message(Command("mahjong_help"))
async def handle_help(message: Message):
    """Показує всі доступні команди для маджонгу"""
    help_text = """
<b>Mahjong Bot - Довідка</b>

<b>Реєстрація:</b>
/mahjong_register - Зареєструватися в системі

<b>Ігрові команди:</b>
/result @гравець1 очки1 @гравець2 очки2 ... - Записати результат
/mahjong_edit match_XXX - Редагувати матч (потім надішліть нові дані)
/mahjong_delete match_XXX тип_гри - Видалити матч (yonma/sanma)

<b>Статистика:</b>
/mahjong_stats yonma - Ваша особиста статистика
/mahjong_ranking yonma - Таблиця лідерів Yonma
/mahjong_ranking sanma - Таблиця лідерів Sanma

<b>Інформація:</b>
/mahjong_help - Ця довідка

<b>Приклад запису гри:</b>
/result @alice 32000 @bob 28000 @charlie 24000 @dave 16000

<b>Система автоматично:</b>
- Визначає тип гри (3 гравці = Sanma, 4 = Yonma)
- Розраховує Uma та Oka за правилами сезону
- Перевіряє суму очок (має бути рівно 25000×4 або 35000×3)
- Генерує унікальний ID матчу (match_001, match_002...)
- Оновлює рейтинг гравців
"""
    await message.reply(help_text)


@router.message(Command("mahjong_create_season"), IsAdmin())
async def handle_create_season(message: Message, command: CommandObject):
    """
    Створює новий сезон (тільки для адмінів).
    Season ID генерується автоматично на основі поточної дати.

    Використання:
    /mahjong_create_season name:"2026 Q1 Yonma" type:yonma start:25000 return:30000 uma:15,5,-5,-15 oka:20
    """
    if not command.args:
        help_text = """
<b>Створення сезону</b>

Season ID генерується автоматично (напр. 2026Q1_yonma)

<b>Формат 1 (однорядковий):</b>
/mahjong_create_season name:"Назва" type:yonma start:25000 return:30000 uma:15,5,-5,-15 oka:20

<b>Формат 2 (багаторядковий):</b>
/mahjong_create_season
name: "Назва"
type: yonma
start: 25000
return: 30000
uma: 15,5,-5,-15
oka: 20

<b>Параметри:</b>
• name - Назва сезону (в лапках)
• type - yonma або sanma
• start - Стартові очки (25000/35000)
• return - Return points (30000/40000)
• uma - Uma через кому (4 числа для yonma, 3 для sanma)
• oka - Oka бонус для 1-го місця

<b>Приклад Yonma:</b>
/mahjong_create_season name:"Winter 2026 Yonma" type:yonma start:25000 return:30000 uma:15,5,-5,-15 oka:0

<b>Приклад Sanma:</b>
/mahjong_create_season name:"Winter 2026 Sanma" type:sanma start:35000 return:40000 uma:15,0,-15 oka:0
"""
        await message.reply(help_text)
        return

    try:
        season_id = await mahjong_service.create_season_from_command(command.args)
        await message.reply(f"Сезон успішно створено!\nID: <code>{season_id}</code>")
        if ADMIN_ID:
            from bot.bot import bot

            await bot.send_message(ADMIN_ID, f"Створено новий сезон: {season_id}")
    except ValueError as e:
        await message.reply(str(e))
    except Exception as e:
        await message.reply(f"Помилка: {e}")


@router.message(Command("mahjong_result", "result"))
async def handle_match_result(message: Message):
    """
    Зберігає результат матчу.

    Використання:
    /result @player1 32000 @player2 28000 @player3 24000 @player4 16000
    """
    if not message.from_user:
        return

    try:
        match_result, ranking_changes = await mahjong_service.process_match(
            message=message, recorded_by=message.from_user.id
        )

        # Форматуємо відповідь
        result_text = f"Гру збережено!\n"
        result_text += f"ID: {match_result.match_id}\n"
        result_text += f"Тип гри: {match_result.game_type.value}\n\n"
        result_text += "Результати:\n"

        for player in match_result.players:
            result_text += f"#{player.placement} {player.display_name}: {player.raw_score} pts → {player.final_uma:+.1f}"

            # Показуємо зміну в рейтингу
            change_info = ranking_changes.get(player.id)
            if change_info and change_info["change"] is not None:
                change = change_info["change"]
                if change > 0:
                    result_text += f" [+{change}]"
                elif change < 0:
                    result_text += f" [{change}]"

                new_pos = change_info["new_position"]
                if new_pos:
                    result_text += f" (#{new_pos})"

            result_text += "\n"

        await message.reply(result_text)

    except ValueError as e:
        await message.reply(str(e))
    except Exception as e:
        await message.reply(f"Системна помилка: {e}")


@router.message(Command("mahjong_edit"))
async def handle_edit_match(message: Message, command: CommandObject):
    """
    Редагує існуючий матч.

    Використання:
    /mahjong_edit match_042
    @player1 30000 @player2 28000 @player3 24000 @player4 18000
    """
    if not message.from_user or not command.args:
        await message.reply(
            "Використання: /mahjong_edit match_XXX\n@player1 score1 @player2 score2 ..."
        )
        return

    match_id = command.args.split()[0]

    try:
        updated_match = await mahjong_service.edit_match(
            match_id=match_id, message=message, recorded_by=message.from_user.id
        )

        result_text = f"Матч {match_id} оновлено!\n\n"
        result_text += "Нові результати:\n"

        for player in updated_match.players:
            result_text += f"#{player.placement} {player.display_name}: {player.raw_score} pts → {player.final_uma:+.1f}\n"

        await message.reply(result_text)

    except ValueError as e:
        await message.reply(str(e))
    except Exception as e:
        await message.reply(f"❌ Системна помилка: {e}")


@router.message(Command("mahjong_delete"))
async def handle_delete_match(message: Message, command: CommandObject):
    """
    Видаляє матч.

    Використання:
    /mahjong_delete match_042 yonma
    """
    if not command.args:
        await message.reply(
            "Використання: /mahjong_delete match_XXX game_type (yonma/sanma)"
        )
        return

    args = command.args.split()
    if len(args) < 2:
        await message.reply("Вкажіть ID матчу та тип гри (yonma/sanma)")
        return

    match_id = args[0]
    game_type_str = args[1].lower()

    if game_type_str not in ["yonma", "sanma"]:
        await message.reply("Тип гри має бути 'yonma' або 'sanma'")
        return

    game_type = GameType.YONMA if game_type_str == "yonma" else GameType.SANMA

    try:
        await mahjong_service.delete_match(match_id, game_type)
        await message.reply(f"Матч {match_id} видалено")

    except Exception as e:
        await message.reply(f"Помилка: {e}")


@router.message(Command("mahjong_register"))
async def handle_register_player(message: Message, command: CommandObject):
    """
    Реєструє гравця в системі.

    Використання:
    /mahjong_register
    """
    if not message.from_user:
        return

    user_id = message.from_user.id
    username = (
        message.from_user.username or message.from_user.first_name or str(user_id)
    )
    display_name = (
        message.from_user.first_name or message.from_user.username or "Player"
    )

    try:
        await mahjong_service.register_player(user_id, username, display_name)
        await message.reply(f"Ви зареєстровані як '{display_name}'!")
    except ValueError as e:
        await message.reply(str(e))
    except Exception as e:
        await message.reply(f"Помилка: {e}")


@router.message(Command("mahjong_ranking", "mahjong_top"))
async def handle_ranking(message: Message, command: CommandObject):
    """
    Показує таблицю лідерів.

    Використання:
    /mahjong_ranking yonma
    /mahjong_ranking sanma
    """
    game_type_str = (command.args or "yonma").lower()

    if game_type_str not in ["yonma", "sanma"]:
        await message.reply("Тип гри має бути 'yonma' або 'sanma'")
        return

    game_type = GameType.YONMA if game_type_str == "yonma" else GameType.SANMA

    try:
        ranking = await mahjong_service.get_season_ranking(game_type, limit=20)

        if not ranking:
            await message.reply("Таблиця рейтингу ще порожня")
            return

        ranking_text = f"Таблиця лідерів - {game_type.value.upper()}\n\n"

        for idx, player_stats in enumerate(ranking, 1):
            ranking_text += f"{idx}. {player_stats.display_name}\n"
            ranking_text += f"   Очки: {player_stats.total_score:+.1f} | Ігор: {player_stats.games_played}\n"
            ranking_text += (
                f"   Середнє місце: {player_stats.average_placement:.2f}\n\n"
            )

        await message.reply(ranking_text)

    except Exception as e:
        await message.reply(f"Помилка: {e}")


@router.message(Command("mahjong_stats", "mahjong_profile"))
async def handle_player_stats(message: Message, command: CommandObject):
    """
    Показує статистику гравця.

    Використання:
    /mahjong_stats yonma - Ваша статистика по Yonma
    /mahjong_stats sanma - Ваша статистика по Sanma
    """
    if not message.from_user:
        return

    game_type_str = (command.args or "yonma").lower()

    if game_type_str not in ["yonma", "sanma"]:
        await message.reply("Тип гри має бути 'yonma' або 'sanma'")
        return

    game_type = GameType.YONMA if game_type_str == "yonma" else GameType.SANMA

    try:
        stats, position = await mahjong_service.get_player_stats(
            message.from_user.id, game_type
        )

        if not stats:
            await message.reply(f"У вас ще немає статистики в {game_type.value}")
            return

        stats_text = f"<b>Ваша статистика - {game_type.value.upper()}</b>\n\n"

        if position:
            stats_text += f"Місце в рейтингу: <b>#{position}</b>\n"

        stats_text += f"Очки: <b>{stats.total_score:+.1f}</b>\n"
        stats_text += f"Зіграно ігор: <b>{stats.games_played}</b>\n"
        stats_text += f"Середнє місце: <b>{stats.average_placement:.2f}</b>\n\n"

        stats_text += "<b>Місця:</b>\n"
        stats_text += f"1-е місце: {stats.placements.get('1', 0)} разів\n"
        stats_text += f"2-е місце: {stats.placements.get('2', 0)} разів\n"
        stats_text += f"3-є місце: {stats.placements.get('3', 0)} разів\n"
        if game_type == GameType.YONMA:
            stats_text += f"4-е місце: {stats.placements.get('4', 0)} разів\n"

        stats_text += f"\n<b>Рекорди:</b>\n"
        stats_text += f"Найбільше очок: {stats.highest_raw_score}\n"
        stats_text += f"Найменше очок: {stats.lowest_raw_score}\n"
        stats_text += f"Середні очки: {stats.average_raw_score:.0f}\n"

        await message.reply(stats_text)

    except Exception as e:
        await message.reply(f"Помилка: {e}")
