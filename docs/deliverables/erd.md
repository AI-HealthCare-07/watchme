# ERD

- 기준: `app/models.py` (SQLAlchemy 2.0, 운영 PostgreSQL 16 / 로컬·테스트 SQLite)
- 표 생성: 앱 시작 시 `Base.metadata.create_all` (마이그레이션 도구 없음 → 2단계는 **새 표만 추가**, 기존 표 변경 없음)
- 개인 식별 정보(이름·연락처·이메일)는 어느 표에도 없어요. 체험은 추측 불가능한 토큰(`secrets.token_urlsafe(16)`, 22자)으로만 찾아요.

## 1. 구현된 표 (1단계, 배포 중)

```mermaid
erDiagram
    trials ||--o{ day_logs : "하루 기록 (최대 30)"
    trials ||--o{ week_decisions : "주차별 강도 결정 (최대 4)"

    trials {
        string token PK "개인 링크 /c/{token}, 랜덤 22자"
        datetime created_at "UTC"
        date start_date "KST 기준 시작일 = Day 1"
        string sex "M | F"
        int age "18~100"
        float height_cm "120~220"
        float weight_kg "30~250, 시작 몸무게"
        string plan_variant "normal | overweight | obese | high_risk"
        string diet_style "veg | meat | mixed (NULL=맞춤 질문 전)"
        string lunch_place "home | out | store"
        string breakfast "skip | light | full"
        int exercise_min "10 | 25 | 45"
        string free_days "자유 한 끼 요일 2개, 예: 2,5 (0=월)"
    }

    day_logs {
        string token PK, FK "trials.token, ON DELETE CASCADE"
        int day PK "1~30"
        bool kept "지켰어요 / 못 지켰어요"
        float weight_kg "선택, 30~250"
    }

    week_decisions {
        string token PK, FK "trials.token, ON DELETE CASCADE"
        int week PK "1~4 (7·14·21·28일째 요약)"
        int level "0~2, 다음 주부터 적용"
    }
```

| 표 | 역할 | 키·제약 |
|---|---|---|
| `trials` | 30일 체험 1건 = 몸 정보 + 맞춤 답변 5개 + 계획 종류 | PK `token`. `free_days`가 NULL이면 맞춤 질문 전(`setup_done = False`) |
| `day_logs` | 하루 체크 기록 | 복합 PK (`token`, `day`) → 같은 날 기록은 하나, 다시 누르면 덮어씀 |
| `week_decisions` | 주간 요약에서 고른 강도 | 복합 PK (`token`, `week`) → 주차마다 한 번만 결정 |

- 계획(식단·운동·팁)은 **표에 저장하지 않아요.** `build_plan(답변, 시작일, token 시드, 강도 결정)`으로 매번 같은 결과를 계산해요.
- 보관: 시작 후 120일(체험 30일 + 90일)이 지난 체험과 기록을 매일 삭제(`scripts/purge.py`).

## 2. 2단계 표 (카카오 로그인 + 하루 두 번 카톡) — ✅ 구현, 2026-11-17 운영 반영

출처: `docs/superpowers/specs/2026-11-16-watchme-phase2-design.md` 7장, `docs/superpowers/plans/2026-11-16-watchme-phase2.md` Task 3.

```mermaid
erDiagram
    kakao_accounts ||--o{ trial_owners : "계정 1개에 체험 여러 개"
    trials ||--o| trial_owners : "체험 1개는 계정 1개에만"
    kakao_accounts ||--o{ sent_messages : "발송 기록"
    trials ||--o| next_trials : "이전 체험"
    trials ||--o| next_trials : "다음 30일 체험"

    kakao_accounts {
        bigint kakao_id PK "카카오 회원번호만 저장"
        text refresh_token_enc "Fernet 암호문, NULL 가능"
        bool can_message "talk_message 동의 + 토큰 유효"
        bool notify "알림 켬/끔, 기본 켬"
        datetime created_at
    }

    trial_owners {
        string token PK, FK "trials.token, ON DELETE CASCADE"
        bigint kakao_id FK "kakao_accounts.kakao_id"
    }

    sent_messages {
        bigint kakao_id PK "kakao_accounts 계정"
        date day PK "KST 날짜"
        string kind PK "morning | evening | report | welcome"
    }

    next_trials {
        string token PK, FK "이전 체험, ON DELETE CASCADE"
        string next_token FK "새로 만든 체험"
    }

    trials {
        string token PK "1단계 표 그대로"
    }
```

| 표 | 역할 | 핵심 규칙 |
|---|---|---|
| `kakao_accounts` | 카카오 계정 | 닉네임·이메일 없음. 액세스 토큰은 저장 안 함(발송 때마다 리프레시 토큰으로 발급) |
| `trial_owners` | 체험 ↔ 계정 연결 | 다른 계정에 이미 연결된 체험은 거절 |
| `sent_messages` | 중복 발송 방지 | (계정, 날짜, 종류)를 **먼저 insert** → 이미 있으면 건너뜀. cron이 두 번 돌아도 한 통 |
| `next_trials` | "다음 30일 도전" 한 번만 | 같은 체험에서 두 번 눌러도 같은 새 체험으로 이동 |

- 연결 끊기: 카카오 unlink 호출(실패해도 진행) → `trial_owners`·`sent_messages`·`kakao_accounts` 행 삭제. 체험과 기록은 그대로.
- 보관 삭제 확장: 체험이 지워지면 연결도 지워지고, 남은 체험이 없는 계정은 계정 행과 발송 기록까지 삭제.
