"""
Gmail 이메일 요약 모듈
- Gmail API로 이메일 수집
- Claude API로 요약 생성
- Telegram으로 알림 전송
"""

import os
import json
import base64
import requests
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Gmail API 권한 범위
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# 설정 파일 경로
BASE_DIR = Path(__file__).parent
CREDENTIALS_FILE = BASE_DIR / 'credentials.json'
TOKEN_FILE = BASE_DIR / 'token.json'
CONFIG_FILE = BASE_DIR / 'config.json'


def load_config() -> dict:
    """설정 파일 로드"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def get_gmail_service():
    """Gmail API 서비스 객체 반환 (OAuth 인증 포함)"""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"credentials.json 파일이 없습니다.\n"
                    f"Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 생성하고\n"
                    f"{CREDENTIALS_FILE} 경로에 저장하세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def fetch_recent_emails(service, hours: int = 24, max_results: int = 50) -> list[dict]:
    """최근 N시간 이내 이메일 가져오기"""
    since_time = datetime.now() - timedelta(hours=hours)
    query = f'after:{int(since_time.timestamp())}'

    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=max_results
    ).execute()

    messages = results.get('messages', [])
    emails = []

    for msg_ref in messages:
        msg = service.users().messages().get(
            userId='me',
            id=msg_ref['id'],
            format='full'
        ).execute()

        email_data = parse_email(msg)
        emails.append(email_data)

    return emails


def parse_email(msg: dict) -> dict:
    """Gmail 메시지를 파싱하여 딕셔너리로 반환"""
    headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}

    subject = headers.get('Subject', '(제목 없음)')
    sender = headers.get('From', '(발신자 불명)')
    date = headers.get('Date', '')

    body = extract_body(msg['payload'])

    return {
        'id': msg['id'],
        'subject': subject,
        'sender': sender,
        'date': date,
        'body': body[:2000],  # 본문은 최대 2000자
        'snippet': msg.get('snippet', ''),
    }


def extract_body(payload: dict) -> str:
    """이메일 본문 추출 (멀티파트 지원)"""
    body = ''

    if payload.get('body', {}).get('data'):
        body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
    elif payload.get('parts'):
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
                body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                break
            elif part.get('mimeType') == 'text/html' and not body and part.get('body', {}).get('data'):
                body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')

    return body.strip()


def summarize_with_claude(emails: list[dict], api_key: str) -> str:
    """Claude API를 사용하여 이메일 목록 요약"""
    client = anthropic.Anthropic(api_key=api_key)

    if not emails:
        return "오늘 수신된 이메일이 없습니다."

    email_text = ""
    for i, email in enumerate(emails, 1):
        email_text += f"""
--- 이메일 {i} ---
발신자: {email['sender']}
제목: {email['subject']}
날짜: {email['date']}
내용 미리보기: {email['snippet']}
"""

    prompt = f"""다음은 오늘 수신된 이메일 목록입니다. 중요한 내용을 한국어로 간결하게 요약해주세요.

{email_text}

요약 형식:
1. 전체 이메일 수 및 주요 발신자
2. 중요/긴급 이메일 (있다면)
3. 카테고리별 분류 (업무, 광고, 뉴스레터 등)
4. 오늘 처리해야 할 액션 아이템 (있다면)

간결하고 실용적으로 요약해주세요."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


def send_telegram(token: str, chat_id: str, message: str) -> bool:
    """Telegram Bot API로 메시지 전송"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Telegram 전송 실패: {e}")
        return False


def run_daily_summary() -> dict:
    """일일 이메일 요약 실행 - 메인 함수"""
    config = load_config()
    result = {
        'timestamp': datetime.now().isoformat(),
        'status': 'running',
        'email_count': 0,
        'summary': '',
        'telegram_sent': False,
        'error': None
    }

    try:
        # Gmail 서비스 초기화
        service = get_gmail_service()

        # 이메일 수집 (최근 24시간)
        emails = fetch_recent_emails(service, hours=24)
        result['email_count'] = len(emails)

        # Claude로 요약
        anthropic_api_key = config.get('anthropic_api_key') or os.environ.get('ANTHROPIC_API_KEY', '')
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

        summary = summarize_with_claude(emails, anthropic_api_key)
        result['summary'] = summary

        # Telegram 전송
        telegram_token = config.get('telegram_bot_token') or os.environ.get('TELEGRAM_BOT_TOKEN', '')
        telegram_chat_id = config.get('telegram_chat_id') or os.environ.get('TELEGRAM_CHAT_ID', '')

        if telegram_token and telegram_chat_id:
            today = datetime.now().strftime('%Y년 %m월 %d일')
            telegram_message = f"📧 *{today} Gmail 일일 요약*\n\n총 {len(emails)}개 이메일\n\n{summary}"
            result['telegram_sent'] = send_telegram(telegram_token, telegram_chat_id, telegram_message)

        result['status'] = 'success'

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        print(f"오류 발생: {e}")

    return result
