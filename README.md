# Watchme — 30일 생활습관 챌린지

> 체중이 아니라, **한국인 평균 대비 내 병 위험이 내려가는 게 보이는** 30일 챌린지.

**https://evrd.fyi** · 로그인 없이 바로 시작할 수 있어요.

<!-- 대표 화면 캡처 3장(시작·기록·리포트) 자리 -->

## 왜 만들었나
- 체중계 숫자는 동기가 약하고, 건강검진 결과는 1년에 한 번이에요. 생활습관 앱은 로그인·개인정보부터 요구하고 며칠 지나면 잊혀요.
- Watchme는 성별·나이·키·몸무게 4가지만으로 **같은 성별·나이대 평균 대비 고혈압·당뇨 참고 위험도**를 보여 주고, 내 생활에 맞춘 30일 계획과 매일 10초 체크, 카카오톡 아침·저녁 메시지로 습관을 이어 가게 해요.
- 학습 목표: ① 집 서버 직접 구축·운영 ② 카카오톡 연동 끝까지 경험 ③ 무료 LLM API를 최소한으로 붙여 보기.

## 주요 기능
| 영역 | 내용 |
|---|---|
| 참고 위험도 | 국민건강영양조사 2022–2024 원시자료로 만든 가중 로지스틱 회귀(연속 BMI) → "평균보다 N%" |
| 30일 맞춤 계획 | 맞춤 질문 5개 → 규칙 기반 계획(메뉴·운동·팁 풀, 토큰 시드로 항상 같은 계획), 계획 종류 4가지, 강도 0~2단계 |
| 매일 기록 | 오늘 계획 · 체중(선택) · 지켰어요, 도장판에서 지난 날 수정, 의심 카드, 주간 요약 |
| PDF·리포트 | 주간 계획표 PDF(QR), 30일 리포트(체중·위험도 처음 → 지금), 주간 리포트(국민건강영양조사 걷기 통계 또래 비교, 자랑 카드 PNG) |
| 카카오 | 카카오 로그인(`talk_message`만) → "나에게 보내기" 아침 7:30 계획·저녁 9시 확인·주간 리포트, 다른 기기에서 이어 하기, 다음 30일 도전 |
| AI 한 줄 요청 | "매운 거 못 먹어요" → Gemini가 후보 메뉴·운동 중 **뺄 것만** 고름. 실패·8초 초과면 기본 계획 |
| 운영 지표 | 관리자만 여는 `/admin`: 카톡 연결자, 30일 추이, 단계별 전환, 체크 지속률, 발송 결과 |

자세한 요구사항은 [docs/deliverables/requirements.md](docs/deliverables/requirements.md).

## 화면 흐름
시작 → 몸 정보 4문항 → 결과 → 맞춤 질문(+ 한 줄 요청) → 준비 완료 → 매일 기록 → 주간 요약·주간 리포트·PDF → 30일 리포트 → 다음 30일 도전

흐름도와 화면별 와이어프레임: [docs/deliverables/wireframes.md](docs/deliverables/wireframes.md)

## 기술 스택
Python 3.12 · FastAPI · Jinja2(서버 렌더링) · SQLAlchemy 2 · PostgreSQL 16(로컬·테스트는 SQLite) · reportlab(PDF) · Pillow(자랑 카드) · httpx(카카오·Gemini) · cryptography(토큰 암호화) · 바닐라 JS·CSS(빌드 없음, 외부 스크립트 0개) · Docker Compose · Caddy

## 아키텍처
```
폰 → 공유기(80/443) → Caddy(자동 HTTPS) → app(127.0.0.1:8000) → PostgreSQL
                                          ├→ 카카오 OAuth·메시지 API
                                          └→ Gemini API
cron: 아침·저녁 카톡 발송 · 매일 백업 · 90일 지난 체험 삭제
```

