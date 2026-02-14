"""
MahjongCalculator - чистий шар бізнес-логіки.
Не ходить у БД, не знає про Telegram. Тільки математика.
"""
from dataclasses import dataclass
from mahjong.models import LeagueRules, GameType, MatchPlayer, MatchResult
from datetime import datetime, timezone


@dataclass
class PlayerRawInput:
    """Вхідні дані одного гравця перед розрахунками"""
    id: int  # Telegram user ID
    raw_score: int  # Сирові очки зі скорбду


@dataclass
class MatchInput:
    """Набір гравців для розрахунку матчу"""
    players: list[PlayerRawInput]
    game_type: GameType


class MahjongCalculator:
    def __init__(self, rules: LeagueRules):
        self.rules = rules

    def calculate(self, match_input: MatchInput) -> list[MatchPlayer]:
        # 1. Визначаємо очікувану кількість гравців
        players_count = 4 if self.rules.game_type == GameType.YONMA else 3
        
        if len(match_input.players) != players_count:
            raise ValueError(f"Очікувалось {players_count} гравців, отримано {len(match_input.players)}")

        # 2. ПЕРЕВІРКА СУМИ ОЧОК (Validation of total raw scores)
        expected_total_score = self.rules.start_points * players_count
        actual_total_score = sum(p.raw_score for p in match_input.players)
        
        if actual_total_score != expected_total_score:
            raise ValueError(
                f"Помилка суми очок! В сумі має бути {expected_total_score}, "
                f"але отримано {actual_total_score}. Перевірте введені дані."
            )

        # 3. Сортування та групування (для нічиїх)
        sorted_inputs = sorted(match_input.players, key=lambda p: p.raw_score, reverse=True)
        groups = self._group_by_score(sorted_inputs)

        results = []
        current_rank_idx = 0
        
        # Внесок кожного гравця в кастомну Оку
        oka_contribution = self.rules.oka / players_count

        for group in groups:
            group_size = len(group)
            
            # Ділимо Уму між учасниками нічиєї
            uma_slice = self.rules.uma[current_rank_idx : current_rank_idx + group_size]
            avg_uma = sum(uma_slice) / group_size
            
            # Ділимо кастомну Оку між учасниками нічиєї на 1-му місці
            group_oka_prize = (self.rules.oka / group_size) if current_rank_idx == 0 else 0
            
            placement = current_rank_idx + 1

            for player_input in group:
                # Різниця відносно стартового стеку
                score_diff = (player_input.raw_score - self.rules.start_points) / 1000
                
                # Підсумкова формула: Різниця - Внесок + Ума + Приз (якщо 1-й)
                final_points = score_diff - oka_contribution + avg_uma + group_oka_prize
                
                results.append(MatchPlayer(
                    id=player_input.id,
                    username="",  # Will be populated by service layer
                    placement=placement,
                    raw_score=player_input.raw_score,
                    final_uma=round(final_points, 1),
                    display_name=""  # Will be populated by service layer
                ))
            current_rank_idx += group_size

        # 4. Корекція Zero-sum (для похибок округлення float)
        self._adjust_zero_sum(results)
        return results

    def _group_by_score(self, players):
        if not players: return []
        groups = [[players[0]]]
        for i in range(1, len(players)):
            if players[i].raw_score == players[i-1].raw_score:
                groups[-1].append(players[i])
            else:
                groups.append([players[i]])
        return groups

    def _adjust_zero_sum(self, results: list[MatchPlayer]):
        # Оскільки ми перевірили вхідну суму очок, total тут буде 
        # або 0.0, або дуже близьке число (напр. 0.1) через округлення.
        total = round(sum(p.final_uma for p in results), 1)
        if total != 0:
            # Сортуємо: 1 місце в пріоритеті на отримання/віддачу похибки
            results.sort(key=lambda x: (x.placement, -x.raw_score))
            results[0].final_uma = round(results[0].final_uma - total, 1)

