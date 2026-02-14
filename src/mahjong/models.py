from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone


class GameType(str, Enum):
    """Тип гри: Yonma (4 гравці) або Sanma (3 гравці)"""

    YONMA = "yonma"
    SANMA = "sanma"


# Riichi mahjong models
class Player(BaseModel):
    id: int
    username: Optional[str] = None
    display_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LeagueRules(BaseModel):
    """Конфігурація правил для сезону або знімок для матчу"""

    game_type: GameType
    start_points: int = 25000
    return_points: int = 30000
    # Ума має бути масивом рівно з 4 чисел для Yonma та 3 чисел для Sanma
    uma: list[float]
    oka: int = 0


class Season(BaseModel):
    """Документ сезону (Колекція: seasons)"""

    season_id: str
    name: str
    game_type: GameType
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rules: LeagueRules
    match_counter: int = 0


class PlayerSeasonStats(BaseModel):
    """Статистика гравця в сезоні (Колекція: seasons/{id}/player_stats)"""

    id: int
    display_name: str
    game_type: GameType
    total_score: float = 0.0  # Сумарна Ума (головне поле для сортування)
    games_played: int = 0
    # Словник для зберігання кількості 1, 2, 3 та 4 місць (3 для Sanma, 4 для Yonma)
    placements: dict[str, int] = Field(
        default_factory=lambda: {"1": 0, "2": 0, "3": 0, "4": 0}
    )
    highest_raw_score: int = 0
    lowest_raw_score: int = 0
    average_raw_score: float = 0.0

    @property
    def average_placement(self) -> float:
        """Динамічне поле, не зберігається в БД, але зручне для бота"""
        if self.games_played == 0:
            return 0.0
        # Для Sanma не враховуємо 4-е місце
        placements_to_count = (
            {"1", "2", "3"}
            if self.game_type == GameType.SANMA
            else {"1", "2", "3", "4"}
        )
        total_places = sum(
            int(place) * self.placements.get(place, 0) for place in placements_to_count
        )
        return total_places / self.games_played


class MatchPlayer(BaseModel):
    """Результат конкретного гравця в матчі
    
    Snapshots player identity at match time for historical accuracy:
    - id: player_id (links to Player record)
    - username: lowercase unique identifier (matches Player.username)
    - display_name: player's display name at match time (can change later on Player record)
    """

    id: int
    username: str  # Synced from Player.username for reference
    placement: int = Field(..., ge=1, le=4)  # Місце строго від 1 до 4
    raw_score: int
    final_uma: float
    display_name: str  # Synced from Player.display_name, snapshots at match time


class MatchResult(BaseModel):
    """Документ збереженого матчу (Колекція: seasons/{id}/matches)"""

    # Optional, бо ID генерує Firestore при збереженні
    match_id: Optional[str] = None
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recorded_by: int
    game_type: GameType
    rules_snapshot: LeagueRules
    players: list[MatchPlayer] = Field(..., min_length=3, max_length=4)

    @field_validator("players")
    @classmethod
    def validate_players_count(cls, v: list[MatchPlayer], info) -> list[MatchPlayer]:
        game_type = info.data.get("game_type")
        if game_type == GameType.YONMA and len(v) != 4:
            raise ValueError("Yonma матч повинен мати рівно 4 гравців")
        elif game_type == GameType.SANMA and len(v) != 3:
            raise ValueError("Sanma матч повинен мати рівно 3 гравців")
        return v
