import re
from pydantic import BaseModel
from mahjong.models import GameType
from aiogram.types import Message


class ParsedPlayer(BaseModel):
    """Витягнутий гравець з результатів."""

    username: str  # Посилання (@username або перший_назва)
    name: str | None = None  # Повне ім'я або first_name
    id: int | None = None  # Telegram user_id
    score: int


class Parser:
    """Простий парсер Telegram Message через entities."""

    SCORE_PATTERN = re.compile(r"(-?\d+)")

    def parse_results(self, message: Message) -> tuple[GameType, list[ParsedPlayer]]:
        """
        Витягує гравців (username/id) та очки з Message.

        Returns:
            (GameType, list[ParsedPlayer]): (YONMA|SANMA, [ParsedPlayer, ...])
        """
        text = message.text or ""
        players = []

        # Витягуємо всі mention/text_mention entities
        for entity in message.entities or []:
            if entity.type == "mention":
                # @username
                username = text[entity.offset : entity.offset + entity.length][
                    1:
                ]  # Видаляємо @
                name = None
                player_id = None
            elif entity.type == "text_mention":
                # Юзер без username - беремо з User об'єкту
                if not entity.user:
                    continue
                username = (
                    entity.user.username
                    or entity.user.first_name
                    or str(entity.user.id)
                )
                name = entity.user.first_name
                player_id = entity.user.id
            else:
                continue

            # Шукаємо очки після mention
            pos = entity.offset + entity.length
            score_match = self.SCORE_PATTERN.search(text[pos:])
            if not score_match:
                continue

            score = int(score_match.group(1))
            players.append(
                ParsedPlayer(username=username, name=name, id=player_id, score=score)
            )

        # Перевірка на дублікати гравців
        player_ids = [p.id for p in players if p.id is not None]
        player_usernames = [p.username.lower() for p in players if p.username]

        # Перевірка дублікатів по ID
        if len(player_ids) != len(set(player_ids)):
            raise ValueError(
                "Помилка: один і той самий гравець зустрічається кілька разів"
            )

        # Перевірка дублікатів по username
        if len(player_usernames) != len(set(player_usernames)):
            duplicates = [u for u in player_usernames if player_usernames.count(u) > 1]
            raise ValueError(
                f"Помилка: гравець @{duplicates[0]} зустрічається кілька разів"
            )

        # Визначаємо тип гри
        game_type = (
            GameType.YONMA
            if len(players) == 4
            else GameType.SANMA
            if len(players) == 3
            else None
        )

        if not game_type:
            raise ValueError(f"Очікується 3 або 4 гравці, отримано: {len(players)}")

        return game_type, players


if __name__ == "__main__":
    from unittest.mock import Mock

    parser = Parser()

    # Тест 1: Yonma
    print("Test 1: Yonma")
    msg = Mock(spec=Message)
    msg.text = "@alice 28000 @bob 25000 @charlie 23000 @dave 24000"
    msg.entities = [
        Mock(type="mention", offset=0, length=6),  # @alice at 0-5
        Mock(type="mention", offset=13, length=4),  # @bob at 13-16
        Mock(type="mention", offset=24, length=8),  # @charlie at 24-31
        Mock(type="mention", offset=39, length=5),  # @dave at 39-43
    ]
    game_type, players = parser.parse_results(msg)
    print(f"  Type: {game_type}, Players: {players}\n")

    # Тест 2: Sanma
    print("Test 2: Sanma")
    msg = Mock(spec=Message)
    msg.text = "@alice 28000 @bob 25000 @charlie 24000"
    msg.entities = [
        Mock(type="mention", offset=0, length=6),  # @alice at 0-5
        Mock(type="mention", offset=13, length=4),  # @bob at 13-16
        Mock(type="mention", offset=24, length=8),  # @charlie at 24-31
    ]
    game_type, players = parser.parse_results(msg)
    print(f"  Type: {game_type}, Players: {players}\n")

    # Тест 3: text_mention
    print("Test 3: text_mention with User IDs")
    user1 = Mock(id=123, username="alice", first_name="Alice")
    user2 = Mock(id=456, username=None, first_name="Bob")
    user3 = Mock(id=789, username="charlie", first_name="Charlie")
    msg = Mock(spec=Message)
    msg.text = "Alice 30000 Bob 20000 Charlie 10000"
    msg.entities = [
        Mock(type="text_mention", offset=0, length=5, user=user1),  # Alice at 0-4
        Mock(type="text_mention", offset=12, length=3, user=user2),  # Bob at 12-14
        Mock(type="text_mention", offset=22, length=7, user=user3),  # Charlie at 22-28
    ]
    game_type, players = parser.parse_results(msg)
    print(f"  Type: {game_type}, Players: {players}\n")
