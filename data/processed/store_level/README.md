# 점포 단위(store-level) 산출물

설계: `docs/store_level_recommendation_options.md`. 원천 출처: `docs/campus/seoul_store_raw_sources.md`.
점포 테이블 자체는 원천(상가정보·인허가)을 그대로 담고 있어 **커밋하지 않는다.** 이 폴더에는 공개해도 되는 감사 표본과 설명만 둔다.

## 서울 점포 테이블 v0 (로컬)

`<작업 폴더>/데이터/가공/서울캠/seoul_store_table_v0.csv`. 서울 공식 상권 786곳 안 점포, 한 줄이 가게 한 곳이다.

실행(저장소 루트에서):

```bash
~/.venvs/maximus/bin/python -I scripts/campus/서울캠/geocode_goodprice_public_v0.py   # 착한가격 공공 좌표(한 번)
~/.venvs/maximus/bin/python -I scripts/campus/서울캠/build_seoul_store_table_v0.py
```

| 열 | 설명 |
|---|---|
| store_id | 상가업소번호. license_only는 `L` + 인허가 관리번호 |
| 상호, 지점명 | 상가정보 상호명·지점명. license_only는 인허가 사업장명, 지점명 빈칸 |
| 소분류코드, 소분류명 | 상가정보 상권업종 소분류. license_only는 코드 빈칸, 이름에 인허가 위생업태 |
| 목적 | 식사·카페·공부·쇼핑·여가문화 또는 빈칸. `scripts/build_purpose_features.py`의 `PURPOSE_INDUSTRIES`(서울시 상권분석 서비스업종 → 목적)를 쓴다. 소분류·위생업태를 서비스업종으로 옮기는 대응표는 스크립트의 `SBIZ_TO_SERVICE`, `LICENSE_TO_SERVICE` |
| area_code, area_name | 상권(within). 폴리곤이 겹치면(49쌍) 면적이 작은 상권 하나 |
| lat, lon | WGS84. 상가정보 좌표, license_only는 인허가 좌표(EPSG:5174 변환) |
| 층 | 상가정보 층정보 |
| license_year | 매칭된 인허가 연도(80m 안 similar(norm(상호)), 여러 개면 가장 오래된 것). 음식 대분류만 매칭 |
| license_service | general_restaurants / rest_cafes / bakeries |
| nopo | license_year ≤ 2005 |
| tenure10 | 2006 ≤ license_year ≤ 2015 |
| old_cafe | 휴게음식점(커피숍·다방·과자점·전통찻집·떡카페)·제과점 인허가 중 ≤ 2015 |
| goodprice | 착한가격업소(공공 좌표) 80m 안 similar 상호. 음식 외 업종 포함 |
| rarity | 1 − 상권 안 백분위(같은 상권 같은 소분류 점포 수). 1에 가까울수록 그 상권에서 드문 업종 |
| franchise | 지점명 있음, 서울 상가정보에서 5번 이상 나오는 상호 접두어(`is_franchise`, KNOWN_CHAINS 포함), 상호 첫 단어 5번 이상 중 하나 |
| source | sbiz / license_only |

### 한계
- 목적 대응표는 사람이 정했다. 표에 없는 소분류(부동산·의료·미용·액세서리 등)는 목적 빈칸이다. PATH-v0 표를 따라 제과점(빵·떡)은 **식사**, 요가·태권도(스포츠강습)는 **공부**로 간다.
- 프랜차이즈 규칙은 흔한 이름도 잡는다(예: '전주식당', 업종이 다른 같은 이름). 독립 가게 일부가 후보에서 빠진다.
- 상호 유사도는 포함 관계도 같다고 본다('스시' ↔ '스시코리아'). 정밀도는 감사 표본으로 잰다.
- 인허가일자는 지위승계 뒤에도 남아 노포가 과대될 수 있다(`docs/campus/limitations.md`).

## 매칭 감사 표본

`match_audit_sample_v0.csv`: 인허가가 매칭된 상가정보 점포 50곳(무작위, seed 42). 좌표는 없다.
열: 상호, 소분류명, 인허가 상호, 인허가 연도, 거리_m, 판정. **판정 칸은 사람이 채운다**(맞음 / 틀림 / 애매).
