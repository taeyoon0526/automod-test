# AutoModSeeder (Red-DiscordBot v3)

AutoMod 배지 테스트용으로, 현재 길드에 무작위 AutoMod 키워드 규칙을 생성/관리하는 Cog입니다.
규칙은 기본적으로 **비활성화(Disabled)** 상태로 생성되며, 실제 운영 방해를 최소화합니다.

## 주요 특징
- 명령어 1번으로 랜덤 AutoMod 규칙 생성(기본 10개)
- 이 Cog가 만든 규칙만 안전하게 목록/삭제
- 레이트리밋 완화 및 오류 분류 처리
- 재시작 후에도 Config에 rule_id 유지

## 권한 및 전제
- **명령어 사용 가능 계정**: `1173942304927645786`만 허용
- **봇 권한**: 서버 관리(Manage Guild) 필요
- **Intents**: `guilds`만 필요 (message_content 불필요)

## 명령어 목록
아래 모든 명령어는 **길드에서만 사용 가능**하며, 위 지정된 사용자만 실행할 수 있습니다.

### 1) 기본 생성
- **[p]automodseed** (별칭: **[p]amseed**)
  - 기본 설정으로 랜덤 AutoMod 규칙 10개 생성 시도
  - 기본값: `enabled=False`

### 2) 생성(명시형)
- **[p]automodseed create [count=10] [enabled=false]**
  - `count`: 1~10 범위 허용(10 초과 입력 시 10으로 clamp)
  - `enabled`: true/false, yes/no, on/off, 1/0 지원

### 3) 목록
- **[p]automodseed list**
  - 이 Cog가 만든 규칙 목록을 표시

### 4) 상태
- **[p]automodseed status**
  - Config에 저장된 rule_id 수 vs 실제 존재 수
  - 최근 실행 시각 표시

### 5) 정리
- **[p]automodseed purge**
  - 이 Cog가 만든 규칙만 전부 삭제
  - 다른 규칙은 절대 건드리지 않음

### 6) 설정(옵션)
- **[p]automodseed set mode <block|alert>**
  - action 모드 설정
  - alert 모드는 `allow_alert_mode=True`일 때만 허용

- **[p]automodseed set lockdenied <on|off>**
  - 권한 없는 사용자에게 무응답(silent) 처리 여부

## 동작 요약
- 랜덤 키워드: `amseed_{guild_id}_{random_hex}` 형태
- 규칙 생성 실패 시 가능한 만큼만 생성 후 요약 리포트 제공
- 레이트리밋(429)은 1회 백오프 후 재시도
- 삭제/생성 시 랜덤 sleep으로 레이트리밋 완화

## 설치 및 로드
```
[p]load automodseeder
[p]help automodseed
```

## 테스트 시나리오 예시
```
[p]automodseed
[p]automodseed create 10 false
[p]automodseed list
[p]automodseed status
[p]automodseed purge
```
