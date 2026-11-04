# 세렌디피티 선행연구 원문 확인 노트 (1차: 서지 특정 + 초록·2차 출처 수준)

작성: 2026-11-02 / 브랜치 `gunwoo/serendipity`
대상 문서: `docs/serendipity/recommendation_design.md` 2·3장, `scripts/build_serendipity_ranking.py`

> **이 노트의 확인 범위를 먼저 밝힌다.** 이번 세션의 클라우드 환경은 네트워크 허용 목록이 좁아서 논문 원문 호스트에 접속하지 못했다. 직접 시도했다가 막힌 호스트는 `arxiv.org`, `pmc.ncbi.nlm.nih.gov`, `jyx.jyu.fi`(Kotkov 학위논문·저자 공개본), `jcst.ict.ac.cn`(JCST 전문 PDF), `ebooks.iospress.nl`(DISCOVERY), `will-qianzhao.github.io`(Kotkov 2018 저자 공개본)이다. 그래서 **13편 모두 전문을 읽지 못했다.** 웹 검색 결과에 나온 초록, 출판사 서지, 저자 저장소 README, 인용 논문의 요약만 확인했다. 각 연구의 `확인 범위` 칸에 이 수준을 적었다.
>
> - "원문 확인"이라고 쓴 곳은 없다. 수식은 원문에서 옮긴 것이 아니다. 기억에 의존한 내용은 **[사전 지식·미확인]**으로 따로 표시했다.
> - 판정(맞음/부분적으로 틀림/틀림)은 초록 수준 근거로 낸 잠정 판정이다. 전문 확인 뒤 바뀔 수 있다.
> - 전문을 읽으려면 환경의 Network access에 위 호스트와 `dl.acm.org`, `link.springer.com`, `www.nature.com`, `journals.open.tudelft.nl`, `research.utwente.nl`, `openproceedings.org`, `www.frontiersin.org`, `hal-lirmm.ccsd.cnrs.fr`, `researchswinger.org`, `iris.unito.it`를 추가해야 한다(13장 참조). 그다음 이 노트의 2차를 쓴다.

---

## 0-1. 로직에 바로 반영할 것 Top 5

1. **관성 기준선 대비 정의를 Ge·Murakami의 'primitive model' 방식으로 명시한다.** Kotkov 2016 서베이가 정리한 고전 지표(Murakami 2008, Ge et al. 2010)는 "단순 기준 추천(primitive model)이 내지 않는 항목 중 관련 있는 것의 비율"로 세렌디피티를 잰다 **[사전 지식·미확인, 2016 서베이 전문으로 수식 확인 필요]**. 우리의 "관성 Top-K 합집합 밖 + R 하한 통과" 구조와 같은 틀이다. 지금 문서는 근거를 '곱 형태'로 대고 있는데, 실제로 가져올 근거는 이쪽이다. 평가 지표로 `SRDP@K = |{i ∈ TopK : i ∉ 관성 TopK, R_i ≥ 0.6}| / K`를 추가하면 집계 데이터에서도 바로 계산된다.
2. **'곱 형태가 맞다'는 주장을 근거에서 빼고, 세 요소의 결합 방식을 '모두 충족(AND)'으로 다시 쓴다.** Kotkov 2018은 세렌디피티를 관련성·새로움·의외성 성분의 **조합(8가지 변형)**으로 정의하고 사용자 응답으로 분류한다(초록·인용 확인). 곱 점수 S = R×U는 우리 설계 선택이지 원문 결론이 아니다. 구현은 그대로 둬도 되지만, 설문 라벨 규칙(세 문항 모두 4점 이상 = 1)은 원문의 AND 정의와 맞으므로 이것을 '정의', S는 '순위용 근사'로 구분한다.
3. **의외성의 한 변형은 만족도를 떨어뜨린다 — U의 `u_cat`·`u_spatial` 가중치를 다시 본다.** Kotkov 2018의 핵심 결과는 "대부분의 세렌디피티 종류와 모든 성분 변형이 선호를 넓히지만, **의외성의 한 변형은 만족도를 해친다**"이다(초록 확인). 학위논문 인용 단편상 unexpectedness(find)가 unexpectedness(implicit)보다 만족도가 높다(검색 단편 확인). implicit은 "평소 소비한 것과 다르다"에 가까운 정의인데 **[변형 정의는 사전 지식·미확인]**, 이는 우리 `u_cat`(관성과의 범주 거리)·`u_spatial`(관성과의 공간 거리)와 같은 성격이다. 이 둘이 U의 50%를 차지한다. 설문(4.2)에 '예상 밖이다'뿐 아니라 '평소 가던 곳과 다르다'를 분리 문항으로 넣어, 어느 변형이 만족을 떨어뜨리는지 우리 자료로 확인해야 한다.
4. **arXiv 2507.03503은 '잔차 보정'이 아니라 '보정(calibrated popularity, CP) 재정렬'이다 — 인기도 분포 맞추기 지표를 추가한다.** 원 논문은 인기 구간(head/mid/tail) 분포를 기준 분포에 맞추는 CP 재정렬과 맥락 인지 모형을 비교하고, 인기 편향을 ARP(평균 추천 인기도)·PopLift로 잰다(초록·요약 확인). 우리 결과표에 **ARP와 head/mid/tail 비율**을 추가하고, 기준 분포를 '동대문구발 유입의 인기 구간 분포'로 두면 집계 OD로 그대로 계산된다. `u_resid`의 근거로는 이 논문을 쓰지 않는다.
5. **반사실 시뮬레이션은 Mauro et al.처럼 '추천 수용률 p' 축을 둔 되먹임 루프로 바꾼다.** 원 논문은 사용자가 매 단계 추천을 따를지(확률) 기존 이동 모형대로 움직일지 정하고, 그 이동이 다시 추천기에 들어가는 루프를 돌린다(초록 확인). 우리 5.5는 1회성 산술 이동(5·10·20%)이다. 같은 축(수용률)을 쓰되 2~3회 반복해 유입이 바뀐 뒤 순위를 다시 계산하면 집계 데이터에서도 '루프' 근사가 된다. 결과 해석에서 "개인 다양성↑, 집단 쏠림↑가 갈라진다"를 검증 가설로 둔다.

