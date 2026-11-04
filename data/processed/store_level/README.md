# 점포 단위(store-level) 산출물

설계: `docs/store_level/recommendation_options.md`. 원천 출처: `docs/campus/seoul_store_raw_sources.md`.
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
- 목적 대응표는 사람이 정했다. 표에 없는 소분류(부동산·의료·미용·액세서리 등)는 목적 빈칸이다. PATH-v0 표를 따라 제과점(빵·떡)은 **식사**로 간다. 요가·태권도(스포츠강습)는 PATH-v0에서는 공부지만 점포 단계에서는 목적을 비운다(2026-11-03 팀 결정, `NO_PURPOSE_SERVICES`). 댄스·복합 예술 교육(기타 예술/스포츠 교육기관)은 예술학원으로 보고 공부에 남는다.
- 프랜차이즈 규칙은 흔한 이름도 잡는다(예: '전주식당', 업종이 다른 같은 이름). 독립 가게 일부가 후보에서 빠진다.
- 상호 유사도는 포함 관계도 같다고 본다('스시' ↔ '스시코리아'). 정밀도는 감사 표본으로 잰다.
- 인허가일자는 지위승계 뒤에도 남아 노포가 과대될 수 있다(`docs/campus/limitations.md`).

## 점포 후보와 접근성 판정 v0 (로컬)

`<작업 폴더>/데이터/가공/서울캠/store_candidates_v0.csv`. 실행: `~/.venvs/maximus/bin/python -I scripts/store_level/build_store_candidates_v0.py` (점포 테이블 v0 먼저).

| 열 | 설명 |
|---|---|
| group | candidate(의외성 상권 안 후보) / inertia_ref(관성 상권 기준 점포) |
| purpose, area_code, store_id | 목적·상권·점포. 같은 점포가 여러 목적 관성 상권에 들면 목적마다 한 줄 |
| mmr_rank, in_k10, in_k20 | SERP-v0 목적별 MMR 순위(상위 20까지만 있음). 기본은 K=10, 민감도는 K=20과 eligible 전체(빈 순위 포함) |
| walk_from_rep | 상권 대표점 → 점포 도보(분), 직선 × 1.3 ÷ 시속 4km |
| reach_flag | **판정.** 안정(도보 ≤5분) / 경계(5~10분) / 제외(>10분) |
| mean_period_ratio | 동대문구 출발지 334곳의 30분 도달률(세 시간대 평균, PATH-v0) |
| t_area, t_store_seoulcampus | 참고. 서울캠 → 상권 대표점, 서울캠 → 점포(`t_area − walk(하차점→대표점) + walk(하차점→점포)`) |
| seoulcampus_flag | 참고. 서울캠 기준 안정(≤25) / 경계(25~30) / 제외(>30) |
| reach_source, wait_risk | 참고. 서울캠 시간의 출처(측정·추정·도보), `seoulcampus_areas_reach_v1.csv`의 대기 위험 |
| 나머지 | 점포 테이블 v0 열 |

- **출발점은 동대문구다**(SERP-v0·PATH-v0와 같음, 2026-11-03 팀 결정). 후보 상권은 이미 동대문구 출발지 25% 이상이 30분 안에 닿는 곳이다. 점포는 상권 대표점에서 얼마나 더 걸어야 하는지로 판정한다. 기준 5·10분은 대표점에서 상권 가장자리까지 걸리는 시간(중앙값 약 4분, 이태원 관광특구 약 12분)을 보고 정했다.
- K=10 후보의 판정: 안정 80.3%, 경계 15.5%, 제외 4.3%. 대표점 도보 시간은 중앙값 2.8분, 90분위 6.8분, 최대 16.7분이다. 참고로 서울캠 기준이면 제외가 73.5%였다.
- 서울캠 참고 시간 계산: 측정은 캐시된 ODsay 응답(119곳)의 최단 totalTime. 하차점은 마지막 탑승 구간의 끝 좌표다.
- 추정: 캐시 119곳으로 맞춘 `t = 15.5 + 2.83 × 직선km`(잔차 MAE 3.8분, 캐시 범위 직선 약 1~12km). 하차점은 대표점에서 가장 가까운 버스 정류소(`data/raw/서울시버스노선별정류소정보_20260902.xlsx`)나 지하철역(`seoul_station_master_20260902.csv`)이다. 이 두 파일은 `scripts/build_seoul_transit_network.py`가 쓰는 원천이다.
- 직선 1km 안 상권은 걷는 쪽이 더 빠르면 도보로 본다.
- ODsay는 새로 부르지 않는다.

