# Gmail 일일 요약 시스템

Gmail 이메일을 Claude AI로 자동 요약하고 Telegram으로 알림을 보내는 시스템입니다.

## 빠른 시작

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. Google Cloud Console 설정
1. https://console.cloud.google.com/ 접속
2. 새 프로젝트 생성
3. **Gmail API** 활성화
4. **OAuth 2.0 클라이언트 ID** 생성 (데스크톱 앱)
5. `credentials.json` 다운로드 → 이 폴더에 저장

### 3. 서버 실행
```bash
python app.py
```

### 4. 웹 대시보드에서 설정
http://localhost:5000 접속 후:
- **Anthropic API Key**: Claude API 키 입력
- **Telegram Bot Token**: @BotFather로 생성한 토큰 (선택)
- **Telegram Chat ID**: 알림 받을 채팅 ID (선택)

### 5. 첫 실행 - Google OAuth 인증
"지금 요약 실행" 버튼 클릭 시 브라우저가 열리며 Google 계정 인증 진행

## 파일 구조
```
email_summary_system/
├── app.py                  # Flask 웹 서버 + APScheduler
├── email_summarizer.py     # Gmail + Claude 요약 로직
├── templates/
│   └── dashboard.html      # 웹 대시보드
├── credentials.json        # Google OAuth 자격증명 (직접 추가)
├── token.json              # OAuth 토큰 (자동 생성)
├── config.json             # API 키 설정
├── history.json            # 실행 히스토리
└── requirements.txt        # 패키지 목록
```

## Telegram Chat ID 찾기
1. @userinfobot 에게 메시지 보내기
2. 또는 @getmyid_bot 사용
