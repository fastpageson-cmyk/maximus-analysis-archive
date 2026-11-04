# 점포 단위 v1 로컬 실행 프롬프트

원천(상가정보·인허가)과 점포 테이블은 사용자 Mac에만 있다. 아래 블록을 Mac의 로컬 에이전트(Claude Code·Codex 등)에 **그대로** 붙여 넣는다. 블록 하나로 끝까지 진행된다.

변경 내용: `docs/store_level/v1_changes.md` · 열 설명: `data/processed/store_level/README.md` v1 절

````text
너는 막시무스 프로젝트 저장소(maximus-analysis-archive)에서 점포 단위 추천 v1을 로컬 데이터로 다시 만든다. 답과 보고는 한국어로 짧게 한다.

## 0. 준비
1. 저장소 루트로 이동한다. 작업 폴더(저장소의 상위 어딘가)에 `데이터/원천/서울캠`, `데이터/가공/서울캠`이 있어야 한다. 없으면 멈추고 알려라.
2. 브랜치를 받는다.
   git fetch origin gunwoo/store-level
   git checkout -B gunwoo/store-level origin/gunwoo/store-level
   git status  # 깨끗해야 한다. 커밋 안 된 변경이 있으면 멈추고 알려라
3. 파이썬은 ~/.venvs/maximus/bin/python 만 쓴다. 테스트를 먼저 돌린다(테스트는 -I 없이, 저장소 루트에서).
   ~/.venvs/maximus/bin/python -m pytest -q
   실패하면 멈추고 실패 내용을 그대로 보고한다. 테스트를 끄거나 건너뛰지 마라.

## 1. v1 파이프라인 (순서대로, 각 로그를 /tmp/maximus_v1_<단계>.log 로도 남긴다)
   ~/.venvs/maximus/bin/python -I scripts/campus/서울캠/build_seoul_store_table_v1.py      2>&1 | tee /tmp/maximus_v1_table.log
   ~/.venvs/maximus/bin/python -I scripts/store_level/build_store_candidates_v1.py                       2>&1 | tee /tmp/maximus_v1_candidates.log
   ~/.venvs/maximus/bin/python -I scripts/store_level/build_store_serendipity_v1.py                      2>&1 | tee /tmp/maximus_v1_serendipity.log
   ~/.venvs/maximus/bin/python -I scripts/store_level/validate_store_serendipity_v1.py                   2>&1 | tee /tmp/maximus_v1_validate.log
   ~/.venvs/maximus/bin/python -I scripts/store_level/compare_store_serendipity_v0_v1.py                 2>&1 | tee /tmp/maximus_v1_compare.log
- 오류가 나면 원인을 찾아 최소한으로 고치고, 무엇을 왜 고쳤는지 보고에 적는다.
- `scripts/campus/서울캠/store_rules_v1.py`의 규칙 상수(키워드·제외 목록·BOUNDARY_SUBTYPES·STUDY_INCLUDE_BOOKS)는 바꾸지 마라. 이상해 보이면 보고에 제안만 적는다.
- v0 파일·스크립트는 지우거나 덮어쓰지 마라. v1 스크립트는 `_v1` 파일만 쓴다.

## 2. 점검 (출력만, 커밋 안 함. 단 2-3 감사 표본은 커밋)
2-1. seoul_store_table_v1.csv에서:
   - category_source 분포, category_fixed 수, (소분류명_원 → 소분류명) 상위 20쌍
   - exclude_reason 분포, 사유별 상위 소분류명 10개
   - 목적별 점포 수(전체·비프랜차이즈)를 v0 테이블(seoul_store_table_v0.csv)과 나란히
   - 공부 목적 점포의 소분류명 분포(독서실/스터디 카페·서점·북카페 외 다른 게 있으면 목록)
   - destination=False이면서 목적이 있는 점포 수, 목적별
2-2. 예시 가게 확인(상호 부분 일치로 찾는다. 없으면 '테이블에 없음'):
   - '출장열쇠' → 목적 빈칸, exclude_reason 있음
   - 'INTERNATIONALSPORTSREHAB' → 목적 빈칸
   - '마이보쌈' → 소분류명 족발/보쌈, category_source name_rule
   - '상계솥뚜껑삼겹살' → 돼지고기 구이/찜
   - '킹스컵밥' → 김밥/만두/분식, 목적 식사
   - store_serendipity_top30_v1.csv 공부 목록에 학원·문구가 없는지, PC방·여관/모텔·호텔/리조트·헬스장이 여가 목록에 없는지
