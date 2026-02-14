from datetime import datetime, timezone
from os import getenv

from google.cloud.firestore import AsyncClient

from mahjong.models import Player


class PlayerRepository:
    def __init__(self, client: AsyncClient):
        self.client = client
        self.collection = self.client.collection(
            getenv("MAHJONG_PLAYERS_COLLECTION", "mahjong_players")
        )

    async def get_player(self, player_id: int) -> Player | None:
        doc = await self.collection.document(str(player_id)).get()
        if doc.exists:
            return Player.model_validate(doc.to_dict())
        return None

    async def create_player(self, player: Player) -> None:
        await self.collection.document(str(player.id)).set(player.model_dump())

    async def update_player(self, player: Player) -> None:
        player.updated_at = datetime.now(timezone.utc)
        await self.collection.document(str(player.id)).update(player.model_dump())

    async def list_players(self, limit: int = 100) -> list[Player]:
        query = self.collection.limit(limit)
        players: list[Player] = []
        async for doc in query.stream():
            players.append(Player.model_validate(doc.to_dict()))
        return players

    async def resolve_username_to_id(self, username: str) -> int | None:
        """Знаходить player_id за username"""
        username_lower = username.lower()
        query = self.collection.where("username", "==", username_lower).limit(1)
        async for doc in query.stream():
            data = doc.to_dict()
            return data.get("id")
        return None

    async def resolve_usernames_to_ids(self, usernames: list[str]) -> dict[str, int]:
        """Знаходить player_id для списку usernames. Викидає ValueError якщо хтось не знайдений"""
        if not usernames:
            return {}

        search_usernames = [u.lower() for u in usernames]
        query = self.collection.where(
            "username", "in", search_usernames[:30]
        )  # Firestore limit

        result = {}
        found_normalized = set()

        async for doc in query.stream():
            data = doc.to_dict()
            u_name = data.get("username", "").lower()
            u_id = data.get("id")

            if u_name and u_id:
                result[u_name] = u_id
                found_normalized.add(u_name)

        missing = set(search_usernames) - found_normalized
        if missing:
            raise ValueError(f"Гравців не знайдено: {', '.join(missing)}")

        return result
