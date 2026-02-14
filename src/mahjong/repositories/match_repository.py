from os import getenv

from google.cloud.firestore import AsyncClient
from google.cloud.firestore import Increment

from mahjong.models import MatchResult


class MatchRepository:
    def __init__(self, client: AsyncClient):
        self.client = client
        self.seasons_collection = getenv(
            "MAHJONG_SEASONS_COLLECTION", "mahjong_seasons"
        )

    async def get_match(self, season_id: str, match_id: str) -> MatchResult | None:
        match_ref = (
            self.client.collection(self.seasons_collection)
            .document(season_id)
            .collection("matches")
            .document(match_id)
        )
        doc = await match_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data["match_id"] = match_id
            return MatchResult.model_validate(data)
        return None

    async def create_match(self, season_id: str, match: MatchResult) -> str:
        """Створює матч з автоматичним sequential ID"""

        # Інкрементуємо лічильник та отримуємо номер
        season_ref = self.client.collection(self.seasons_collection).document(season_id)
        await season_ref.update({"match_counter": Increment(1)})

        # Отримуємо новий номер
        season_doc = await season_ref.get()
        if not season_doc.exists:
            raise ValueError(f"Сезон {season_id} не знайдено")

        counter = season_doc.get("match_counter")
        match_id = f"match_{counter:03d}"

        # Зберігаємо матч
        match_ref = season_ref.collection("matches").document(match_id)
        match_data = match.model_dump()
        match_data["match_id"] = match_id
        await match_ref.set(match_data)

        return match_id

    async def update_match(
        self, season_id: str, match_id: str, match: MatchResult
    ) -> None:
        """Оновлює існуючий матч"""
        match_ref = (
            self.client.collection(self.seasons_collection)
            .document(season_id)
            .collection("matches")
            .document(match_id)
        )
        match_data = match.model_dump()
        match_data["match_id"] = match_id
        await match_ref.update(match_data)

    async def delete_match(self, season_id: str, match_id: str) -> None:
        """Видаляє матч"""
        match_ref = (
            self.client.collection(self.seasons_collection)
            .document(season_id)
            .collection("matches")
            .document(match_id)
        )
        await match_ref.delete()

    async def list_matches(self, season_id: str, limit: int = 50) -> list[MatchResult]:
        """Повертає останні матчі сезону"""
        query = (
            self.client.collection(self.seasons_collection)
            .document(season_id)
            .collection("matches")
            .order_by("date", direction="DESCENDING")
            .limit(limit)
        )

        matches: list[MatchResult] = []
        async for doc in query.stream():
            data = doc.to_dict()
            data["match_id"] = doc.id
            matches.append(MatchResult.model_validate(data))
        return matches