2-3. 업종 보정 감사 표본: category_fixed=True 점포 50곳을 무작위(seed 42)로 뽑아
   data/processed/store_level/category_fix_audit_sample_v1.csv 로 저장한다.
   열: 상호, 소분류명_원, 소분류명, category_source, 위생업태, 판정(빈칸), 판정_claude, 근거_claude.
   좌표·store_id·area_code는 넣지 않는다. 판정_claude에 '맞음/틀림/애매'와 한 줄 근거를 채운다(상호만 보고 판단). 판정 칸은 사람이 채우므로 비워 둔다.

## 3. v0 대비 비교 보고
data/processed/store_level/store_serendipity_v0_v1_compare.md(스크립트가 만든다)를 바탕으로 아래를 표로 정리한다.
   - 목적별 추천 수 v0 → v1, 남음/빠짐/새로 들어옴, 목적별 상권 수
   - 빠진 가게 목록과 사유(store_rules_v1_preimpact_top30.csv 판정. '규칙 해당 없음(순위 밀림)'은 v1 규칙이 아니라 다른 가게가 올라와 밀린 것)
   - 새로 들어온 가게 중 목적별 상위 5곳
   - 설문 카드 덱: 방법별(serendipity / near_rep / random_area / inertia_rule) 카드 수와 공공 태그 없는 카드 비율 v0 → v1
   - validation_summary_v1.json의 4_contribution(ILD, 관성 상권 겹침률)과 6_survey(has_tag_by_method)를 v0와 나란히
   - 민감도 store_serendipity_sensitivity_v1.csv 자카드 범위(가중치 ±0.1, K=20)를 v0와 나란히
   - 사전 추정(docs/store_level/v1_changes.md 3절)과 실제가 다른 곳
이 내용을 docs/store_level/v1_changes.md 맨 끝에 '## 6. 로컬 실행 결과 (YYYY-MM-DD)' 절로 추가한다. 3절의 사전 추정은 지우지 말고 그대로 둔다.
data/processed/store_level/README.md v1 절의 '### v1 한계' 위에 '### v1 실행 결과' 몇 줄(목적별 추천 수, 제외 사유 분포 요약)을 넣는다.

## 4. 커밋 규칙
- 커밋해도 되는 것만 경로를 하나씩 지정해서 git add 한다(git add . / -A 금지):
  data/processed/store_level/store_serendipity_top30_v1.csv
  data/processed/store_level/store_serendipity_sensitivity_v1.csv
  data/processed/store_level/survey_cards_v1.csv
  data/processed/store_level/survey_cards_key_v1.csv
  data/processed/store_level/validation_summary_v1.json
  data/processed/store_level/store_serendipity_v0_v1_compare.md
  data/processed/store_level/category_fix_audit_sample_v1.csv
  docs/store_level/v1_changes.md, data/processed/store_level/README.md
  (1단계에서 코드를 고쳤다면 그 스크립트)
- 절대 커밋 금지: 데이터/ 아래 전부(원천·가공 점포 테이블 seoul_store_table_v*.csv, store_candidates_v*.csv, store_serendipity_v*.csv), 캐시(ODsay·네이버), API 키·.env, 좌표(lat/lon)·store_id·place_id가 든 파일.
- add 뒤 `git diff --cached --stat` 로 파일 목록을 보고, 올라가는 CSV마다 첫 줄(열 이름)에 lat·lon·store_id·place_id·area_code가 없는지 확인한다.
  `git diff --cached | grep -iE "place_id|api[_-]?key|secret|token"` 결과도 비어 있어야 한다. 걸리면 그 파일을 빼고 보고한다.
- 커밋 메시지 형식(한국어 설명 가능):
  feat(store-level): <무엇>   ← 산출물·코드 (예: feat(store-level): v1 상위 30·설문 카드 재생성)
  docs(store-level): <무엇>   ← 문서 (예: docs(store-level): v1 로컬 실행 결과 기록)
  산출물과 문서는 커밋을 나눈다. 파일명·메시지에 final 을 쓰지 않는다.
- git push -u origin gunwoo/store-level. 네트워크 오류면 2·4·8·16초 간격으로 4번까지 다시 시도한다. PR은 만들지 않는다.

## 5. 마지막 보고 (이 순서로, 짧게)
1. 커밋 해시와 메시지
2. 테스트 결과(통과 수)
3. 목적별 추천 수 v0 → v1 표, 빠진 가게 수(사유별)
4. 공공 태그 없는 카드 비율 v0 → v1(방법별)
5. 예시 가게 확인 결과(2-2)
6. 고친 코드가 있으면 무엇을 왜
7. 규칙에 대한 제안(오탐·미탐 예시, 상수 이름과 함께)
````
