from datetime import datetime
from google.cloud.firestore import AsyncClient
from aiogram.types import Message

from mahjong.parser import Parser, ParsedPlayer
from mahjong.calculator import MahjongCalculator, PlayerRawInput, MatchInput
from mahjong.repositories import (
    PlayerRepository,
    MatchRepository,
    StatsRepository,
    SeasonRepository,
)
from mahjong.models import GameType, MatchResult, Player, PlayerSeasonStats



class MahjongService:
    """Оркеструє весь процес від Message до Firestore"""

    def __init__(self, db_client: AsyncClient):
        self.player_repo = PlayerRepository(db_client)
        self.match_repo = MatchRepository(db_client)
        self.stats_repo = StatsRepository(db_client)
        self.season_repo = SeasonRepository(db_client)
        self.parser = Parser()

    def _define_current_season_id(self, game_type: GameType) -> str:
        """Визначає ID сезону за поточною датою. Eg: 2026Q1_yonma"""
        year = datetime.now().year
        month = datetime.now().month

        if 1 <= month <= 3:
            base_season_id = f"{year}Q1"
        elif 4 <= month <= 6:
            base_season_id = f"{year}Q2"
        elif 7 <= month <= 9:
            base_season_id = f"{year}Q3"
        else:
            base_season_id = f"{year}Q4"

        season_suffix = "yonma" if game_type == GameType.YONMA else "sanma"
        return f"{base_season_id}_{season_suffix}"

    async def _validate_players_registered(
        self, parsed_players: list[ParsedPlayer]
    ) -> None:
        """Перевіряє що всі гравці зареєстровані в БД"""
        unregistered = []
        for player in parsed_players:
            if player.id:
                existing = await self.player_repo.get_player(player.id)
                if not existing:
                    unregistered.append(player.username or str(player.id))

        if unregistered:
            raise ValueError(
                f"Гравці не зареєстровані: {', '.join(unregistered)}\n"
                f"Використайте команду /mahjong_register для реєстрації"
            )

    async def process_match(
        self, message: Message, recorded_by: int
    ) -> tuple[MatchResult, dict[int, dict]]:
        """
        Обробляє матч від Message до Firestore.

        Returns:
            tuple[MatchResult, dict]: MatchResult з match_id та зміни в рейтингу
        """
        # PARSING: Message → (GameType, list[ParsedPlayer])
        try:
            game_type, parsed_players = self.parser.parse_results(message)
        except ValueError as e:
            raise ValueError(f"Помилка парсингу: {e}")

        # Визначаємо сезон
        season_id = self._define_current_season_id(game_type)
        season = await self.season_repo.get_season(season_id)
        if not season:
            raise ValueError(
                f"Сезон {season_id} не знайдено. Створіть сезон через адмін панель."
            )

        # VALIDATION: Перевіряємо що всі гравці зареєстровані
        await self._validate_players_registered(parsed_players)

        # RESOLVING: username → player_id
        usernames = [p.username for p in parsed_players if not p.id]
        if usernames:
            try:
                username_to_id = await self.player_repo.resolve_usernames_to_ids(
                    usernames
                )
                for player in parsed_players:
                    if not player.id:
                        player.id = username_to_id.get(player.username.lower())
            except ValueError as e:
                raise ValueError(f"Помилка резолву ID: {e}")

        # Перевірка що всі ID знайдені
        if any(p.id is None for p in parsed_players):
            missing = [p.username for p in parsed_players if p.id is None]
            raise ValueError(
                f"Не вдалось знайти ID для гравців: {', '.join(missing)}"
            )

        # CALCULATING: ParsedPlayer → MatchPlayer
        calculator = MahjongCalculator(season.rules)
        calculator_input = MatchInput(
            players=[
                PlayerRawInput(id=p.id, raw_score=p.score)
                for p in parsed_players
                if p.id
            ],  # type: ignore
            game_type=game_type,
        )

        try:
            match_players = calculator.calculate(calculator_input)
        except ValueError as e:
            raise ValueError(f"Помилка розрахунку: {e}")

        # SYNC: Populate username and display_name from Player records in DB
        # This ensures MatchPlayer snapshots the current player identity
        player_records = {}
        for parsed_player in parsed_players:
            if parsed_player.id and parsed_player.id not in player_records:
                player_record = await self.player_repo.get_player(parsed_player.id)
                if player_record:
                    player_records[parsed_player.id] = player_record

        for match_player, parsed_player in zip(match_players, parsed_players):
            if parsed_player.id in player_records:
                player_record = player_records[parsed_player.id]
                match_player.username = player_record.username or parsed_player.username
                match_player.display_name = player_record.display_name or parsed_player.name or parsed_player.username
            else:
                # Fallback if player record not found (shouldn't happen due to validation)
                match_player.username = parsed_player.username.lower()
                match_player.display_name = parsed_player.name or f"@{parsed_player.username}"

        # SAVING: MatchResult → Firestore
        match_result = MatchResult(
            recorded_by=recorded_by,
            game_type=game_type,
            rules_snapshot=season.rules,
            players=match_players,
        )

        try:
            match_id = await self.match_repo.create_match(season_id, match_result)
            match_result.match_id = match_id
        except Exception as e:
            raise Exception(f"Помилка збереження матчу: {e}")

        # GET OLD RANKINGS: Запам'ятовуємо старі позиції
        old_rankings = {}
        for match_player in match_players:
            old_pos = await self.stats_repo.get_player_ranking_position(
                season_id, match_player.id
            )
            old_rankings[match_player.id] = old_pos

        # UPDATE STATS: Оновлюємо статистику гравців
        for match_player in match_players:
            try:
                await self.stats_repo.update_player_stats(
                    season_id=season_id,
                    player_id=match_player.id,
                    display_name=match_player.display_name,
                    match_player=match_player,
                    game_type=game_type,
                )
            except Exception as e:
                raise Exception(f"Помилка оновлення статистики: {e}")

        # GET NEW RANKINGS: Отримуємо нові позиції та рахуємо зміни
        ranking_changes = {}
        for match_player in match_players:
            new_pos = await self.stats_repo.get_player_ranking_position(
                season_id, match_player.id
            )
            old_pos = old_rankings.get(match_player.id)

            ranking_changes[match_player.id] = {
                "old_position": old_pos,
                "new_position": new_pos,
                "change": (old_pos - new_pos) if (old_pos and new_pos) else None,
                "display_name": match_player.display_name,
            }

        return match_result, ranking_changes

    async def edit_match(
        self, match_id: str, message: Message, recorded_by: int
    ) -> MatchResult:
        """
        Редагує існуючий матч.
        Повертає оновлений MatchResult.
        """
        # Парсимо нові дані
        try:
            game_type, parsed_players = self.parser.parse_results(message)
        except ValueError as e:
            raise ValueError(f"Помилка парсингу: {e}")

        # Визначаємо сезон
        season_id = self._define_current_season_id(game_type)
        season = await self.season_repo.get_season(season_id)
        if not season:
            raise ValueError(f"Сезон {season_id} не знайдено")

        # Перевіряємо що матч існує
        existing_match = await self.match_repo.get_match(season_id, match_id)
        if not existing_match:
            raise ValueError(f"Матч {match_id} не знайдено")

        # Валідуємо гравців
        await self._validate_players_registered(parsed_players)

        # Резолвимо ID
        usernames = [p.username for p in parsed_players if not p.id]
        if usernames:
            username_to_id = await self.player_repo.resolve_usernames_to_ids(usernames)
            for player in parsed_players:
                if not player.id:
                    player.id = username_to_id.get(player.username.lower())

        

        # Розраховуємо нові результати
        calculator = MahjongCalculator(season.rules)
        calculator_input = MatchInput(
            players=[
                PlayerRawInput(id=p.id, raw_score=p.score)
                for p in parsed_players
                if p.id
            ],  # type: ignore
            game_type=game_type,
        )
        match_players = calculator.calculate(calculator_input)

        # SYNC: Populate username and display_name from Player records in DB
        player_records = {}
        for parsed_player in parsed_players:
            if parsed_player.id and parsed_player.id not in player_records:
                player_record = await self.player_repo.get_player(parsed_player.id)
                if player_record:
                    player_records[parsed_player.id] = player_record

        for match_player, parsed_player in zip(match_players, parsed_players):
            if parsed_player.id in player_records:
                player_record = player_records[parsed_player.id]
                match_player.username = player_record.username or f"@{parsed_player.username}"
                match_player.display_name = player_record.display_name or parsed_player.name or f"@{parsed_player.username}"
            else:
                # Fallback
                match_player.username = parsed_player.username.lower()
                match_player.display_name = parsed_player.name or f"@{parsed_player.username}"

        # Оновлюємо матч
        updated_match = MatchResult(
            match_id=match_id,
            recorded_by=recorded_by,
            game_type=game_type,
            rules_snapshot=season.rules,
            players=match_players,
            date=existing_match.date,  # Зберігаємо оригінальну дату
        )
        await self.match_repo.update_match(season_id, match_id, updated_match)

        # Перераховуємо статистику для всіх гравців які були в старому або новому матчі
        affected_player_ids = set()
        for p in existing_match.players:
            affected_player_ids.add(p.id)
        for p in match_players:
            affected_player_ids.add(p.id)

        # Перераховуємо статистику для кожного гравця
        for player_id in affected_player_ids:
            # Знаходимо display_name з оновленого матчу або з БД
            display_name = f"Player {player_id}"
            for p in match_players:
                if p.id == player_id:
                    display_name = p.display_name
                    break
            else:
                # Якщо гравця немає в новому матчі, отримуємо з БД
                player = await self.player_repo.get_player(player_id)
                if player:
                    display_name = player.display_name or f"@{player.username}"

            await self.stats_repo.recalculate_player_stats(
                season_id=season_id,
                player_id=player_id,
                display_name=display_name,
                game_type=game_type,
            )

        return updated_match

    async def delete_match(self, match_id: str, game_type: GameType) -> None:
        """Видаляє матч та перераховує статистику"""
        season_id = self._define_current_season_id(game_type)

        # Отримуємо матч перед видаленням
        match = await self.match_repo.get_match(season_id, match_id)
        if not match:
            raise ValueError(f"Матч {match_id} не знайдено")

        # Видаляємо матч
        await self.match_repo.delete_match(season_id, match_id)

        # Перераховуємо статистику для всіх гравців матчу
        for match_player in match.players:
            # Отримуємо display_name з БД
            player = await self.player_repo.get_player(match_player.id)
            display_name = (
                player.display_name if player else f"Player {match_player.id}"
            )

            await self.stats_repo.recalculate_player_stats(
                season_id=season_id,
                player_id=match_player.id,
                display_name=display_name,
                game_type=game_type,
            )

    async def get_season_ranking(self, game_type: GameType, limit: int = 50):
        """Повертає топ гравців сезону"""
        season_id = self._define_current_season_id(game_type)
        return await self.stats_repo.get_season_ranking(season_id, limit)

    async def get_match(self, match_id: str, game_type: GameType) -> MatchResult | None:
        """Отримує матч за ID"""
        season_id = self._define_current_season_id(game_type)
        return await self.match_repo.get_match(season_id, match_id)

    async def get_player_stats(
        self, player_id: int, game_type: GameType
    ) -> tuple[PlayerSeasonStats | None, int | None]:
        """
        Отримує статистику гравця та його позицію в рейтингу.

        Returns:
            tuple[PlayerSeasonStats | None, int | None]: Stats та позиція в рейтингу
        """

        season_id = self._define_current_season_id(game_type)
        stats = await self.stats_repo.get_player_stats(season_id, player_id)

        if not stats:
            return None, None

        position = await self.stats_repo.get_player_ranking_position(
            season_id, player_id
        )
        return stats, position

    async def register_player(
        self, user_id: int, username: str, display_name: str
    ) -> None:
        """Реєструє нового гравця"""
        existing = await self.player_repo.get_player(user_id)
        if existing:
            raise ValueError(
                f"Гравець вже зареєстрований як '{existing.display_name}'"
            )

        player = Player(
            id=user_id,
            username=username.lower() if username else None,
            display_name=display_name,
        )
        await self.player_repo.create_player(player)

    async def create_season_from_command(self, args: str) -> str:
        """
        Створює сезон з command args.
        Format: name:"Name" type:yonma start:25000 return:30000 uma:15,5,-5,-15 oka:20
        Season ID генерується автоматично на основі дати (напр. 2026Q1_yonma)

        Returns:
            str: Згенерований season_id
        """
        import re
        from mahjong.models import Season, LeagueRules

        # Парсимо аргументи (підтримуємо і однорядковий, і багаторядковий формат)
        params = {}

        # name (в лапках) - підтримуємо з/без name:
        match = re.search(r'name\s*:\s*"([^"]+)"', args, re.IGNORECASE)
        if not match:
            raise ValueError('Не вказано name (має бути в лапках: name: "Назва")')
        params["name"] = match.group(1)

        # type
        match = re.search(r"type\s*:\s*(yonma|sanma)", args, re.IGNORECASE)
        if not match:
            raise ValueError("Не вказано type (yonma або sanma)")
        game_type_str = match.group(1).lower()
        game_type = GameType.YONMA if game_type_str == "yonma" else GameType.SANMA

        # start points
        match = re.search(r"start\s*:\s*(\d+)", args, re.IGNORECASE)
        if not match:
            raise ValueError("Не вказано start points")
        start_points = int(match.group(1))

        # return points
        match = re.search(r"return\s*:\s*(\d+)", args, re.IGNORECASE)
        if not match:
            raise ValueError("Не вказано return points")
        return_points = int(match.group(1))

        # uma
        match = re.search(r"uma\s*:\s*([-\d,\.]+)", args, re.IGNORECASE)
        if not match:
            raise ValueError("Не вказано uma")
        uma_str = match.group(1).replace(" ", "")  # Видаляємо пробіли
        uma = [float(x) for x in uma_str.split(",")]

        expected_uma_count = 4 if game_type == GameType.YONMA else 3
        if len(uma) != expected_uma_count:
            raise ValueError(
                f"Uma має містити {expected_uma_count} чисел для {game_type_str}"
            )

        # oka
        match = re.search(r"oka\s*:\s*(\d+)", args, re.IGNORECASE)
        if not match:
            raise ValueError("Не вказано oka")
        oka = int(match.group(1))

        # Генеруємо season_id автоматично на основі дати
        season_id = self._define_current_season_id(game_type)

        # Перевіряємо що сезон не існує
        existing = await self.season_repo.get_season(season_id)
        if existing:
            raise ValueError(f"Сезон {season_id} вже існує")

        # Створюємо сезон
        rules = LeagueRules(
            game_type=game_type,
            start_points=start_points,
            return_points=return_points,
            uma=uma,
            oka=oka,
        )

        season = Season(
            season_id=season_id,
            name=params["name"],
            game_type=game_type,
            is_active=True,
            rules=rules,
            match_counter=0,
        )

        await self.season_repo.create_season(season)
        return season_id
