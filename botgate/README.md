# BotGate

Red-DiscordBot v3.5+용 커스텀 Cog입니다. 서버에 들어오는 미승인 봇을 자동으로 킥하고, 로그 채널에 **서버 소유자 전용 승인 버튼**을 제공하여 허용 목록을 관리합니다.

## 기능 요약
- 미승인 봇 자동 킥 + 로그 임베드
- 소유자 전용 승인 버튼(수동 명령 허용도 지원)
- 승인 버튼 권한자(유저/역할) 커스텀 관리
- 승인된 봇 입장 시 자동 역할 부여(선택)
- OAuth2 초대 링크 자동 생성
- 길드별 설정/데이터 저장(Config, 멀티 서버 지원)

## 설치 방법
1) 레포 추가
```
[p]repo add botgate_repo https://github.com/<YOUR_GITHUB>/<YOUR_REPO>
```
2) 코그 설치
```
[p]cog install botgate_repo botgate
```
3) 코그 로드
```
[p]load botgate
```

## 필수 권한/인텐트 체크리스트
- Discord Developer Portal에서 **SERVER MEMBERS INTENT** ON
- Red 실행 인텐트에 `members` 활성화
- Red봇 권한:
  - `Kick Members` (미승인 봇 킥)
  - `View Channel`, `Send Messages`, `Embed Links` (로그 채널)
  - `Manage Roles` (승인된 봇 자동 역할 부여 시)
- 역할 계층: Red봇 역할이 대상 역할/봇보다 위에 있어야 합니다.

## 기본 사용 순서(권장)
1) `[p]botgate channel #log`
2) `[p]botgate setrole @ApprovedBot` (선택)
3) `[p]botgate toggle` 로 ON
5) (선택) 승인 버튼 권한자 추가(서버 소유자만)
   - `[p]botgate approver adduser @User`
   - `[p]botgate approver addrole @Role`

## 명령어
- `[p]botgate toggle` : 기능 ON/OFF
- `[p]botgate channel <#textchannel>` : 로그 채널 설정
- `[p]botgate setrole <@role | none>` : 승인된 봇 자동 역할 설정/해제
- `[p]botgate status` : 현재 설정 요약(embed)
- `[p]botgate allow <bot_id>` : 수동 허용
- `[p]botgate deny <bot_id>` : 수동 차단(허용 목록 제거)
- `[p]botgate approver adduser <@user>` : 승인 버튼 권한 유저 추가(서버 소유자만)
- `[p]botgate approver deluser <@user>` : 승인 버튼 권한 유저 삭제(서버 소유자만)
- `[p]botgate approver addrole <@role>` : 승인 버튼 권한 역할 추가(서버 소유자만)
- `[p]botgate approver delrole <@role>` : 승인 버튼 권한 역할 삭제(서버 소유자만)
- `[p]botgate approver list` : 승인 버튼 권한 목록 조회(서버 소유자만)
- `[p]botgate approver reset` : 승인 버튼 권한 초기화(서버 소유자만)
- `[p]botgate approver owneralways <true|false>` : 소유자 항상 허용 설정(서버 소유자만)

## OAuth2 초대 링크
- 초대 링크는 봇 ID만 포함하며 permissions 값은 사용하지 않습니다.
- OAuth2 링크 형식:
```
https://discord.com/oauth2/authorize?client_id=<BOT_ID>&permissions=0&integration_type=0&scope=bot
```

## 문제 해결
- 버튼이 안 눌림(재시작 후)
  - 로그 메시지가 남아 있다면 버튼은 재시작 후에도 복구되도록 처리되어 있습니다.
  - 그래도 동작하지 않으면 로그 임베드 하단의 안내대로 `[p]botgate allow <bot_id>`로 수동 승인하세요.
- 킥이 안 됨
  - `Kick Members` 권한, 역할 계층 확인
- 역할이 안 붙음
  - `Manage Roles` 권한 및 역할 계층 확인

## 주의사항
- 기본적으로 서버 소유자만 버튼 승인이 가능합니다.
- 서버 소유자만 approver를 추가/삭제/조회/초기화할 수 있습니다.
- 미승인 봇은 자동 킥 시도되며, 실패 시 사유를 로그로 남깁니다.
- 승인된 봇 입장 로그는 **입장 확인까지만** 남기며, 역할 부여 상세 로그는 남기지 않습니다.
