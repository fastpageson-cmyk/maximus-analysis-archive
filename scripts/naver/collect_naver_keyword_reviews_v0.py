"""네이버 플레이스 키워드 리뷰 '집계 수'만 모은다 v0 (exact·fuzzy 연결 점포).

    요청   = POST pcmap-api.place.naver.com/graphql, getVisitorReviewStats 하나만. 쿠키·캡차 토큰은 보내지 않는다
    받는 것 = place_id, 키워드 코드·문구, 키워드별 선택 인원, 참여 인원(userCount), 방문자 리뷰 수, 수집 시각
    버리는 것 = 별점·별점 분포·테마·메뉴 등 나머지 전부. 저장 전에 집계 필드만 남긴다(리뷰 본문·닉네임·사진은 이 요청에 없음)
    블로그 리뷰 수는 이 응답에 없어 빈칸
    요청 규칙·캐시 = match_naver_places_v0.Polite (2~3초 + 무작위, 403·429·캡차 3번 연속이면 멈춤)
캐시: 데이터/캐시/naver_place/{place_id}.json (집계 필드만)
출력: 데이터/가공/서울캠/naver_keyword_counts_v0.csv (커밋 금지)
실행: ~/.venvs/maximus/bin/python -I scripts/naver/collect_naver_keyword_reviews_v0.py --limit 1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from match_naver_places_v0 import OUT, ROOT, Blocked, Polite  # noqa: E402

CACHE = ROOT / "데이터/캐시/naver_place"
MATCH = OUT / "naver_place_match_v0.csv"
GRAPHQL_URL = "https://pcmap-api.place.naver.com/graphql"
QUERY = """query getVisitorReviewStats($id: String, $itemId: String, $businessType: String = "place") {
  visitorReviewStats(input: {businessId: $id, itemId: $itemId, businessType: $businessType}) {
    id
    analysis { votedKeyword { totalCount reviewCount userCount details { code displayName count } } }
    visitorReviewsTotal
  }
}"""
COLUMNS = ["store_id", "place_id", "keyword_code", "keyword", "count", "n_participants", "n_votes",
           "n_visitor_reviews", "n_blog_reviews", "collected_at"]


def payload(place_id: str) -> list[dict]:
    return [{"operationName": "getVisitorReviewStats", "variables": {"businessType": "restaurant", "id": place_id}, "query": QUERY}]


def parse_stats(data, collected_at: str) -> dict:
    """응답에서 집계 필드만 꺼낸다. 다른 필드는 버린다."""
    stats = (data[0] if isinstance(data, list) else data).get("data", {}).get("visitorReviewStats") or {}
    vk = (stats.get("analysis") or {}).get("votedKeyword") or {}
    return {
        "place_id": str(stats.get("id") or ""),
        "n_participants": vk.get("userCount"),
        "n_votes": vk.get("totalCount"),
        "n_visitor_reviews": stats.get("visitorReviewsTotal"),
        "keywords": [{"code": d.get("code"), "name": d.get("displayName"), "count": d.get("count")} for d in vk.get("details") or []],
        "collected_at": collected_at,
    }


def fetch(client: Polite, place_id: str) -> dict:
    path = CACHE / f"{place_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    referer = f"https://pcmap.place.naver.com/restaurant/{place_id}/review/visitor"
    data = client.call("POST", GRAPHQL_URL, json=payload(place_id),
                       headers={"Content-Type": "application/json", "Origin": "https://pcmap.place.naver.com", "Referer": referer})
    stats = parse_stats(data, datetime.now().isoformat(timespec="seconds"))
    path.write_text(json.dumps(stats, ensure_ascii=False))
    return stats


def to_rows(store_id: str, s: dict) -> list[dict]:
    base = {"store_id": store_id, "place_id": s["place_id"], "n_participants": s["n_participants"], "n_votes": s["n_votes"],
            "n_visitor_reviews": s["n_visitor_reviews"], "n_blog_reviews": None, "collected_at": s["collected_at"]}
    if not s["keywords"]:
        return [{**base, "keyword_code": None, "keyword": None, "count": 0}]
    return [{**base, "keyword_code": k["code"], "keyword": k["name"], "count": k["count"]} for k in s["keywords"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="앞에서부터 N곳만(시험용)")
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    m = pd.read_csv(MATCH, dtype={"store_id": str, "place_id": str})
    m = m[m.match_status.isin(["exact", "fuzzy"])]
    m = m.head(args.limit) if args.limit else m
    client, rows, ok = Polite(), [], 0
    try:
        for s in m.itertuples(index=False):
            stats = fetch(client, s.place_id)
            rows += to_rows(s.store_id, stats)
            ok += 1
    except Blocked as e:
        print("멈춤:", e)
    out = pd.DataFrame(rows, columns=COLUMNS)
    out.to_csv(OUT / "naver_keyword_counts_v0.csv", index=False, encoding="utf-8-sig")
    print(f"수집 {ok}/{len(m)}, 키워드 행 {len(out)}")
    if ok:
        per = out.drop_duplicates("store_id")
        print("참여 인원 중앙값", per.n_participants.median(), "/ 20 미만 비율", round(per.n_participants.fillna(0).lt(20).mean(), 3))


if __name__ == "__main__":
    main()
