import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/naver"))


def test_find_places_digs_nested_place_dicts():
    from match_naver_places_v0 import find_places

    data = {"place": [{"place": {"id": "1", "title": "가게", "x": "127.0", "y": "37.5", "extra": 1}, "address": None}]}
    assert find_places(data) == [{"id": "1", "title": "가게", "x": "127.0", "y": "37.5", "roadAddress": None, "ctg": None}]


def test_judge_prefers_exact_then_nearest_and_drops_far():
    from match_naver_places_v0 import judge

    places = [
        {"id": "far", "title": "빔블커피", "x": "127.0100", "y": "37.5"},     # 약 880m
        {"id": "near", "title": "다른가게", "x": "127.0001", "y": "37.5"},    # 약 9m, 이름 다름
        {"id": "same", "title": "빔블커피", "x": "127.0005", "y": "37.5"},    # 약 44m, 이름 같음
    ]
    r = judge("빔블커피", 37.5, 127.0, places)
    assert (r["place_id"], r["match_status"]) == ("same", "exact")
    r = judge("없는가게", 37.5, 127.0, places)
    assert (r["place_id"], r["match_status"]) == ("near", "fuzzy")
    assert judge("빔블커피", 37.6, 127.0, places)["match_status"] == "none"


def test_parse_stats_keeps_only_aggregates():
    from collect_naver_keyword_reviews_v0 import parse_stats, to_rows

    data = [{"data": {"visitorReviewStats": {
        "id": "123", "visitorReviewsTotal": 39,
        "review": {"avgRating": 4.9},
        "analysis": {"menus": [{"label": "x"}], "votedKeyword": {"totalCount": 151, "userCount": 38, "details": [
            {"code": "drink_good", "displayName": "음료가 맛있어요", "count": 23, "iconUrl": "u"}]}},
    }}}]
    s = parse_stats(data, "2026-11-03T00:00:00")
    assert s == {"place_id": "123", "n_participants": 38, "n_votes": 151, "n_visitor_reviews": 39,
                 "keywords": [{"code": "drink_good", "name": "음료가 맛있어요", "count": 23}], "collected_at": "2026-11-03T00:00:00"}
    rows = to_rows("S1", s)
    assert rows[0]["count"] == 23 and rows[0]["n_blog_reviews"] is None


def test_parse_stats_empty_response_gives_zero_row():
    from collect_naver_keyword_reviews_v0 import parse_stats, to_rows

    s = parse_stats([{"data": {"visitorReviewStats": None}}], "t")
    assert s["keywords"] == [] and to_rows("S1", s)[0]["count"] == 0
