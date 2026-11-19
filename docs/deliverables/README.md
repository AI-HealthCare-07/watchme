# Watchme 최종 프로젝트 제출물

OZ코딩스쿨 최종 프로젝트 제출 자료 모음이에요. 코드·설계 문서 기준으로 만들었고, 구현이 진행되면(2단계 카카오 ✅, 3단계 AI ✅) 함께 갱신해요.

| 제출물 | 파일 | 기준 |
|---|---|---|
| ERD | [erd.md](erd.md) · [erd.png](erd.png)(표 11개 한 장) | `app/models.py` |
| 요구사항 정의서 | [requirements.md](requirements.md) | `docs/superpowers/specs/` |
| API 명세서 | [api.md](api.md) | `app/routes.py`, `app/kakao_routes.py` |
| 와이어프레임 | [wireframes.md](wireframes.md) | `app/templates/`, 화면 캡처 18장 `screenshots/`(카톡 실제 메시지 포함) |
| 링크 | [links.md](links.md) | 배포 주소, GitHub, 문서, 발표 자료 |
| PPT 구성안 | [ppt-outline.md](ppt-outline.md) | 15장, 실제 사용자 숫자부터 (2026-11-19 다시 씀) |
| 시연영상 대본 | [demo-script.md](demo-script.md) | 약 4분 20초, AI 한 줄 요청·운영 지표 장면 포함 |
| README 목차 | [readme-outline.md](readme-outline.md) | 저장소 루트 `README.md`로 만듦 |

## 2단계 진행 상황 (✅ 완료, 2026-11-17 운영 반영)

| 2단계 계획 Task | 상태 | 갱신할 제출물 |
|---|---|---|
| 1·2 설정·카카오 HTTP 클라이언트 | ✅ | — |
| 3 새 표(`kakao_accounts`·`trial_owners`·`sent_messages`·`next_trials`) | ✅ | erd |
| 4 로그인 경로·환영 메시지·연결 카드 | ✅ | api, wireframes, requirements |
| 5 첫 배포·실험(알림 울리는지) | ✅ | demo-script, wireframes(메시지 문구) |
| 6 아침·저녁 발송 | ✅ | api(cron), requirements |
| 7 알림 끄기·연결 끊기 | ✅ | api, wireframes |
| 8 다음 30일 도전 | ✅ | api, wireframes, erd |
| 9 보관 삭제 확장·개인정보 안내 | ✅ | requirements, wireframes |
| 10 최종 배포·cron | ✅ | ppt-outline, links |

- 11/18 화면 개편(기록 화면 맨 위 카톡 바·칩·접는 위험도·주황 지난 날 띠, 시작·결과 화면 축약, 항상 밝은 화면)도 반영했어요.

## 3단계 진행 상황 (AI 한 줄 요청, ✅ 완료, 2026-11-18 운영 반영)

| 3단계 계획 Task | 상태 | 갱신할 제출물 |
|---|---|---|
| 2 Gemini 클라이언트(`app/ai.py`) | ✅ | — |
| 3 새 표 `ai_picks`·계획에 제외 반영 | ✅ | erd |
| 4 설정 화면 한 줄 요청·AI 호출 | ✅ | api, wireframes, requirements |
| 5 준비·기록 화면 안내·개인정보 문구·다음 도전 복사 | ✅ | wireframes, requirements |
| 6 runbook·배포·첫 실험 | ✅ | links, demo-script, ppt-outline |

- 랜딩 스토리형 개편·대표 아이콘(2026-11-18): wireframes ①, requirements FR-01·FR-01a 반영.
- 보완(2026-11-18): "내 계획 만들기"·시작 버튼 한 번만 제출, 동시에 두 번 보내도 오류 없음, AI 대기 전체 8초 제한.
- 주간 리포트·또래 비교(국민건강영양조사 걷기)·체중 그래프·자랑 카드·주간 카톡(2026-11-18): requirements FR-35~40, api #20·21, wireframes ⑧-2, demo-script 3:00.
- 운영 지표 `/admin`·랜딩 조회 카운터·카톡 발송 기록(2026-11-18): requirements FR-41~44, api #22, erd 4장, wireframes ⑧-3.
- 발표 준비 점검(2026-11-19): 오래된 문구 정리(erd 제목·표 11개, requirements 근거 문서·테스트 수, links 문서 목록·데이터 출처), PPT 구성안·시연 대본 다시 씀, 저장소 README 만듦. 와이어프레임 실제 캡처·카톡 화면, ERD 표 11개 한 장 이미지(`erd.png`) 추가.

## 직접 해야 할 것 (발표 전)
- [x] 제출용 공개 저장소 https://github.com/AI-HealthCare-07/watchme (2026-11-19, 가린 사본)
- [x] 화면 캡처 17장(2026-11-19, 로컬 예시 데이터) → `screenshots/`, 와이어프레임·README에 넣음
- [x] 카톡 '나와의 채팅' 실제 메시지 캡처(2026-11-19, 이름 잘라냄) → `screenshots/10-kakao-chat.png`
- [ ] 시연 영상 녹화 후 `links.md`에 주소 추가
- [ ] 발표 전날 `/admin` 숫자 캡처 → PPT 2·14장
- [x] PPT 초안 15장(2026-11-19, `ppt-outline.md` 기준, 발표자 노트 포함) → `links.md` 발표 자료. PPTX·PDF 내려받기는 슬라이드 화면에서
- [ ] PPT 빈칸 채우기: 2장 사용자 숫자·날짜, 8장 영상 링크, 14장 "숫자를 보고 고친 것"

- 데모 체험(`scripts/seed_demo.py`)도 운영 지표에서 빠지게 고침(2026-11-19).
- 마지막 갱신: 2026-11-19 (기준 커밋 `799834c`, main 배포, 테스트 350개 통과)