### 한계
- **점포마다 30분 안인지는 판정하지 않는다.** PATH-v0 도달률은 상권 단위 비율이라 점포까지 내릴 수 없다. 대표점 도보 시간은 "상권 안에서 얼마나 구석인가"만 보여 준다.
- 대표점이 실제 하차 역·정류장과 다를 수 있다. 서울캠 참고 시간 중 추정 상권(K=10 상권 35곳 중 31곳)은 직선거리 회귀라 노선 사정을 모른다.

## 매칭 감사 표본

`match_audit_sample_v0.csv`: 인허가가 매칭된 상가정보 점포 50곳(무작위, seed 42). 좌표는 없다.
열: 상호, 소분류명, 인허가 상호, 인허가 연도, 거리_m, 판정, 판정_claude, 근거_claude. **판정 칸은 사람이 채운다**(맞음 / 틀림 / 애매). `판정_claude`는 Claude가 같은 가게인지 본 1차 판정이다(맞음 47, 애매 3, 틀림 0). 사람 판정이 있으면 검증 스크립트는 그쪽을 먼저 쓴다.

## 네이버 장소 연결·키워드 집계 v0 (로컬)

`scripts/naver/match_naver_places_v0.py` → `collect_naver_keyword_reviews_v0.py` 순서로 돌린다. 대상은 식사·카페·공부 K=10 후보와 관성 기준 점포를 합친 3,252곳이다.

- 장소 연결: `map.naver.com/p/api/search/instant-search`(검색어 = 정규화 상호 + 도로명, coords = 점포 좌표). 80m 안이고 상호가 비슷하면 exact, 80m 안이기만 하면 fuzzy, 없으면 none.
- 키워드 집계: `pcmap-api.place.naver.com/graphql`의 `getVisitorReviewStats`. 키워드 코드·문구·선택 인원, 참여 인원(`userCount`), 방문자 리뷰 수만 저장한다. 별점·메뉴·리뷰 본문은 저장하지 않는다. 블로그 리뷰 수는 이 응답에 없다.
- 요청: 쿠키·캡차 토큰을 보내지 않는다. 단일 스레드로 2~3초 + 무작위 지연을 두고, 403·429·캡차 응답이 3번 연속이면 멈춘다. 캐시(`데이터/캐시/naver_search`, `naver_place`)가 있는 곳은 건너뛴다.
- 결과 CSV, 캐시, place_id는 커밋하지 않는다. 공개 파일은 `naver_match_audit_sample_v0.csv`(place_id·좌표 없음)뿐이다.

## 점포 의외성 점수 v0

실행: `~/.venvs/maximus/bin/python -I scripts/store_level/build_store_serendipity_v0.py` (후보 v0 먼저).

- 로컬: `데이터/가공/서울캠/store_serendipity_v0.csv`(후보 전체, 점수 열 포함)
- 공개: `store_serendipity_top30_v0.csv`(purpose, rank, 상호, 소분류명, area_name, 테마태그, 공공태그, reach_flag, review_evidence, reason), `store_serendipity_sensitivity_v0.csv`(기본판 대비 목적별 상위 30 자카드)
- 점수: `r_store = 0.4·pct(영업연수|소분류) + 0.2·착한가격 + 0.4·fit`, `u_store = 0.3·희소도 + 0.2·노포/10년+ + 0.3·u_content + 0.2·u_local`, `s_store = r × u`. 상권 안 MMR(λ=0.7, 같은 소분류 1곳)로 3곳을 고르고, `S = serendipity_score × s_store`로 목적별 30곳까지 둔다. 프랜차이즈와 `reach_flag=제외`는 MMR 전에 뺀다.

### v0 한계
- **리뷰 특성이 없다.** 네이버 키워드 집계 요청(`getVisitorReviewStats`)은 캡차 토큰 없이 보내면 첫 요청부터 429가 온다(2026-11-03). 그래서 모든 점포가 `review_evidence=low`이고, `fit·u_content·u_local`은 0.5다. 테마 사전(P5)도 만들지 못했다. 점수는 영업연수·착한가격·희소도·노포/10년+로만 정해진다.
- 오래가게 지정 원천이 아직 없다. 인허가가 없는 점포(쇼핑·공부·여가)는 영업연수 백분위를 0.5로 둔다.
- 목적별 추천 수는 식사 30, 카페 21, 공부 25, 쇼핑 30, 여가문화 24다. 카페·공부·여가는 상권 안 같은 목적 점포가 적어서 3곳을 못 채우는 상권이 있다.
- 상권 10곳 × 3곳 = 최대 30곳이라 상위 집합이 거의 정해져 있다. 그래서 가중치를 ±0.1 바꿔도 자카드는 0.82~1.0이다. K=20일 때는 0.41~0.67이다.

