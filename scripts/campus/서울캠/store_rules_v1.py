"""점포 단계 규칙 v1: 업종 보정 · 점포 단계 목적 · 비목적지 제외 · 희소도 가점 대상.

v0(`build_seoul_store_table_v0.py`)에서 고치는 세 가지를 한곳에 모은다. 설명과 근거는 `docs/store_level_v1_changes.md`.

    1 업종 보정   category: 상호 키워드(name_rule) > 인허가 위생업태(license, 상가정보와 크게 어긋날 때만) > 상가정보 소분류(sbiz)
    2 공부 축소   점포 단계 공부 = 독서실/스터디 카페 (+ 서점·북카페, STUDY_INCLUDE_BOOKS). 학원·문구·스포츠강습은 목적 없음
                 상권 단계(PATH-v0·SERP-v0) PURPOSE_INDUSTRIES는 그대로 둔다
    3 비목적지    소분류 패턴(EXCLUDE_SUBTYPE_PATTERNS) ∨ 상호 키워드(EXCLUDE_NAME_KEYWORDS) ∨ 경계 업종 끔(BOUNDARY_SUBTYPES) → 목적 없음
                 희소도 가점은 목적지형 소분류에만(생활형 ERRAND_SUBTYPE_PATTERNS는 rarity 0)

입력 열(apply_rules): 상호, 소분류명, service(서비스업종, 없으면 NaN), food(음식 업종 여부), source(sbiz / license_only),
                    선택: 위생업태(sbiz 점포에 매칭된 인허가 위생업태)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
for p in (REPO / "scripts", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from build_purpose_features import map_industry_to_purpose  # noqa: E402

VERSION = "v1"

# ── 2. 점포 단계 목적 ─────────────────────────────────────────────
# True면 서점(서적)과 상호에 북카페·책방이 든 카페를 공부로 둔다. False면 서점은 목적 없음, 북카페는 카페
STUDY_INCLUDE_BOOKS = True
BOOKCAFE_KEYWORDS = ["북카페", "북까페", "책방", "BOOKCAFE"]
# 점포 단계에서만 목적을 비우는 서비스업종(v0 NO_PURPOSE_SERVICES = {"스포츠강습"}에 학원·문구를 더한다)
NO_PURPOSE_SERVICES_V1 = {"스포츠강습", "일반교습학원", "외국어학원", "컴퓨터학원", "예술학원", "문구", "비디오/서적임대"}

# ── 1. 업종 보정 ─────────────────────────────────────────────────
# 상호 키워드 → (보정 소분류명, 서비스업종). 위에서부터 처음 맞는 규칙 하나. 음식 업종(food)에만 쓴다(스터디카페 규칙은 전 업종)
# 보정 소분류명은 상가정보 소분류명을 그대로 쓴다(희소도·MMR이 같은 소분류로 묶이도록)
NAME_RULES: list[tuple[str, str, str]] = [
    (r"스터디\s?카페|스터디\s?까페|독서실", "독서실/스터디 카페", "독서실"),
    (r"컵밥|김밥|떡볶이|떡뽁이|분식", "김밥/만두/분식", "분식전문점"),
    (r"족발|보쌈", "족발/보쌈", "한식음식점"),
    (r"곱창|막창|대창", "곱창 전골/구이", "한식음식점"),
    (r"닭갈비|닭발|오리고기|오리구이|닭한마리", "닭/오리고기 구이/찜", "한식음식점"),
    (r"치킨|통닭", "치킨", "치킨전문점"),
    (r"한우|소고기|소갈비|우대갈비", "소고기 구이/찜", "한식음식점"),
    (r"삼겹|오겹|목살|숯불|갈비|고깃집", "돼지고기 구이/찜", "한식음식점"),
    (r"라멘|우동|소바", "일식 면 요리", "일식음식점"),
    (r"초밥|스시|사시미", "일식 회/초밥", "일식음식점"),
    (r"짜장|짬뽕|마라탕|반점|중화요리", "중국집", "중식음식점"),
    (r"호프|포차|포장마차|이자카야|주점|맥주", "생맥주 전문", "호프-간이주점"),
    (r"다방|커피|카페|까페|COFFEE|CAFE", "카페", "커피-음료"),
]
_NAME_RES = [(re.compile(p, re.IGNORECASE), name, svc) for p, name, svc in NAME_RULES]
STUDY_NAME_RULE = NAME_RULES[0][0]

# 인허가 위생업태 우선: 같은 그룹이 아니면 '크게 어긋남'으로 보고 위생업태를 쓴다.
# 식사 안(한식 ↔ 일식 등)은 위생업태가 '한식' 기본값으로 등록된 경우가 많아 상가정보를 둔다. True로 바꾸면 식사 안에서도 위생업태 우선
SERVICE_GROUP = {
    **dict.fromkeys(["한식음식점", "중식음식점", "일식음식점", "양식음식점", "분식전문점", "패스트푸드점", "치킨전문점"], "식사"),
    **dict.fromkeys(["호프-간이주점", "일반주점"], "주점"), "커피-음료": "카페", "제과점": "제과",
}
LICENSE_OVERRIDE_WITHIN_MEAL = False

# ── 3. 비목적지 제외 ─────────────────────────────────────────────
# 소분류명에 이 문자열이 들어가면 제외(출장·수리·설치·열쇠, 의료·재활·치료, 부동산, 세탁, 렌탈, 차량·시공 등)
EXCLUDE_SUBTYPE_PATTERNS = ["철물", "공구", "열쇠", "수리", "설치", "부동산", "중개", "세탁", "빨래", "렌탈", "임대", "대여",
                            "약국", "의원", "병원", "치과", "한의", "재활", "치료", "요양", "장례", "벽지/장판", "자동차", "주유",
                            "인력", "이삿짐", "청소 서비스", "방역", "인쇄"]
# 상호에 이 문자열이 들어가면 제외(대소문자 무시)
EXCLUDE_NAME_KEYWORDS = ["출장", "수리", "설치", "열쇠", "도어락", "대행", "렌탈", "재활", "치료", "클리닉", "REHAB", "통증",
                         "정형외과", "의원", "한의원", "병원", "약국", "부동산", "공인중개", "세탁", "도배", "철거", "용달", "퀵서비스"]
# 경계 업종: 소분류명 → (유지 여부, 근거). False면 제외. 사용자가 바꿀 수 있다
BOUNDARY_SUBTYPES: dict[str, tuple[bool, str]] = {
    "PC방": (False, "게임 목적이면 집 근처 PC방과 다를 게 없어 '거기까지 가 볼' 이유가 약하다"),
    "노래방": (True, "친구와 함께 가는 여가로 상권 나들이의 마무리가 된다. 코인노래방도 대학생 이용이 많다"),
    "여관/모텔": (False, "숙박 업종. 30분 안 당일 나들이 추천에 맞지 않는다"),
    "호텔/리조트": (False, "숙박 업종. 라운지·카페가 따로 있으면 카페 업종으로 잡힌다"),
    "헬스장": (False, "회원제 운동 시설. 한 번 찾아가는 곳이 아니다"),
    "전자 게임장": (True, "오락실은 들러 볼 만한 놀거리다"),
    "기타 오락장": (True, "뽑기방·방탈출 등 체험형 놀거리가 섞여 있다"),
    "당구장": (True, "친구와 함께 가는 여가"),
    "볼링장": (True, "친구와 함께 가는 여가, 상권에 드물다"),
    "골프 연습장": (True, "스크린골프는 모임 여가로 쓰인다. 레슨 전용 아카데미는 상호 키워드로 걸러지지 않으니 남는다"),
    "탁구장": (True, "체험형 운동 여가"),
    "스쿼시/라켓볼장": (True, "체험형 운동 여가"),
    "종합 스포츠시설": (True, "클라이밍 등 체험형이 섞여 있다. 재활·치료는 상호 키워드로 뺀다"),
    "기타 스포츠시설 운영업": (True, "클라이밍·스튜디오 등 체험형이 섞여 있다"),
}
# 생활형(희소도 가점 없음): 장보기·생활용품. 목적은 남기되 '이 상권에 드문' 가점·태그를 주지 않는다
ERRAND_SUBTYPE_PATTERNS = ["슈퍼마켓", "편의점", "정육", "수산물", "반찬/식료품", "채소/과일", "건어물", "미곡", "곡물", "식료품",
                           "핸드폰", "가전", "전기용품", "조명", "실/섬유", "침구", "커튼", "가구", "안경"]


def _contains_any(s: pd.Series, words: list[str]) -> pd.Series:
    pat = "|".join(re.escape(w) for w in words)
    return s.fillna("").astype(str).str.contains(pat, case=False, regex=True)


def name_rule(name: str) -> tuple[str, str] | None:
    """상호에 맞는 첫 보정 규칙의 (소분류명, 서비스업종). 없으면 None."""
    for rx, sub, svc in _NAME_RES:
        if rx.search(str(name or "")):
            return sub, svc
    return None


def _group(svc) -> str | None:
    return SERVICE_GROUP.get(svc) if isinstance(svc, str) else None


def resolve_category(df: pd.DataFrame) -> pd.DataFrame:
    """소분류명·service를 보정하고 category_source(sbiz / license / name_rule), category_fixed, 소분류명_원을 더한다."""
    from build_seoul_store_table_v0 import LICENSE_TO_SERVICE

    out = df.copy()
    out["소분류명_원"] = out["소분류명"]
    out["category_source"] = (out["source"].eq("sbiz")).map({True: "sbiz", False: "license"})
    out["category_fixed"] = False

    # 인허가 위생업태 우선(상가정보 음식 점포에 매칭된 것만)
    if "위생업태" in out:
        lic_svc = out["위생업태"].map(LICENSE_TO_SERVICE)
        g_lic, g_cur = lic_svc.map(_group), out["service"].map(_group)
        diff = g_lic.ne(g_cur) | (LICENSE_OVERRIDE_WITHIN_MEAL & lic_svc.ne(out["service"]))
        over = out["source"].eq("sbiz") & out["food"] & lic_svc.notna() & g_cur.notna() & diff
        out.loc[over, "소분류명"] = out.loc[over, "위생업태"]
        out.loc[over, "service"] = lic_svc[over]
        out.loc[over, "category_source"] = "license"
        out.loc[over, "category_fixed"] = True

    # 상호 키워드 보정: 음식 업종만(스터디카페 규칙은 전 업종). 서비스업종이 이미 같으면 그대로 둔다
    rules = out["상호"].map(name_rule)
    for i, r in rules.items():
        if r is None:
            continue
        sub, svc = r
        if not (out.at[i, "food"] or re.search(STUDY_NAME_RULE, str(out.at[i, "상호"]), re.IGNORECASE)):
            continue
        if out.at[i, "service"] == svc:
            continue
        out.at[i, "소분류명"], out.at[i, "service"] = sub, svc
        out.at[i, "category_source"], out.at[i, "category_fixed"] = "name_rule", True
    return out


def store_purpose(service: pd.Series, names: pd.Series, include_books: bool | None = None) -> pd.Series:
    """점포 단계 목적. 학원·문구·스포츠강습은 None, 서점·북카페는 include_books에 따라."""
    books = STUDY_INCLUDE_BOOKS if include_books is None else include_books
    no_purpose = NO_PURPOSE_SERVICES_V1 | (set() if books else {"서적"})
    p = service.map(lambda s: None if (not isinstance(s, str) or s in no_purpose) else map_industry_to_purpose(s))
    if books:
        p = p.mask(service.eq("커피-음료") & _contains_any(names, BOOKCAFE_KEYWORDS), "공부")
    return p


def exclude_reason(names: pd.Series, subtypes: pd.Series) -> pd.Series:
    """비목적지면 사유(subtype / name / boundary:<소분류명>), 아니면 None."""
    sub = _contains_any(subtypes, EXCLUDE_SUBTYPE_PATTERNS)
    name = _contains_any(names, EXCLUDE_NAME_KEYWORDS)
    off = {k for k, (keep, _) in BOUNDARY_SUBTYPES.items() if not keep}
    bnd = subtypes.isin(off)
    r = pd.Series(None, index=names.index, dtype=object)
    r = r.mask(bnd, "boundary:" + subtypes.astype(str))
    r = r.mask(name, "name")
    return r.mask(sub, "subtype")


def is_destination(subtypes: pd.Series) -> pd.Series:
    """희소도 가점 대상(목적지형). 생활형 소분류는 False."""
    return ~_contains_any(subtypes, ERRAND_SUBTYPE_PATTERNS)


def apply_rules(df: pd.DataFrame, include_books: bool | None = None) -> pd.DataFrame:
    """업종 보정 → 점포 단계 목적 → 비목적지 제외 → 목적지형 여부. 목적_보정전은 제외 규칙 전 목적."""
    out = resolve_category(df)
    out["목적_보정전"] = store_purpose(out["service"], out["상호"], include_books)
    out["exclude_reason"] = exclude_reason(out["상호"], out["소분류명"])
    out["목적"] = out["목적_보정전"].where(out["exclude_reason"].isna(), None)
    out["destination"] = is_destination(out["소분류명"])
    return out
