from os import getenv

from google.cloud.firestore import AsyncClient

from mahjong.models import PlayerSeasonStats, MatchPlayer, GameType


class StatsRepository:
    def __init__(self, client: AsyncClient):
        self.client = client
        self.seasons_collection = getenv(
            "MAHJONG_SEASONS_COLLECTION", "mahjong_seasons"
        )

    async def get_player_stats(
        self, season_id: str, player_id: int
    ) -> PlayerSeasonStats | None:
        doc_ref = (
            self.client.collection(self.seasons_collection)
            .document(season_id)
            .collection("player_stats")
            .document(str(player_id))
        )
        doc = await doc_ref.get()
        if doc.exists:
            return PlayerSeasonStats.model_validate(doc.to_dict())
        return None

    async def update_player_stats(
        self,
        season_id: str,
        player_id: int,
        display_name: str,
        match_player: MatchPlayer,
        game_type: GameType,
    ) -> None:
        """Оновлює статистику гравця після нового матчу"""
        stats_ref = (
            self.client.collection(self.seasons_collection)
            .document(season_id)
            .collection("player_stats")
            .document(str(player_id))
        )

        doc = await stats_ref.get()

        if not doc.exists:
            # Перший матч гравця
            stats = PlayerSeasonStats(
                id=player_id,
                display_name=display_name,
                game_type=game_type,
                total_score=match_player.final_uma,
                games_played=1,
                placements={
                    "1": 1 if match_player.placement == 1 else 0,
                    "2": 1 if match_player.placement == 2 else 0,
                    "3": 1 if match_player.placement == 3 else 0,
                    "4": 1 if match_player.placement == 4 else 0,
                },
                highest_raw_score=match_player.raw_score,
                lowest_raw_score=match_player.raw_score,
                average_raw_score=float(match_player.raw_score),
            )
            await stats_ref.set(stats.model_dump())
        else:
            # Оновлення існуючої статистики
            current = doc.to_dict()

            new_total_score = current.get("total_score", 0) + match_player.final_uma
            new_games_played = current.get("games_played", 0) + 1

            new_placements = current.get("placements", {"1": 0, "2": 0, "3": 0, "4": 0})
            placement_key = str(match_player.placement)
            new_placements[placement_key] = new_placements.get(placement_key, 0) + 1

            new_highest = max(
                current.get("highest_raw_score", 0), match_player.raw_score
            )
            new_lowest = min(
                current.get("lowest_raw_score", float("inf")), match_player.raw_score
            )

            # Правильний розрахунок середнього
            old_avg = current.get("average_raw_score", 0)
            old_games = current.get("games_played", 0)
            new_average = (
                old_avg * old_games + match_player.raw_score
            ) / new_games_played

            await stats_ref.update(
                {
                    "total_score": new_total_score,
                    "games_played": new_games_played,
                    "placements": new_placements,
                    "highest_raw_score": new_highest,
                    "lowest_raw_score": new_lowest,
                    "average_raw_score": new_average,
                }
            )

    async def get_season_ranking(
        self, season_id: str, limit: int = 50
    ) -> list[PlayerSeasonStats]:
        """Повертає топ гравців сезону"""
        query = (
            self.client.collection(self.seasons_collection)
            .document(season_id)
            .collection("player_stats")
            .order_by("total_score", direction="DESCENDING")
            .limit(limit)
        )

        ranking: list[PlayerSeasonStats] = []
        async for doc in query.stream():
            ranking.append(PlayerSeasonStats.model_validate(doc.to_dict()))
        return ranking

    async def recalculate_player_stats(
        self, season_id: str, player_id: int, display_name: str, game_type: GameType
    ) -> None:
        """Перераховує статистику гравця з нуля на основі всіх його матчів"""
        from mahjong.models import MatchResult

        # Отримуємо всі матчі гравця
        matches_ref = (
            self.client.collection(self.seasons_collection)
            .document(season_id)
            .collection("matches")
        )

        # Збираємо всі матчі де грав цей гравець
        all_matches = []
        async for doc in matches_ref.stream():
            match_data = doc.to_dict()
            match_data["match_id"] = doc.id
            match = MatchResult.model_validate(match_data)

            # Перевіряємо чи грав цей гравець
            if any(p.id == player_id for p in match.players):
                all_matches.append(match)

        if not all_matches:
            # Видаляємо статистику якщо матчів немає
            stats_ref = (
                self.client.collection(self.seasons_collection)
                .document(season_id)
                .collection("player_stats")
                .document(str(player_id))
            )
            await stats_ref.delete()
            return

        # Рахуємо статистику з нуля
        total_score = 0.0
        games_played = len(all_matches)
        placements = {"1": 0, "2": 0, "3": 0, "4": 0}
        raw_scores = []

        for match in all_matches:
            for player in match.players:
                if player.id == player_id:
                    total_score += player.final_uma
                    placements[str(player.placement)] += 1
                    raw_scores.append(player.raw_score)

        stats = PlayerSeasonStats(
            id=player_id,
            display_name=display_name,
            game_type=game_type,
            total_score=total_score,
            games_played=games_played,
            placements=placements,
            highest_raw_score=max(raw_scores),
            lowest_raw_score=min(raw_scores),
            average_raw_score=sum(raw_scores) / len(raw_scores),
        )

        # Зберігаємо нову статистику
        stats_ref = (
            self.client.collection(self.seasons_collection)
            .document(season_id)
            .collection("player_stats")
            .document(str(player_id))
        )
        await stats_ref.set(stats.model_dump())

    async def get_player_ranking_position(
        self, season_id: str, player_id: int
    ) -> int | None:
        """Повертає позицію гравця в рейтингу (1-based)"""
        query = (
            self.client.collection(self.seasons_collection)
            .document(season_id)
            .collection("player_stats")
            .order_by("total_score", direction="DESCENDING")
        )

        position = 1
        async for doc in query.stream():
            if doc.id == str(player_id):
                return position
            position += 1

        return None