## v1 (규칙 보정판)

변경 내용·근거·사전 영향: `docs/store_level/v1_changes.md`. 로컬 실행 프롬프트: `docs/prompts/store_level_v1_local_run.md`.
규칙은 모두 `scripts/campus/서울캠/store_rules_v1.py` 상수다(업종 보정 `NAME_RULES`·`SERVICE_GROUP`, 공부 `NO_PURPOSE_SERVICES_V1`·`STUDY_INCLUDE_BOOKS`, 제외 `EXCLUDE_SUBTYPE_PATTERNS`·`EXCLUDE_NAME_KEYWORDS`·`BOUNDARY_SUBTYPES`, 생활형 `ERRAND_SUBTYPE_PATTERNS`).

실행 순서(저장소 루트, 로컬):

```bash
~/.venvs/maximus/bin/python -I scripts/campus/서울캠/build_seoul_store_table_v1.py
~/.venvs/maximus/bin/python -I scripts/store_level/build_store_candidates_v1.py
~/.venvs/maximus/bin/python -I scripts/store_level/build_store_serendipity_v1.py
~/.venvs/maximus/bin/python -I scripts/store_level/validate_store_serendipity_v1.py
~/.venvs/maximus/bin/python -I scripts/store_level/compare_store_serendipity_v0_v1.py
```

### 점포 테이블 v1에서 바뀌거나 늘어난 열 (`seoul_store_table_v1.csv`, 로컬·커밋 금지)

| 열 | 설명 |
|---|---|
| 소분류명 | **보정된** 소분류명. 상호 키워드 규칙이면 상가정보 소분류명(예: 족발/보쌈), 위생업태 우선이면 위생업태명 |
| 소분류명_원 | 보정 전 값(상가정보 소분류명, license_only는 위생업태) |
| category_fixed | 업종이 바뀌었는지 |
| category_source | sbiz(상가정보 그대로) / license(license_only, 또는 위생업태 우선으로 바뀜) / name_rule(상호 키워드) |
| 목적 | **점포 단계 목적.** 공부 = 독서실/스터디 카페 + 서점·북카페(`STUDY_INCLUDE_BOOKS`). 학원·문구·스포츠강습은 빈칸. 비목적지는 빈칸 |
| 목적_보정전 | 비목적지 제외를 적용하기 전 목적(업종 보정·공부 규칙은 적용됨) |
| exclude_reason | subtype(소분류 패턴) / name(상호 키워드) / boundary:<소분류명>(경계 업종 끔) / 빈칸 |
| destination | 목적지형 소분류인지. False(생활형: 식료품·정육·침구·가구·가전·조명·안경 등)면 희소도 가점 없음 |
| rarity | `rarity_raw`, 단 destination=False면 0 |
| rarity_raw | 1 − 상권 안 백분위(같은 상권 같은 **보정 소분류명** 점포 수). v0는 소분류코드로 묶었다 |
| 위생업태 | 매칭된 인허가 위생업태(v0에서는 내부 열이었다) |

나머지 열은 v0와 같다.

### 공개 산출물 v1

- `store_serendipity_top30_v1.csv`: v0 열 + `category_source`
- `store_serendipity_sensitivity_v1.csv`, `survey_cards_v1.csv`, `survey_cards_key_v1.csv`, `validation_summary_v1.json`: v0와 같은 형식
- `store_serendipity_v0_v1_compare.md`: 목적별 추천 수, 빠진·새 가게, 카드 덱의 공공 태그 없는 비율 비교
- `store_rules_v1_preimpact_top30.csv`, `store_rules_v1_preimpact_cards.csv`: **v1 결과가 아니다.** 공개 v0 목록에 v1 규칙을 덧씌운 가게별 판정(사전 추정, `scripts/store_level/estimate_store_rules_v1_impact.py`)

### v1 한계
- 키워드·제외 목록은 사람이 정했다. `category_fixed=True`와 `exclude_reason` 표본을 로컬에서 검수해야 한다.
- 위생업태 우선은 식사 / 주점 / 카페 / 제과 그룹이 다를 때만 쓴다(`LICENSE_OVERRIDE_WITHIN_MEAL=False`).
- 숙박·헬스장 제외는 이번에 더한 판단이다(PC방 제외·노래방 유지는 팀 기본값). `BOUNDARY_SUBTYPES`로 바꾼다.
- 공부하기 좋은 일반 카페는 리뷰 키워드가 생긴 뒤에 넣는다.