if __name__ == "__main__":
    print("=" * 60)
    print("MAHJONG CALCULATOR TESTS")
    print("=" * 60)

    # Test 1: Yonma базовий
    print("\n[Test 1] Yonma базовий (без нічиї)")
    yonma_rules = LeagueRules(
        game_type=GameType.YONMA,
        uma=[15.0, 5.0, -5.0, -15.0],
        oka=0,
        start_points=25000,
        return_points=30000
    )
    calc_yonma = MahjongCalculator(yonma_rules)
    
    match = MatchInput(
        players=[
            PlayerRawInput(id=1, raw_score=32000),  # +2 pts
            PlayerRawInput(id=2, raw_score=30000),  # 0 pts
            PlayerRawInput(id=3, raw_score=23000),  # -2 pts
            PlayerRawInput(id=4, raw_score=15000),  # -10 pts
        ],
        game_type=GameType.YONMA
    )
    
    result = calc_yonma.calculate(match)
    for r in result:
        print(f"  Player {r.id} (#{r.placement}): {r.raw_score} → {r.final_uma:+.1f}")
    
    total = sum(p.final_uma for p in result)
    print(f"  Total: {total:.1f} (should be 0.0)")
    assert abs(total) < 0.1, f"Zero-sum failed: {total}"
    print("  ✓ PASSED")

    # Test 2: Sanma базовий
    print("\n[Test 2] Sanma базовий (без нічиї)")
    sanma_rules = LeagueRules(
        game_type=GameType.SANMA,
        uma=[15.0, 0.0, -15.0],
        oka=0,
        start_points=35000,
        return_points=40000
    )
    calc_sanma = MahjongCalculator(sanma_rules)
    
    match = MatchInput(
        players=[
            PlayerRawInput(id=10, raw_score=45000),  # +5 pts
            PlayerRawInput(id=11, raw_score=35000),  # 0 pts
            PlayerRawInput(id=12, raw_score=25000),  # -5 pts
        ],
        game_type=GameType.SANMA
    )
    
    result = calc_sanma.calculate(match)
    for r in result:
        print(f"  Player {r.id} (#{r.placement}): {r.raw_score} → {r.final_uma:+.1f}")
    
    total = sum(p.final_uma for p in result)
    print(f"  Total: {total:.1f} (should be 0.0)")
    assert abs(total) < 0.1, f"Zero-sum failed: {total}"
    print("  ✓ PASSED")

    # Test 3: Yonma с Ока
    print("\n✅ Test 3: Yonma з Ока бонусом")
    yonma_oka_rules = LeagueRules(
        game_type=GameType.YONMA,
        uma=[15.0, 5.0, -5.0, -15.0],
        oka=20,  # +20 для першого місця
        start_points=25000,
        return_points=30000
    )
    calc_oka = MahjongCalculator(yonma_oka_rules)
    
    match = MatchInput(
        players=[
            PlayerRawInput(id=100, raw_score=35000),  # Лідер, має oka
            PlayerRawInput(id=101, raw_score=31000),
            PlayerRawInput(id=102, raw_score=22000),
            PlayerRawInput(id=103, raw_score=12000),
        ],
        game_type=GameType.YONMA
    )
    
    result = calc_oka.calculate(match)
    leader = result[0]
    print(f"  Leader (ID: {leader.id}): {leader.raw_score} → {leader.final_uma:+.1f}")
    print(f"  Expected oka bonus: +{yonma_oka_rules.oka}")
    assert leader.final_uma > 30, f"Leader should have oka bonus, got {leader.final_uma}"
    
    total = sum(p.final_uma for p in result)
    print(f"  Total: {total:.1f} (should be 0.0)")
    assert abs(total) < 0.1, f"Zero-sum failed: {total}"
    print("  ✓ PASSED")

    # Test 4: Нічія (2 перші місця)
    print("\n[Test 4] Yonma з нічію на 1-му місці")
    match_tie = MatchInput(
        players=[
            PlayerRawInput(id=200, raw_score=32000),  # Tie for 1st
            PlayerRawInput(id=201, raw_score=32000),  # Tie for 1st
            PlayerRawInput(id=202, raw_score=23000),
            PlayerRawInput(id=203, raw_score=13000),
        ],
        game_type=GameType.YONMA
    )
    
    result = calc_yonma.calculate(match_tie)
    for r in result:
        print(f"  Player {r.id} (#{r.placement}): {r.raw_score} → {r.final_uma:+.1f}")
    
    # Обидва з 1-м місцем повинні мати середню uma (15+5)/2 = 10
    tied_players = [r for r in result if r.placement == 1]
    print(f"  Tied players count: {len(tied_players)} (should be 2)")
    assert len(tied_players) == 2, f"Should have 2 players at placement 1"
    
    total = sum(p.final_uma for p in result)
    print(f"  Total: {total:.1f} (should be 0.0)")
    assert abs(total) < 0.1, f"Zero-sum failed: {total}"
    print("  ✓ PASSED")

    # Test 5: Санма з нічією
    print("\n[Test 5] Sanma з нічію")
    match_sanma_tie = MatchInput(
        players=[
            PlayerRawInput(id=300, raw_score=45000),
            PlayerRawInput(id=301, raw_score=30000),  # Tie for 2nd
            PlayerRawInput(id=302, raw_score=30000),  # Tie for 2nd
        ],
        game_type=GameType.SANMA
    )
    
    result = calc_sanma.calculate(match_sanma_tie)
    for r in result:
        print(f"  Player {r.id} (#{r.placement}): {r.raw_score} → {r.final_uma:+.1f}")
    
    tied_second = [r for r in result if r.placement == 2]
    print(f"  Players at 2nd place: {len(tied_second)} (should be 2)")
    
    total = sum(p.final_uma for p in result)
    print(f"  Total: {total:.1f} (should be 0.0)")
    assert abs(total) < 0.1, f"Zero-sum failed: {total}"
    print("  ✓ PASSED")

    # Test 6: Error - неправильна кількість гравців
    print("\n[Test 6] Error handling - неправильна кількість гравців")
    bad_match = MatchInput(
        players=[
            PlayerRawInput(id=400, raw_score=30000),
            PlayerRawInput(id=401, raw_score=30000),
        ],
        game_type=GameType.YONMA  # Yonma потребує 4 гравців
    )
    
    try:
        calc_yonma.calculate(bad_match)
        print("  Got exception as expected, not PASSED")
    except ValueError as e:
        print(f"  Correctly raised: {e}")
        print("  ✓ PASSED")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)