# README 목차 (저장소 루트 `README.md`용)

> 아직 저장소에 `README.md`가 없어요. 아래 목차와 각 절에 넣을 내용(→)대로 채우면 돼요.

1. **Watchme** — 한 줄 소개, 배포 링크 https://evrd.fyi, 대표 화면 캡처 3장(시작·기록·리포트)
2. **왜 만들었나** → 문제와 차별점("한국인 평균 대비 내 병 위험"), 학습 목표 2가지(집 서버, 카카오 연동)
3. **주요 기능** → `requirements.md` 2.1 요약(입력 → 위험도 → 맞춤 계획 → 매일 기록 → 주간 요약·PDF → 리포트)
4. **화면 흐름** → `wireframes.md` 1장 Mermaid 흐름도
5. **기술 스택** → Python 3.12, FastAPI, Jinja2, SQLAlchemy 2, PostgreSQL 16, reportlab, 바닐라 JS·CSS(빌드 없음), Docker Compose, Caddy
6. **아키텍처** → 폰 → 공유기(80/443) → Caddy(HTTPS) → app(127.0.0.1:8000) → db, 모듈 표(`routes`·`service`·`risk`·`plan`·`progress`·`report`·`pdf`)
7. **데이터 모델** → `erd.md` Mermaid (1단계 + 2단계 카카오 표)
8. **API** → `api.md` 엔드포인트 표
9. **참고 위험도 계산** → 데이터 출처(KNHANES 2022–2024), 로지스틱 회귀식, 면책 문구, `scripts/knhanes_stats.py`
10. **로컬 실행**
    - `python -m venv .venv` → `.venv/Scripts/pip install -e .[dev]`
    - `.env.example` 복사 → `uvicorn app.main:app --reload`
    - 통계 파일(`app/data/korea_stats.json`)이 없으면 "준비 중" 화면
11. **테스트** → `.venv/Scripts/python -m pytest -q` (152개), TDD로 개발
12. **배포·운영** → 집 서버 구성 요약, `git push` 배포, 백업·삭제 cron, 자세한 건 `docs/server-runbook.md`
13. **보안·개인정보** → 토큰 링크, 최소 수집, 90일 삭제, 요청 제한, 외부 스크립트 없음
14. **로드맵** → 1단계 ✅ / 2단계 카카오 ✅ / 3단계 AI 한 줄 요청(Gemini 무료, 진행 중) / 나중: 주간 AI 코치 한마디, 효도 구독·결제(사업자 정리 후)
15. **문서** → `docs/superpowers/specs/`, `plans/`, `docs/deliverables/`
16. **라이선스·출처** → 글꼴(Pretendard, 나눔고딕 OFL), 통계 자료 출처
