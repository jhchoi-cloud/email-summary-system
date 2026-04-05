"""
GitHub Actions용 standalone 실행 스크립트
"""
import os
import json
from pathlib import Path
from email_summarizer import run_daily_summary

# 환경변수에서 config 로드 (GitHub Actions secrets)
config_file = Path(__file__).parent / 'config.json'
config = {}

if config_file.exists():
    with open(config_file) as f:
        config = json.load(f)

# 환경변수 우선 적용
if os.environ.get('ANTHROPIC_API_KEY'):
    config['anthropic_api_key'] = os.environ['ANTHROPIC_API_KEY']
if os.environ.get('TELEGRAM_BOT_TOKEN'):
    config['telegram_bot_token'] = os.environ['TELEGRAM_BOT_TOKEN']
if os.environ.get('TELEGRAM_CHAT_ID'):
    config['telegram_chat_id'] = os.environ['TELEGRAM_CHAT_ID']

# config.json 업데이트
with open(config_file, 'w') as f:
    json.dump(config, f)

# 실행
result = run_daily_summary()
print(f"상태: {result['status']}")
print(f"이메일 수: {result['email_count']}")
if result.get('error'):
    print(f"오류: {result['error']}")
    exit(1)
else:
    print("완료!")