## 0-2. 현재 문서에서 틀린(또는 근거 없는) 서술 목록

| # | 위치 | 현재 서술 | 판정 | 고칠 방향 |
|---|---|---|---|---|
| 1 | 2장 표 1행, 3장 1행 | "Kotkov 2016, 2018: 세렌디피티 = 관련성 × 새로움 × 의외성, 곱 형태 지표" / "곱 형태가 맞다" | **부분적으로 틀림** | 원문은 세 성분의 **조합(AND)과 8가지 변형**을 정의한다. 곱 형태를 원문이 지지한다는 근거는 확인되지 않았다. "Kotkov는 세렌디피티를 관련성·새로움·의외성 성분의 조합으로 정의한다. 우리는 순위를 내려고 R×U 곱으로 근사했다"로 바꾼다 |
| 2 | 1.3 표 `u_novelty`, `u_cat` | "Kotkov의 novelty(비인기)", "Kotkov의 unexpectedness" | **부분적으로 틀림** | Kotkov 2018의 novelty는 **사용자가 그 항목을 몰랐다/소비하지 않았다**(strict·motivational 변형)이고, 비인기 지표가 아니다. 비인기는 집단 수준 대리변수라고 적는다. unexpectedness도 변형이 4가지라 "어느 변형에 대응하는지"를 적어야 한다(우리 `u_cat`·`u_spatial`은 implicit 계열로 보임 **[미확인]**) |
| 3 | 2장 표 6행, 3장 6행 | "arXiv 2507.03503: 원시 인기 대신 '구조로 기대되는 인기 대비 잔차'로 인기를 보정" / "인기 자체보다 '기대 대비 인기'를 보정해야 한다" | **틀림** | 정확한 서지: Forster, Kopeinik, Helic, Thalmann, Kowald, RecSys 2025. 내용은 **맥락 인지 모형(LORE, USG)과 보정 인기도 재정렬(CP)이 인기 편향을 줄이는지** 비교한 것이다. 잔차 보정이 아니다. `u_resid`의 근거에서 빼고, 근거 없는 우리 설계라고 적거나 다른 근거를 찾는다 |
| 4 | 2장 표 4행 "Mobile Personal Guide (MDM 2016)" | 이름·서술 | **부분적으로 틀림(서지)** | 정확한 논문명은 "MPG: Not So Random Exploration of a City"(Ge, Chrysanthis, Pelechrinis, MDM 2016, pp.72–81). MPG는 PrefDiv(Preferential Diversity)를 바탕으로 한다. "선호·인기·거리 균형 + 다양성"은 후속작(EDBT 2017 워크숍)의 변형 PD(pop+dist) 설명과 맞지만, MDM 2016 본문의 가중 방식은 **미확인** |
| 5 | 2장 표 5행, 3장 5행 | "Rahmani et al. 2022: POI 인기 편향" | **맞음(범위 한정)** | 다만 원문의 주제는 **인기 편향 + 활동 사용자 불공정**이다. 제목 "The Unfairness of Active Users and Popularity Bias in Point-of-Interest Recommendation"(BIAS@ECIR 2022)으로 서지를 고친다 |
| 6 | 2장 표 8행, 3장 8행 | "Pappalardo 2015: 사람마다 탐험 성향이 다르다" | **맞음** | 단 개인 궤적(휴대전화 GSM·GPS)으로 정의한 k-returner/k-explorer 구분이라, 집계 OD로는 직접 재현할 수 없다는 점을 더 분명히 한다 |
| 7 | 2장 표 9행, 3장 9행 | "Chowdhury 2020 EJTIR: 재량 통행의 novelty-seeking" / "새로움 추구가 실제로 효용에 들어간다" | **부분적으로 틀림** | 정확한 논문명 "Inter- and Intrapersonal variation in destination choice"(Chowdhury, La Paix, Geurs, EJTIR 20(4), 2020). 결과는 **덜 자주 가는 목적지에서 개인 내 변동이 크다**는 것이고, 이를 novelty/variety-seeking으로 **해석**했다. "새로움 추구 항이 효용에 들어감을 추정했다"는 초록 수준에서 확인되지 않는다 |
| 8 | 2장 표 10행, 3장 10행, 4.3-3 | "Kemperman et al.: 목적지 선택 효용식의 variety-seeking 항" / "관성 상권과의 거리" 항 | **부분적으로 틀림(서지 미특정·내용 차이)** | 특정 논문: Kemperman, Borgers, Oppewal, Timmermans (2000) Leisure Sciences 22:1–18, 테마파크 선택의 **컨조인트 선택 모형**에서 계절성·다양성 추구로 **시간에 따라 선호가 바뀌는** 구조. 반복 선택(이전 방문)에 의존하는 항이라 '관성 상권과의 공간 거리'와 같은 정의가 아니다 **[수식 미확인]** |
| 9 | 2장 표 11행, 3장 11행 | "Quercia et al. 2014: 평균 12% 우회" | **맞음(2차 출처)** | 언론·요약 출처 기준 런던에서 평균 약 12% 길고, 아름다움 +30%·조용함 +26%·행복 +30%. 런던 30명·보스턴 54명 검증. 보스턴은 더 길었다는 보도가 있다. 원문 표 수치 확인 필요 |
| 10 | 2장 표 12행, 3장 12행 | "PMC9008453: 의외성이 구매 의도를 낮출 수 있다" | **맞음, 근거 범위 보충 필요** | 정확한 서지: "Effect of Serendipity in an Encounter on Purchase Intention of Unexpected Products", Frontiers in Psychology 2022(PMID 35432132). 추천 시스템 실험이 아니라 **소비자 실험**이고, **지각된 위험**이 매개하며 **예방 초점(prevention focus)** 소비자에서 부정 효과가 커진다. "R 하한"만으로는 이 경로(위험)를 막지 못한다 |
| 11 | 2장 표 3행, 3장 3행, 5.2 해석 | DISCOVERY "정확도가 올라도 범주 다양성·커버리지가 기준선보다 낮을 수 있다" | **맞음** | 초록 그대로: 세렌디피티가 정확도를 올리고 **가까운·설명 가능한 POI를 선호**하지만, 표준 기준선이 범주 다양성·커버리지에서 앞선다. 정확한 서지 "Does Serendipity Enhance Recommendation Quality? Measuring Accuracy and Beyond-Accuracy Objectives of Serendipitous POI Suggestions"(ECAI 2024) |
| 12 | 2장 표 2행, 3장 2행 | "JCST 2021 … 오프라인 지표는 사용자 인식과 어긋날 수 있다" | **판정 보류** | 서지는 Ziarani & Ravanmehr, JCST 36(2):375–396, 2021. 초록은 '정확도 과강조 → 과특화', '참신성·다양성만으로는 관련성이 보장되지 않아 의외성·관련성을 함께 봐야 함'까지만 확인. "오프라인 지표와 사용자 인식 불일치" 문장은 원문 확인 전까지 출처를 붙이지 않는다 |
| 13 | 2장 표 7행, 4.3-4, 5.5 | "Mauro, Minici, Pappalardo 2025: 개인은 다양해져도 도시 전체 쏠림은 커짐" | **맞음** | 서지: "The urban impact of AI: modelling feedback loops in location-based recommender systems", Machine Learning(Springer, DOI 10.1007/s10994-025-06904-z; 권호 연도는 2025/2026 표기 혼재). 단 우리 5.5는 되먹임 루프가 없는 1회 산술이라 "Mauro 2025를 따라"라고 쓰기엔 방법이 다르다 |

