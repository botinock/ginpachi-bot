from os import getenv

from google.cloud.firestore import AsyncClient
from google.cloud.firestore import Increment

from mahjong.models import Season, GameType


class SeasonRepository:
    def __init__(self, client: AsyncClient):
        self.client = client
        self.collection = self.client.collection(
            getenv("MAHJONG_SEASONS_COLLECTION", "mahjong_seasons")
        )

    async def get_season(self, season_id: str) -> Season | None:
        doc = await self.collection.document(season_id).get()
        if doc.exists:
            return Season.model_validate(doc.to_dict())
        return None

    async def create_season(self, season: Season) -> None:
        await self.collection.document(season.season_id).set(season.model_dump())

    async def update_season(self, season: Season) -> None:
        await self.collection.document(season.season_id).update(season.model_dump())

    async def get_active_season(self, game_type: GameType) -> Season | None:
        """Знаходить активний сезон для конкретного типу гри"""
        query = (
            self.collection.where("is_active", "==", True)
            .where("game_type", "==", game_type.value)
            .limit(1)
        )
        async for doc in query.stream():
            return Season.model_validate(doc.to_dict())
        return None

    async def list_seasons(self, limit: int = 10) -> list[Season]:
        query = self.collection.order_by("created_at", direction="DESCENDING").limit(
            limit
        )
        seasons: list[Season] = []
        async for doc in query.stream():
            seasons.append(Season.model_validate(doc.to_dict()))
        return seasons

    async def set_active_season(self, season_id: str) -> None:
        """Встановлює сезон як активний"""
        season_ref = self.collection.document(season_id)
        await season_ref.update({"is_active": True})

    async def increment_match_counter(self, season_id: str) -> int:
        """Інкрементує лічильник матчів та повертає новий номер"""

        season_ref = self.collection.document(season_id)
        await season_ref.update({"match_counter": Increment(1)})

        # Отримуємо оновлене значення
        doc = await season_ref.get()
        return doc.get("match_counter")
