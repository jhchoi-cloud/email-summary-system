"""
Gmail 일일 요약 시스템 - Flask 웹 앱
- 웹 대시보드: http://localhost:5000
- 매일 오전 9시 자동 실행 (APScheduler)
- 수동 실행 API 제공
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from email_summarizer import run_daily_summary, load_config

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
HISTORY_FILE = BASE_DIR / 'history.json'

# 요약 실행 히스토리 (메모리 + 파일)
summary_history: list[dict] = []


def load_history() -> list[dict]:
    """히스토리 파일 로드"""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_history(history: list[dict]):
    """히스토리 파일 저장"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history[-30:], f, ensure_ascii=False, indent=2)  # 최근 30개만


def scheduled_job():
    """스케줄러가 실행하는 작업"""
    logger.info("스케줄 실행: Gmail 일일 요약 시작")
    result = run_daily_summary()
    summary_history.append(result)
    save_history(summary_history)
    logger.info(f"스케줄 완료: {result['status']} (이메일 {result['email_count']}개)")


# APScheduler 설정
scheduler = BackgroundScheduler(timezone='Asia/Seoul')
scheduler.add_job(
    scheduled_job,
    CronTrigger(hour=9, minute=0),  # 매일 오전 9시
    id='daily_summary',
    name='Gmail 일일 요약',
    replace_existing=True
)


# ──────────────────────────────────────────────
# 웹 라우트
# ──────────────────────────────────────────────

@app.route('/')
def dashboard():
    """메인 대시보드"""
    config = load_config()
    next_run = None
    job = scheduler.get_job('daily_summary')
    if job and job.next_run_time:
        next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')

    return render_template(
        'dashboard.html',
        history=list(reversed(summary_history[-10:])),
        next_run=next_run,
        config_status={
            'anthropic': bool(config.get('anthropic_api_key')),
            'telegram': bool(config.get('telegram_bot_token') and config.get('telegram_chat_id')),
            'gmail': (BASE_DIR / 'token.json').exists(),
        }
    )


@app.route('/api/run', methods=['POST'])
def api_run():
    """수동 실행 API"""
    logger.info("수동 실행 요청")
    result = run_daily_summary()
    summary_history.append(result)
    save_history(summary_history)
    return jsonify(result)


@app.route('/api/history')
def api_history():
    """히스토리 조회 API"""
    return jsonify(list(reversed(summary_history[-20:])))


@app.route('/api/status')
def api_status():
    """시스템 상태 API"""
    config = load_config()
    job = scheduler.get_job('daily_summary')
    next_run = None
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()

    return jsonify({
        'scheduler_running': scheduler.running,
        'next_run': next_run,
        'total_runs': len(summary_history),
        'last_run': summary_history[-1] if summary_history else None,
        'config': {
            'anthropic_configured': bool(config.get('anthropic_api_key')),
            'telegram_configured': bool(config.get('telegram_bot_token')),
            'gmail_authenticated': (BASE_DIR / 'token.json').exists(),
        }
    })


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """설정 조회/저장 API"""
    config_file = BASE_DIR / 'config.json'

    if request.method == 'POST':
        data = request.json or {}
        current = load_config()
        current.update({k: v for k, v in data.items() if v})  # 빈 값은 무시
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        return jsonify({'status': 'saved'})

    config = load_config()
    # API 키는 마스킹
    safe_config = {
        'anthropic_api_key': '****' if config.get('anthropic_api_key') else '',
        'telegram_bot_token': '****' if config.get('telegram_bot_token') else '',
        'telegram_chat_id': config.get('telegram_chat_id', ''),
    }
    return jsonify(safe_config)


if __name__ == '__main__':
    # 히스토리 로드
    summary_history.extend(load_history())

    # 스케줄러 시작
    scheduler.start()
    logger.info("스케줄러 시작 - 매일 오전 9시 자동 실행")

    print("\n" + "="*50)
    print("  Gmail 일일 요약 시스템 시작")
    print("  대시보드: http://localhost:5000")
    print("="*50 + "\n")

    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("서버 종료")
