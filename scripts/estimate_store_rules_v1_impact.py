"""store_rules_v1을 공개 v0 목록에 적용한 사전 영향 추정. **v1 결과가 아니다.**

    입력 = data/processed/store_level/store_serendipity_top30_v0.csv(130곳), survey_cards_v0.csv + survey_cards_key_v0.csv
    한계 = 공개 CSV에는 소분류코드·매칭 위생업태가 없다. 소분류명 → 서비스업종은 아래 NAME_TO_SERVICE로 옮기고,
           인허가 위생업태 우선 규칙은 적용하지 못한다(license_only 점포는 소분류명이 곧 위생업태라 상호 규칙만 본다).
           빠진 자리를 v1에서 어떤 가게가 채우는지, 희소도 재계산으로 순위가 어떻게 바뀌는지는 알 수 없다
출력: data/processed/store_level/store_rules_v1_preimpact_top30.csv, store_rules_v1_preimpact_cards.csv (가게별 판정)
실행: MAXIMUS_WORKSPACE=<'데이터' 하위 폴더가 있는 폴더> python -I scripts/estimate_store_rules_v1_impact.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/campus/서울캠"))
import store_rules_v1 as rules  # noqa: E402
from build_seoul_store_table_v0 import LICENSE_TO_SERVICE  # noqa: E402

PUBLIC = REPO / "data/processed/store_level"
PURPOSES = ["식사", "카페", "공부", "쇼핑", "여가문화"]
TAG_WORDS = ["노포", "10년", "착한가격", "이 상권에 드문"]

# 공개 v0 목록에 나오는 상가정보 소분류명 → 서비스업종(SBIZ_TO_SERVICE를 이름으로 옮긴 것)
NAME_TO_SERVICE = {
    **dict.fromkeys(["곱창 전골/구이", "국/탕/찌개류", "국수/칼국수", "기타 한식 음식점", "냉면/밀면", "닭/오리고기 구이/찜",
                     "돼지고기 구이/찜", "소고기 구이/찜", "백반/한정식", "전/부침개", "족발/보쌈", "해산물 구이/찜", "횟집"], "한식음식점"),
    "중국집": "중식음식점", "일식 면 요리": "일식음식점", "일식 회/초밥": "일식음식점",
    "기타 서양식 음식점": "양식음식점", "베트남식 전문": "양식음식점", "피자": "패스트푸드점",
    **dict.fromkeys(["토스트/샌드위치/샐러드", "그 외 기타 간이 음식점", "김밥/만두/분식"], "분식전문점"),
    "요리 주점": "일반주점", "생맥주 전문": "호프-간이주점", "카페": "커피-음료",
    "가구 소매업": "가구", "가방 소매업": "가방", "건어물/젓갈 소매업": "수산물판매", "수산물 소매업": "수산물판매",
    **dict.fromkeys(["기타 의류 소매업", "남성 의류 소매업", "여성 의류 소매업"], "일반의류"), "유아용 의류 소매업": "유아의류",
    "꽃집": "화초", "반찬/식료품 소매업": "반찬가게", "벽지/장판/마루 소매업": "인테리어", "슈퍼마켓": "슈퍼마켓",
    "시계/귀금속 소매업": "시계및귀금속", "신발 소매업": "신발", "실/섬유제품 소매업": "섬유제품", "침구류/커튼 소매업": "섬유제품",
    "악기 소매업": "악기", "안경렌즈 소매업": "안경", "약국": "의약품", "예술품 소매업": "예술품",
    "운동용품 소매업": "운동/경기용품", "자전거 소매업": "운동/경기용품", "장난감 소매업": "완구", "전기용품/조명장치 소매업": "조명용품",
    "정육점": "육류판매", "채소/과일 소매업": "청과상", "철물/공구 소매업": "철물점", "한복 소매업": "한복점", "핸드폰 소매업": "핸드폰",
    "화장품 소매업": "화장품",
    "기타 예술/스포츠 교육기관": "예술학원", "미술학원": "예술학원", "음악학원": "예술학원", "독서실/스터디 카페": "독서실",
    "문구/회화용품 소매업": "문구", "서점": "서적", "외국어학원": "외국어학원", "입시·교과학원": "일반교습학원",
    "PC방": "PC방", "골프 연습장": "골프연습장", "기타 오락장": "기타오락장", "노래방": "노래방", "당구장": "당구장",
    "볼링장": "볼링장", "전자 게임장": "전자게임장", "여관/모텔": "여관", "호텔/리조트": "호텔",
    **dict.fromkeys(["기타 스포츠시설 운영업", "종합 스포츠시설", "스쿼시/라켓볼장", "탁구장", "헬스장"], "스포츠클럽"),
}
FOOD = {k for k, v in NAME_TO_SERVICE.items() if v in rules.SERVICE_GROUP} | set(LICENSE_TO_SERVICE)


def to_rule_input(d: pd.DataFrame) -> pd.DataFrame:
    lic = d.소분류명.isin(LICENSE_TO_SERVICE) & ~d.소분류명.isin(NAME_TO_SERVICE)
    unknown = sorted(set(d.소분류명[~lic & ~d.소분류명.isin(NAME_TO_SERVICE)]))
    if unknown:
        raise KeyError(f"NAME_TO_SERVICE에 없는 소분류명: {unknown}")
    return d.assign(service=d.소분류명.map(NAME_TO_SERVICE).fillna(d.소분류명.map(LICENSE_TO_SERVICE)),
                    food=d.소분류명.isin(FOOD), source=lic.map({True: "license_only", False: "sbiz"}))


def judge(d: pd.DataFrame, purpose_col: str) -> pd.DataFrame:
    """가게마다 v1 규칙 판정: 제외(비목적지) / 공부 제외 / 목적 변경 / 업종 보정 / 희소 가점 상실 / 유지."""
    r = rules.apply_rules(to_rule_input(d))
    rare = r.reason.fillna("").str.contains("이 상권에 드문")
    out = pd.Series("유지", index=r.index)
    out[rare & ~r.destination] = "희소 가점 상실(생활형)"
    out[r.category_fixed & r.목적.eq(r[purpose_col])] = "업종 보정(목적 같음)"
    moved = r.목적.notna() & r.목적.ne(r[purpose_col])
    out[moved] = "목적 변경 → " + r.목적[moved].astype(str)
    out[r.목적_보정전.isna() & r[purpose_col].eq("공부")] = "공부 제외(학원·문구)"
    out[r.exclude_reason.notna()] = "제외: " + r.exclude_reason[r.exclude_reason.notna()].astype(str)
    r["판정"] = out
    r["빠짐"] = r.목적.ne(r[purpose_col])  # 이 목적 목록에서 빠지는가
    return r


def tag_after(r: pd.DataFrame) -> pd.Series:
    """희소 가점을 잃은 카드는 '이 상권에 드문'을 뺀 나머지 태그로 다시 본다."""
    has = {w: r.reason.fillna("").str.contains(w) for w in TAG_WORDS}
    keep_rare = has["이 상권에 드문"] & r.destination
    return has["노포"] | has["10년"] | has["착한가격"] | keep_rare


def main() -> None:
    top = pd.read_csv(PUBLIC / "store_serendipity_top30_v0.csv")
    t = judge(top, "purpose")
    cols = ["purpose", "rank", "상호", "소분류명_원", "소분류명", "category_source", "목적", "판정"]
    t[cols].rename(columns={"목적": "목적_v1규칙"}).to_csv(PUBLIC / "store_rules_v1_preimpact_top30.csv", index=False, encoding="utf-8-sig")
    s = t.groupby("purpose").agg(v0=("상호", "size"), 빠짐=("빠짐", "sum"),
                                 업종보정=("category_fixed", "sum"), 희소가점상실=("판정", lambda x: x.str.startswith("희소").sum()))
    s["남음"] = s.v0 - s.빠짐
    print("[top30 v0 → v1 규칙 적용 추정]\n", s.reindex(PURPOSES).to_string())
    print(t[t.판정.ne("유지")][cols].to_string(index=False))

    cards = pd.read_csv(PUBLIC / "survey_cards_v0.csv").merge(pd.read_csv(PUBLIC / "survey_cards_key_v0.csv"), on="card_id")
    deck = cards.drop_duplicates("card_id").reset_index(drop=True)
    c = judge(deck, "purpose")
    c["has_tag_v0"] = c.reason.fillna("").str.contains("|".join(TAG_WORDS))
    c["has_tag_v1est"] = tag_after(c)
    c[["card_id", "method", "purpose", "상호", "소분류명_원", "소분류명", "목적", "판정", "has_tag_v0", "has_tag_v1est"]].rename(
        columns={"목적": "목적_v1규칙"}).to_csv(PUBLIC / "store_rules_v1_preimpact_cards.csv", index=False, encoding="utf-8-sig")
    kept = c[~c.빠짐]
    m = pd.DataFrame({"덱(v0)": c.groupby("method").size(), "빠짐": c.groupby("method").빠짐.sum(),
                      "공공태그 없음 v0": (~c.has_tag_v0).groupby(c.method).mean().round(3),
                      "공공태그 없음 v1추정(남은 카드)": (~kept.has_tag_v1est).groupby(kept.method).mean().round(3)})
    print("\n[설문 카드 덱 v0 → v1 규칙 적용 추정]\n", m.to_string())
    print("세트 기준(카드 600장) 빠지는 카드:", int(cards.card_id.isin(c.card_id[c.빠짐]).sum()))


if __name__ == "__main__":
    main()
