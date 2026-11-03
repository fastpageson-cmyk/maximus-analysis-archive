import numpy as np
import pandas as pd


def test_walk_min_is_straight_line_times_detour_at_4kmh():
    from scripts.build_store_candidates_v0 import walk_min

    # 위도 0.009도 ≈ 1.0008km → ×1.3 ÷ 4km/h ≈ 19.5분
    assert np.isclose(walk_min(37.5, 127.0, 37.509, 127.0), 1.0008 * 1.3 / 4 * 60, atol=0.05)
    assert walk_min(37.5, 127.0, 37.5, 127.0) == 0


def test_store_time_swaps_rep_walk_for_store_walk():
    from scripts.build_store_candidates_v0 import store_time, walk_min

    alight, rep, store = (37.5, 127.0), (37.5045, 127.0), (37.509, 127.0)
    t = store_time(20.0, *alight, *rep, *store)
    assert np.isclose(t, 20.0 - walk_min(*alight, *rep) + walk_min(*alight, *store))
    # 점포가 대표점이면 상권 시간 그대로
    assert np.isclose(store_time(20.0, *alight, *rep, *rep), 20.0)


def test_reach_flag_bands():
    from scripts.build_store_candidates_v0 import reach_flag

    flags = reach_flag(pd.Series([10, 25, 25.1, 30, 30.1]))
    assert flags.tolist() == ["안정", "안정", "경계", "경계", "제외"]


def test_gate_keeps_same_purpose_non_franchise_only():
    from scripts.build_store_candidates_v0 import gate

    stores = pd.DataFrame({"목적": ["식사", "식사", "카페", None], "franchise": [False, True, False, False]})
    assert gate(stores, "식사").tolist() == [True, False, False, False]
    assert gate(stores, "카페").tolist() == [False, False, True, False]


def test_reach_flag_from_rep_walk_uses_5_and_10_minutes():
    from scripts.build_store_candidates_v0 import REP_MAX_MIN, REP_STABLE_MIN, reach_flag

    flags = reach_flag(pd.Series([0, 5, 5.1, 10, 10.1]), REP_STABLE_MIN, REP_MAX_MIN)
    assert flags.tolist() == ["안정", "안정", "경계", "경계", "제외"]