---

## 1. Kotkov, Wang, Veijalainen (2016) — 세렌디피티 서베이

- **서지**: Denis Kotkov, Shuaiqiang Wang, Jari Veijalainen. "A survey of serendipity in recommender systems." *Knowledge-Based Systems* 111 (2016): 180–192. DOI [10.1016/j.knosys.2016.08.014](https://doi.org/10.1016/j.knosys.2016.08.014)
- **확인 범위**: 초록, 서지, 목차 제목("Serendipity definitions and metrics")만. 출판사 비공개·셀프 아카이빙 없음(research.fi 표기). 저자 학위논문 PDF(jyx.jyu.fi)는 차단.
- **문제 정의(초록)**: 추천은 과거 행동과 비슷한 항목을 주는 경향이 있다. 세렌디피티 정의·형식화 비교, 세렌디피티 지향 알고리즘 분류, 평가 전략, 향후 과제를 정리한다. RQ1 "추천 시스템에서 세렌디피티란 무엇인가".
- **데이터**: 서베이라 해당 없음.
- **방법·지표**: 원문 미확인. **[사전 지식·미확인]** 서베이는 세렌디피티를 관련성·새로움·의외성 성분으로 정리하고, 대표 지표로 Murakami et al.(2008)과 Ge et al.(2010)을 소개한다. Ge 식은 대략 `UNEXP = RS \ PM`(추천 목록에서 단순 기준 모형 PM의 목록을 뺀 것), `SRDP = |UNEXP ∩ USEFUL| / |RS|` 형태다. Murakami 식은 기준 모형 대비 예측 확률이 더 높고 관련 있는 항목에 가점하는 합 형태다.
- **우리 로직에 쓸 만한 것**: PM(단순 기준 모형) 개념이 우리 '관성 기준선 3종'과 같다. 집계 데이터로도 계산 가능(USEFUL = R ≥ 0.6로 대체). → Top 5 #1.
- **현재 문서 대조**: "곱 형태 지표"는 원문 확인 전까지 근거로 쓰지 말 것(0-2 #1).
- **우리 설계에 반하는 근거**: 확인 못 함.

## 2. Kotkov, Konstan, Zhao, Veijalainen (2018) — 실제 사용자 피드백 기반 세렌디피티 조사

- **서지(특정 완료)**: Denis Kotkov, Joseph A. Konstan, Qian Zhao, Jari Veijalainen. "Investigating serendipity in recommender systems based on real user feedback." *Proceedings of the 33rd Annual ACM Symposium on Applied Computing (SAC 2018)*, Pau, France, pp. 1341–1350. DOI [10.1145/3167132.3167276](https://doi.org/10.1145/3167132.3167276). 데이터셋: [GroupLens Serendipity 2018](https://grouplens.org/datasets/serendipity-2018/)
- **관련 후속작**: Kotkov 학위논문 *Serendipity in Recommender Systems* (University of Jyväskylä, JYU Dissertations / Jyväskylä Studies in Computing 281, 2018).
- **확인 범위**: 초록, 인용 논문 요약, 학위논문 검색 단편. 전문 미확인.
- **문제 정의**: 세렌디피티 정의가 연구마다 다르고, 기존 알고리즘은 세렌디피티 피드백이 없는 공개 데이터로 평가된다. 실제 사용자 응답으로 정의들을 비교한다.
- **데이터(초록)**: MovieLens 사용자 **475명**, 영화 **2,146편**에 대한 설문 응답. 개인 이력 기반.
- **방법**: 세렌디피티 **8가지 변형**을 정의하고 사용자 응답으로 비교(인용 요약). **[사전 지식·미확인]** novelty 2종(strict: 처음 들음 / motivational: 들어봤지만 소비 안 함) × unexpectedness 4종(relevant / find / implicit / recommend) = 8. 각 성분은 5점 척도 문장 동의로 판정. 학위논문 단편에서 확인된 정의: motivational novelty = "The user has heard about the item, but has not consumed it", unexpectedness (recommend) = "The user does not expect the item to be recommended to them".
- **핵심 결과(초록)**: "대부분의 세렌디피티 종류와 모든 성분 변형이 사용자 선호를 넓힌다. 그러나 **의외성의 한 변형은 사용자 만족을 해친다**." 변형마다 선호 확장·만족 효과가 다르다. 학위논문 단편: unexpectedness(find)가 unexpectedness(implicit)보다 만족도에서 낫다.
- **우리 로직에 쓸 만한 것**: ① 설문 문항을 원문 문항으로 맞추기(4.2 Kotkov식 3문항을 8변형이 구분되게 5~6문항으로). ② 공개 데이터셋 구조(항목별 성분 응답)를 우리 설문 라벨 스키마로 차용. 집계 OD로는 성분 정의 자체를 재현할 수 없다(개인이 '알았는지'가 핵심).
- **현재 문서 대조**: 0-2 #1, #2.
- **우리 설계에 반하는 근거**: **있음.** 만족을 떨어뜨리는 의외성 변형이 존재한다. 우리 U의 절반(`u_cat`+`u_spatial`)이 "관성과 다르다"는 implicit 계열이면 만족 하락 위험이 있다(Top 5 #3). 변형 정의는 전문으로 꼭 확인.

## 3. 세렌디피티 추천 체계적 문헌고찰 (JCST 2021)

- **서지(특정 완료)**: Reza Jafari Ziarani, Reza Ravanmehr. "Serendipity in Recommender Systems: A Systematic Literature Review." *Journal of Computer Science and Technology* 36(2): 375–396, 2021. DOI [10.1007/s11390-020-0135-9](https://doi.org/10.1007/s11390-020-0135-9)
- **확인 범위**: 초록만. 저널 사이트 전문 PDF는 차단.
- **문제 정의(초록)**: 정확도 과강조는 정보 과특화와 지루한 추천을 낳는다. 참신성·다양성만으로는 사용자에게 관련 있지 않을 수 있어 의외성과 관련성을 함께 봐야 한다. 정의·데이터셋·평가 기법의 맥락적 수렴을 정리한다.
- **결과(초록)**: 세렌디피티 추천 연구의 질과 양이 늘고 있다. 경향과 향후 가능성 논의.
- **미확인**: 연구 질문 목록, 검토 편수, 지표 분류표.
- **우리 로직에 쓸 만한 것**: 원문 지표 분류표를 확인한 뒤 4장 평가 설계 근거로 쓸 수 있다. 지금은 "beyond-accuracy를 함께 본다" 수준만 근거로 쓸 수 있다.
- **현재 문서 대조**: 0-2 #12(판정 보류).
- **반하는 근거**: 확인 못 함.

## 4. Ben Sassi, Järv, Ben Yahia (2024) — DISCOVERY

- **서지**: Imen Ben Sassi, Priit Järv, Sadok Ben Yahia. "Does Serendipity Enhance Recommendation Quality? Measuring Accuracy and Beyond-Accuracy Objectives of Serendipitous POI Suggestions." *ECAI 2024*, Frontiers in Artificial Intelligence and Applications 392, pp. 3096–3103. DOI [10.3233/FAIA240852](https://doi.org/10.3233/FAIA240852). 공개본: HAL `lirmm-04765352v1`
- **확인 범위**: 초록만(IOS Press 오픈 PDF·HAL 모두 차단).
- **데이터**: Foursquare, Flickr(개인 체크인·사진 이력).
- **방법**: 정확도-세렌디피티 균형을 개선하려는 POI 추천기 DISCOVERY. 비세렌디피티 POI 추천기 3종과 비교. 세렌디피티 측정식 미확인.
- **결과(초록)**: 세렌디피티가 POI 추천 정확도를 올리고 **지리적으로 가깝고 설명 가능한 POI를 선호**한다. 표준 기준선이 **범주 다양성·커버리지**에서 DISCOVERY를 앞선다.
- **우리 로직에 쓸 만한 것**: 우리 5.2에서 상권 유형 수·ILD가 거리순보다 낮은 결과와 같은 방향. MMR을 따로 두는 근거로 유효.
- **현재 문서 대조**: 0-2 #11 맞음.
- **반하는 근거(약함)**: 원문에서는 세렌디피티 모형이 **가까운** POI를 선호했다. 우리 `u_spatial`은 관성에서 **먼** 곳에 가점한다. 방향이 다르다는 점을 3장에 적을 것(우리 '먼 곳'은 관성 기준 거리이고, 출발지 기준으론 5.4km로 인기순보다 가깝긴 하다).

## 5. MPG — "Mobile Personal Guide" (MDM 2016)

- **서지(특정 완료)**: Xiaoyu Ge, Panos K. Chrysanthis, Konstantinos Pelechrinis. "MPG: Not So Random Exploration of a City." *17th IEEE International Conference on Mobile Data Management (MDM 2016)*, Porto, pp. 72–81. (DOI는 IEEE 검색으로 확인 필요)
- **후속·관련**: Ge et al. "In Search for Relevant, Diverse and Crowd-screen Points of Interests"(EDBT 2017 워크숍, openproceedings.org), "Serendipity-based Points-of-Interest Navigation"(ACM TOIT 2020, DOI 10.1145/3391197), PrefDiv(Preferential Diversity), pPrefDiv.
- **확인 범위**: 서지와 후속작 검색 단편만.
- **방법(후속작 단편)**: MPG는 PrefDiv 기반. PrefDiv 변형들은 장소 순위용 '강도(intensity)' 값 계산 방식이 다르다. 예: `PD(pop+dist)`는 인기와 현재 위치로부터의 거리를 관련성 점수로 쓴다.
- **우리 로직에 쓸 만한 것**: "관련성 점수 = 선호·인기·거리 결합 → 그 위에서 다양성 최대화" 구조는 우리 R → MMR과 같다. PrefDiv 식을 확인하면 MMR 대안(선호 강도 비례 다양화)으로 비교 실험 가능. 집계 데이터로 가능.
- **현재 문서 대조**: 0-2 #4.
- **반하는 근거**: 이 계열은 **인기를 관련성에 양(+)으로** 넣는다. 우리는 인기를 U에서 역방향(`u_novelty`)으로 쓴다. 정반대 처리라는 점을 문서에 명시해야 한다.

## 6. Rahmani et al. (2022) — POI 추천의 인기 편향·활동 사용자 불공정

- **서지**: Hossein A. Rahmani, Yashar Deldjoo, Ali Tourani, Mohammadmehdi Naghiaei. "The Unfairness of Active Users and Popularity Bias in Point-of-Interest Recommendation." *BIAS @ ECIR 2022*, CCIS 1610, Springer, pp. 56–68. 코드: [github.com/RecSys-lab/FairPOI](https://github.com/RecSys-lab/FairPOI)
- **확인 범위**: 저장소 README 요약과 인용 리뷰. 전문 미확인.
- **결과(README)**: 최신 알고리즘이 소수의 활동 사용자에게 더 나은 추천을 주고 다수의 비활동 사용자는 덜 맞춤된 추천을 받는다. 대부분 인기 장소를 추천해 항목 불공정을 낳는다.
- **우리 로직에 쓸 만한 것**: 인기순을 관성 기준선으로 두는 근거. 원문의 항목 노출 지표(인기 집단별 노출 비율 등)를 확인해 우리 노출 지니 옆에 추가할 수 있다.
- **현재 문서 대조**: 0-2 #5.
- **반하는 근거**: 확인 못 함.

## 7. arXiv 2507.03503 (2025) — 맥락 인지와 인기 보정

- **서지(특정 완료)**: Andrea Forster, Simone Kopeinik, Denis Helic, Stefan Thalmann, Dominik Kowald. "Exploring the Effect of Context-Awareness and Popularity Calibration on Popularity Bias in POI Recommendations." arXiv:2507.03503, RecSys 2025 채택.
- **확인 범위**: 검색 결과의 초록 요약과 제3자 요약(Pith). 전문 미확인.
- **데이터**: Brightkite, Foursquare, Gowalla, Yelp(개인 체크인).
- **방법**: 비맥락 BPR 대비 맥락 인지 모형(LORE, USG)과 보정 인기도 재정렬(CP)을 단독·결합으로 비교. 인기 편향 지표 ARP(Average Recommendation Popularity), PopLift.
- **결과(요약)**: LORE + CP 결합이 각 사용자의 head/mid/tail 인기 분포와 맞는 목록을 내면서 정확도를 유지(제3자 요약, 확인 필요).
- **우리 로직에 쓸 만한 것**: Top 5 #4. 집계 OD에서 '동대문구발 유입의 인기 구간 분포'를 기준 분포로 두고 CP를 적용 가능.
- **현재 문서 대조**: 0-2 #3 **틀림**.
- **반하는 근거**: CP는 비인기를 **최대화**하지 않고 기준 분포에 **맞춘다**. 우리 `u_novelty`(비인기일수록 가점)는 tail 과대 노출 위험이 있다.

## 8. Mauro, Minici, Pappalardo (2025) — 위치 추천의 도시 영향

- **서지**: Giovanni Mauro, Marco Minici, Luca Pappalardo. "The urban impact of AI: modelling feedback loops in location-based recommender systems." *Machine Learning* (Springer). DOI [10.1007/s10994-025-06904-z](https://doi.org/10.1007/s10994-025-06904-z). 선행 프리프린트 제목 "The Urban Impact of AI: Modeling Feedback Loops in Next-Venue Recommendation".
- **확인 범위**: 초록·인용 요약. 전문 미확인.
- **방법(초록)**: 사용자가 매번 추천을 따를지, 기존 인간 이동 모형대로 움직일지 고르는 시뮬레이션. 이동 결과가 다시 추천기 학습에 들어가 루프를 닫는다.
- **결과(초록)**: 추천기는 개인 수준 방문 다양성을 꾸준히 높이지만, 방문을 소수 인기 장소로 모아 집단 불평등을 키울 수 있다. 대부분의 추천기에서 개인·집단 다양성이 갈라진다.
- **데이터**: 개인 체크인 궤적(세부 미확인).
- **우리 로직에 쓸 만한 것**: Top 5 #5. 수용률 p를 축으로 반복 시뮬레이션.
- **현재 문서 대조**: 0-2 #13.
- **반하는 근거**: 없음(우리 가드레일 방향과 일치).

## 9. Pappalardo et al. (2015) — Returners와 Explorers

- **서지**: Luca Pappalardo, Filippo Simini, Salvatore Rinzivillo, Dino Pedreschi, Fosca Giannotti, Albert-László Barabási. "Returners and explorers dichotomy in human mobility." *Nature Communications* 6, 8166 (2015). DOI [10.1038/ncomms9166](https://doi.org/10.1038/ncomms9166)
- **확인 범위**: 초록, 보충자료 검색 단편. 전문 미확인(nature.com 미시도·허용 필요).
- **데이터**: 개인 GSM 통화 기록, GPS 궤적(규모 미확인).
- **방법**: 상위 k개 최다 방문 장소로 계산한 회전반경과 전체 회전반경을 비교해 k-returner/k-explorer 구분 **[사전 지식: 비율 s_k = r_g^(k)/r_g, 기준 0.5 — 미확인]**. 두 집단을 함께 재현하는 개선 이동 모형 제안.
- **결과(단편)**: GSM 데이터에서 작은 k에선 k-explorer가 많고, k=4부터 k-returner가 더 많다. 2-returner의 방문지는 두 최다 장소 주변에 모이고 2-explorer는 퍼져 있다.
- **우리 로직에 쓸 만한 것**: 집계 OD로는 개인 구분 불가. 대신 상권(목적지) 쪽에서 "유입 출발지의 공간 분산"을 재는 것은 가능(집계 OD의 출발지 분포 회전반경). 탐험 성향 슬라이더 설계 근거로만 쓴다.
- **현재 문서 대조**: 0-2 #6 맞음.
- **반하는 근거**: 없음.

## 10. Chowdhury, La Paix, Geurs (2020) — 목적지 선택의 개인 간·개인 내 변동

- **서지(특정 완료)**: Shamsunnahar Chowdhury(저자 표기 확인 필요), Lissy La Paix, Karst Geurs. "Inter- and Intrapersonal variation in destination choice." *European Journal of Transport and Infrastructure Research* 20(4): 194–213, 2020. DOI [10.18757/ejtir.2020.20.4.3951](https://doi.org/10.18757/ejtir.2020.20.4.3951)
- **확인 범위**: 초록 수준. EJTIR·트벤테대 공개 PDF가 있으나 이번 세션에서 미열람.
- **결과(초록)**: 덜 자주 가는 장소에서 목적지·출발 시각·수단 선택의 개인 내 변동이 비교적 크다. 이를 목적지 선택의 novelty-seeking 근거로 해석. 재량 목적지에서 개인 내 변동이 크고 자유 시간의 variety-seeking과 연결. 활동·출발 시각·목적지 선택 사이 연관이 강하다.
- **데이터**: 개인 다일(多日) 통행 자료로 보임 **[미확인]**.
- **우리 로직에 쓸 만한 것**: 재량 목적에만 적용한다는 범위 설정의 근거로는 유효. 출발 시각과 목적지 선택이 강하게 연결된다는 결과는 **U를 시간대별로 나눌 근거**(우리 08·14·19시 도달률과 연결).
- **현재 문서 대조**: 0-2 #7.
- **반하는 근거**: 없음. 다만 "효용에 새로움 항이 들어간다"는 과장.

## 11. Kemperman et al. — variety-seeking 목적지 선택

- **서지(특정)**: Astrid Kemperman, Aloys Borgers, Harmen Oppewal, Harry Timmermans. "Consumer Choice of Theme Parks: A Conjoint Choice Model of Seasonality Effects and Variety Seeking Behavior." *Leisure Sciences* 22(1): 1–18, 2000. 관련: Kemperman 학위논문 "Temporal aspects of theme park choice behavior"(TU Eindhoven, 2000).
- **확인 범위**: 서지와 인용 요약만. 효용식 미확인.
- **방법(요약)**: 테마파크 선택이 계절성·다양성 추구의 영향을 받는지 검증. 전통 컨조인트 선택 모형과 달리 개인의 선호가 시간에 따라 변할 수 있게 함. 다른 문헌은 이 틀을 '다양성 추구·계절성·분산(diversification)의 세 측면 + 시간 차원'으로 인용.
- **결과(인용)**: 시간에 걸친 목적지 선택에서 계절성과 다양성 추구가 유의한 영향.
- **데이터**: 진술 선호(컨조인트 실험) **[미확인]**.
- **우리 로직에 쓸 만한 것**: 4.3-3의 "조건부 로짓에 variety-seeking 항"은 방향은 맞지만, 원 모형은 **이전 선택(직전 방문)에 의존**하는 항이다. 집계 OD에선 개인의 직전 방문이 없으므로 그대로 추정 불가. 대안: 진술 선호 설문(우리 4.2)을 컨조인트로 설계하면 원 논문 방식을 그대로 쓸 수 있다.
- **현재 문서 대조**: 0-2 #8.
- **반하는 근거**: 확인 못 함.

## 12. Quercia, Schifanella, Aiello (2014) — 행복한 최단 경로

- **서지**: Daniele Quercia, Rossano Schifanella, Luca Maria Aiello. "The Shortest Path to Happiness: Recommending Beautiful, Quiet, and Happy Routes in the City." *Proceedings of the 25th ACM Conference on Hypertext and Social Media (HT 2014)*. arXiv:1407.1031. 공개본: researchswinger.org, iris.unito.it.
- **확인 범위**: 초록, 언론·요약 2차 출처. 전문 미확인.
- **데이터·방법**: 크라우드소싱 플랫폼에서 런던 거리 사진 쌍을 비교해 아름다움·조용함·행복 점수를 매기고, 거리와 이 점수를 함께 고려하는 경로 추천. 런던 30명, 보스턴 54명 사용자 검증(언론).
- **결과(2차 출처)**: 추천 경로는 최단 경로보다 평균 **약 12% 길고**, 아름다움 +30%, 조용함 +26%, 행복 +30%. 몇 분 더 걸을 뿐이라는 표현. 보스턴은 더 길었다는 보도.
- **우리 로직에 쓸 만한 것**: "작은 우회 비용 대비 체감 효용"을 보고하는 방식. 우리 결과도 '관성 대비 추가 이동시간(분)'을 반드시 같이 보고. 집계 데이터로 가능(ODsay 측정 시).
- **현재 문서 대조**: 0-2 #9 맞음(2차 출처 기준).
- **반하는 근거**: 없음. 단 경로 연구라 목적지 추천으로의 이전은 해석상 비유.

## 13. PMC9008453 (2022) — 우연한 만남의 세렌디피티와 구매 의도

- **서지(특정 완료)**: "Effect of Serendipity in an Encounter on Purchase Intention of Unexpected Products." *Frontiers in Psychology* (2022). DOI [10.3389/fpsyg.2022.848907](https://doi.org/10.3389/fpsyg.2022.848907), PMID 35432132, PMCID PMC9008453. 저자 미확인.
- **확인 범위**: 초록 수준. PMC·Frontiers 전문 미열람.
- **방법·결과(초록)**: 소비자 실험. 우연히 마주친 의외 제품에서 세렌디피티가 불확실성 → **지각된 위험**을 높여 구매 의도를 낮춘다(지각된 위험이 매개). **조절초점**이 조절: 예방 초점에서 부정 효과 강화, 촉진 초점에서 약화.
- **우리 로직에 쓸 만한 것**: 설문에 '가 보기 망설여진다(위험 지각)' 문항 추가. 이유 문장(`reason`)에 위험을 줄이는 정보(관련성 근거, 거리·시간)를 함께 보여 주는 설계 근거.
- **현재 문서 대조**: 0-2 #10.
- **반하는 근거**: **있음(약함).** 부정 효과의 경로는 관련성 부족이 아니라 **위험 지각**이다. R 하한 0.6은 이 경로를 직접 막지 못한다. 이 연구를 R 하한의 근거로 쓰면 어긋난다.

---

## 14. 우리 설계(S = R×U, R 하한 0.6, U 4성분, MMR λ=0.7)에 대한 원문 근거 요약

| 설계 요소 | 지지 근거 | 반하거나 약화하는 근거 | 확인 수준 |
|---|---|---|---|
| S = R × U 곱 | 없음(곱 형태를 원문이 쓴다는 확인 없음) | Kotkov 2018은 AND 조합 정의 | 초록 |
| R 하한 0.6 | 세렌디피티 = 관련성 필수(Kotkov 계열, JCST 초록 '관련성도 함께') | 값 0.6의 근거는 어느 원문에도 없음. PMC9008453의 부정 효과는 위험 지각 경로 | 초록 |
| `u_resid` | 없음(2507.03503은 잔차 보정 아님) | — | 초록 |
| `u_novelty` (비인기) | Rahmani 2022 인기 편향 | 2507.03503 CP는 분포 맞춤, MPG 계열은 인기를 관련성에 (+) | 초록 |
| `u_cat`·`u_spatial` (관성과의 거리) | Ge/Murakami의 기준 모형 대비 정의 [미확인] | Kotkov 2018: 한 의외성 변형은 만족 저하. DISCOVERY: 세렌디피티 모형은 가까운 POI 선호 | 초록 |
| MMR λ=0.7 | DISCOVERY(다양성 손실 경고), MPG/PrefDiv(관련성 위 다양화) | λ 값의 근거는 원문 없음 | 초록 |

## 15. 다음 세션에서 할 일(전문 확인)

1. 환경 Network access에 아래 호스트를 허용: `arxiv.org`, `pmc.ncbi.nlm.nih.gov`, `www.frontiersin.org`, `jyx.jyu.fi`, `jcst.ict.ac.cn`, `ebooks.iospress.nl`, `hal-lirmm.ccsd.cnrs.fr`, `www.nature.com`, `journals.open.tudelft.nl`, `research.utwente.nl`, `openproceedings.org`, `researchswinger.org`, `iris.unito.it`, `will-qianzhao.github.io`, `dl.acm.org`, `link.springer.com`.
2. 우선순위: ① Kotkov 학위논문(jyx, 2016 서베이 수식과 2018 8변형 결과 포함) → ② 2507.03503 전문 → ③ Ziarani 2021 지표 분류 → ④ DISCOVERY HAL 공개본 → ⑤ 나머지.
3. **[사전 지식·미확인]** 표시 항목을 원문 문장으로 바꾸고, 0-2 판정을 확정한다.
