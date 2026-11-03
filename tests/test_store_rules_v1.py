import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/campus/서울캠"))
import store_rules_v1 as rules  # noqa: E402


def row(상호, 소분류명, service, food=False, source="sbiz", 위생업태=None):
    return dict(상호=상호, 소분류명=소분류명, service=service, food=food, source=source, 위생업태=위생업태)


def run(*rows, **kw):
    return rules.apply_rules(pd.DataFrame(list(rows)), **kw)


def one(*args, **kw):
    return run(row(*args, **kw)).iloc[0]


def test_locksmith_call_out_is_excluded():
    r = one("중랑구24시출장열쇠집도어락비번분실문수리면목동게이트맨", "철물/공구 소매업", "철물점")
    assert pd.isna(r.목적) and r.exclude_reason == "subtype"
    # 소분류가 멀쩡해도 상호 키워드로 빠진다
    r = one("24시출장열쇠", "기타 의류 소매업", "일반의류")
    assert pd.isna(r.목적) and r.exclude_reason == "name"


def test_rehab_is_excluded_from_leisure():
    r = one("INTERNATIONALSPORTSREHAB", "종합 스포츠시설", "스포츠클럽")
    assert r.목적_보정전 == "여가문화" and pd.isna(r.목적) and r.exclude_reason == "name"


def test_boundary_pc_bang_out_karaoke_in():
    pc, karaoke = run(row("i7PC방", "PC방", "PC방"), row("1%코인노래연습장", "노래방", "노래방")).itertuples()
    assert pd.isna(pc.목적) and pc.exclude_reason == "boundary:PC방"
    assert karaoke.목적 == "여가문화" and pd.isna(karaoke.exclude_reason)


def test_boundary_is_a_switch(monkeypatch):
    monkeypatch.setitem(rules.BOUNDARY_SUBTYPES, "PC방", (True, "test"))
    assert one("i7PC방", "PC방", "PC방").목적 == "여가문화"


def test_mybossam_becomes_korean():
    r = one("마이보쌈", "일식", "일식음식점", food=True, source="license_only", 위생업태="일식")
    assert (r.소분류명, r.service, r.category_source, r.category_fixed) == ("족발/보쌈", "한식음식점", "name_rule", True)
    assert r.소분류명_원 == "일식" and r.목적 == "식사"


def test_samgyeopsal_from_hof_becomes_korean():
    r = one("상계솥뚜껑삼겹살", "호프/통닭", "호프-간이주점", food=True, source="license_only", 위생업태="호프/통닭")
    assert r.service == "한식음식점" and r.category_source == "name_rule"


def test_kings_cupbap_moves_from_cafe_to_meal():
    r = one("킹스컵밥 숙대본점", "커피숍", "커피-음료", food=True, source="license_only", 위생업태="커피숍")
    assert (r.소분류명, r.service, r.목적_보정전, r.목적) == ("김밥/만두/분식", "분식전문점", "식사", "식사")


def test_name_rule_keeps_correct_category():
    r = one("정다방", "카페", "커피-음료", food=True)
    assert not r.category_fixed and r.category_source == "sbiz" and r.목적 == "카페"
    # 음식 업종이 아니면 상호 키워드 보정을 하지 않는다(쇼핑 '고기랑꽃게랑')
    r = one("고기랑꽃게랑", "반찬/식료품 소매업", "반찬가게")
    assert not r.category_fixed and r.목적 == "쇼핑"


def test_license_wins_when_group_differs():
    # 상가정보 카페인데 위생업태가 호프 → 주점(식사)
    r = one("밀물", "카페", "커피-음료", food=True, 위생업태="호프/통닭")
    assert (r.소분류명, r.category_source, r.목적) == ("호프/통닭", "license", "식사")
    # 식사 안(일식 ↔ 한식)은 상가정보를 둔다
    r = one("즉석", "일식 면 요리", "일식음식점", food=True, 위생업태="한식")
    assert r.category_source == "sbiz" and not r.category_fixed


def test_academies_and_stationery_are_not_study():
    for name, sub, svc in [("스텝영어학원", "입시·교과학원", "일반교습학원"), ("아토아뜰리에", "미술학원", "예술학원"),
                           ("츄댄스학원", "기타 예술/스포츠 교육기관", "예술학원"), ("제이유", "외국어학원", "외국어학원"),
                           ("디씨문구", "문구/회화용품 소매업", "문구"), ("태권도", "태권도/무술", "스포츠강습")]:
        assert pd.isna(one(name, sub, svc).목적), name


def test_study_cafe_is_study():
    assert one("비전스터디카페", "독서실/스터디 카페", "독서실").목적 == "공부"
    # 휴게음식점으로 등록된 스터디카페도 공부로
    r = one("어반스터디카페", "커피숍", "커피-음료", food=True, source="license_only", 위생업태="커피숍")
    assert r.목적 == "공부" and r.category_source == "name_rule"


@pytest.mark.parametrize("books, expect", [(True, "공부"), (False, None)])
def test_books_toggle(books, expect):
    assert run(row("서점로티", "서점", "서적"), include_books=books).iloc[0].목적 == expect
    bookcafe = run(row("마을북카페", "카페", "커피-음료", food=True), include_books=books).iloc[0]
    assert bookcafe.목적 == ("공부" if books else "카페")


def test_errand_subtypes_get_no_rarity_bonus():
    d = run(row("은혜정육점", "정육점", "육류판매"), row("참아름이불", "침구류/커튼 소매업", "섬유제품"),
            row("데님리", "남성 의류 소매업", "일반의류"), row("즉석우동", "일식 면 요리", "일식음식점", food=True))
    assert d.destination.tolist() == [False, False, True, True]
    assert d.목적.tolist() == ["쇼핑", "쇼핑", "쇼핑", "식사"]


def test_pharmacy_and_flooring_excluded():
    for name, sub, svc in [("참약사플러스약국", "약국", "의약품"), ("도배플러스", "벽지/장판/마루 소매업", "인테리어")]:
        assert pd.isna(one(name, sub, svc).목적), name