| 모듈 | 역할 |
|---|---|
| `routes.py` · `kakao_routes.py` · `admin.py` | 화면·폼 경로, 카카오 로그인, 운영 지표 |
| `service.py` | 체험 생성·설정·기록·강도·다음 도전·보관 삭제 |
| `risk.py` | 참고 위험도 계산 |
| `plan.py` | 30일 계획 생성 |
| `progress.py` · `report.py` · `weekly.py` | 주간 요약·의심 카드, 30일 리포트, 주간 리포트·또래 비교 |
| `pdf.py` · `card.py` · `chart.py` | 주간 PDF, 자랑 카드 PNG, 체중 그래프 SVG |
| `kakao.py` · `accounts.py` · `notify.py` · `messages.py` | 카카오 API, 계정·연결, 발송, 메시지 문구 |
| `ai.py` | Gemini 한 줄 요청 |
| `metrics.py` | 랜딩 조회 카운터, 발송 기록, 지표 집계 |

## 데이터 모델 · API
- 표 11개(1단계 3 · 카카오 4 · AI 1 · 운영 지표 3). 이름·연락처는 어느 표에도 없어요 → [docs/deliverables/erd.md](docs/deliverables/erd.md)
- 경로 목록 → [docs/deliverables/api.md](docs/deliverables/api.md)

## 참고 위험도 계산
- 자료: 질병관리청 국민건강영양조사(KNHANES) 2022–2024 원시자료. `scripts/knhanes_stats.py`가 가중 로지스틱 회귀 계수·유병률·걷기 비율을 `app/data/korea_stats.json`으로 만들어요(원시자료는 저장소에 없어요).
- 계산: 성별×연령대×질환별 P(질환 | BMI) ÷ 같은 성별·연령대 유병률 → "평균보다 N% 높음/낮음".
- **진단이 아닌 참고용**이에요. 모든 화면과 PDF에 면책 문구가 있어요.

## 로컬 실행
```bash
python -m venv .venv
.venv/Scripts/pip install -e .[dev]
cp .env.example .env
.venv/Scripts/uvicorn app.main:app --reload
```
- 카카오·Gemini·`ADMIN_KEY`가 비어 있으면 그 기능만 꺼지고 나머지는 그대로 동작해요.
- `app/data/korea_stats.json`이 없으면 "준비 중" 화면이 나와요.

## 테스트
```bash
.venv/Scripts/python -m pytest -q
```
349개. 기능마다 설계 문서 → 구현 계획 → TDD(테스트 먼저) → 리뷰 순서로 만들었어요. 카카오·Gemini는 실제 호출 없이 테스트해요.

## 배포 · 운영
집 노트북(Ubuntu Server)에서 Docker Compose(app·db·caddy)로 운영해요. `git push`하면 서버 훅이 빌드·재시작·헬스 체크까지 해요. SSH는 Tailscale 내부망만, 인터넷엔 80/443만 열려 있어요. 매일 `pg_dump` 백업과 서버 밖 사본, Porkbun DDNS. 자세한 건 [docs/server-runbook.md](docs/server-runbook.md).

## 보안 · 개인정보
- 추측 불가능한 토큰 링크(`/c/{token}`), `noindex`·`no-referrer`, 요청 제한
- 이름·연락처 수집 없음, 체험 종료 90일 뒤 자동 삭제
- 카카오 리프레시 토큰은 Fernet 암호화, AI에는 한 줄 요청과 후보 목록만 보냄
- 방문 카운터는 날짜별 숫자만 저장(IP·쿠키·브라우저 정보 없음)

## 로드맵
- ✅ 1단계 무료 30일 체험 · ✅ 2단계 카카오 · ✅ 3단계 AI 한 줄 요청 · ✅ 주간 리포트 · ✅ 운영 지표
- 다음: 알림 시간 선택, 카카오톡 채널, 효도 구독·결제(사업자 정리 후)

## 문서
- 설계: [docs/superpowers/specs/](docs/superpowers/specs/) · 구현 계획: [docs/superpowers/plans/](docs/superpowers/plans/)
- 제출물(ERD·요구사항·API·와이어프레임·PPT 구성안·시연 대본): [docs/deliverables/](docs/deliverables/)

## 출처
- 통계: 질병관리청 국민건강영양조사 2022–2024
- 글꼴: Pretendard, 나눔고딕 (SIL Open Font License)
