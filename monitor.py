"""Cloud BTC alerts. Standard library only; USD prices from CoinGecko."""
import argparse
import json
import math
import os
from pathlib import Path
import smtplib
import ssl
import time
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from urllib.request import Request, urlopen

LEVELS = list(range(79000, 69999, -1000))
STATE = Path(os.environ.get('STATE_FILE', 'state.json'))
COINS = {'BTC': 'bitcoin', 'ETH': 'ethereum', 'ZAMA': 'zama'}


def required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ValueError(f'Missing configuration: {name}')
    return value


def prices():
    key = os.environ.get('COINGECKO_API_KEY', '').strip()
    req = Request(
        'https://api.coingecko.com/api/v3/simple/price?'
        'ids=bitcoin,ethereum,zama&vs_currencies=usd&include_last_updated_at=true',
        headers={**({'x-cg-demo-api-key': key} if key else {}),
                 'User-Agent': 'btc-cloud-monitor/1.0'})
    data = None
    for attempt in range(3):
        try:
            with urlopen(req, timeout=25) as response:
                data = json.load(response)
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    result = {}
    for symbol, coin in COINS.items():
        row = data.get(coin, {})
        value = row.get('usd')
        updated = row.get('last_updated_at', 0)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValueError(f'{symbol}: invalid or missing USD price')
        if not isinstance(updated, (int, float)) or not 0 <= time.time() - updated <= 900:
            raise ValueError(f'{symbol}: stale or missing quote timestamp')
        result[symbol] = {'usd': value, 'updated_at': updated}
    return result


def load_state():
    if not STATE.exists():
        return {'version': 1, 'previous': None, 'sent': [], 'pending': []}
    state = json.loads(STATE.read_text(encoding='utf-8'))
    if state.get('version') != 1 or not all(k in state for k in ('previous', 'sent', 'pending')):
        raise ValueError('Invalid state file; refusing to silently reset alerts')
    return state


def save_state(state):
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2), encoding='utf-8')
    temp.replace(STATE)


def observe(state, quote):
    """Baseline first sample; queue downward crossings, including skipped levels."""
    current = quote['BTC']['usd']
    previous = state['previous']
    queued = {item['level'] for item in state['pending']}
    if previous is not None:
        for level in LEVELS:
            if previous > level >= current and level not in state['sent'] and level not in queued:
                state['pending'].append({'level': level, 'quote': quote, 'observed_at': time.time()})
    state['previous'] = current


def local_time(timestamp):
    return datetime.fromtimestamp(timestamp, timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S UTC+8')


def send(quote, level=None, observed_at=None):
    sender = required('SMTP_USER')
    recipient = required('MAIL_TO')
    password = required('SMTP_PASSWORD')
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = ('BTC 价格监控测试' if level is None else f'BTC 跌破 ${level:,} 提醒')
    heading = '这是一封测试邮件。' if level is None else f'检测到 BTC 向下触及或跌破 ${level:,}。'
    lines = [heading, '', f'检测时间：{local_time(observed_at or time.time())}', '']
    for symbol, row in quote.items():
        digits = 6 if symbol == 'ZAMA' else 2
        lines.append(f'{symbol}：${row["usd"]:,.{digits}f} USD  （报价时间：{local_time(row["updated_at"])}）')
    lines += ['', '价格来源：CoinGecko；以上为触发时快照，发送重试时价格可能已变化。',
              '规则：BTC 79,000 至 70,000，每隔 1,000 美元；各价位只提醒一次。']
    msg.set_content('\n'.join(lines))
    with smtplib.SMTP_SSL('smtp.qq.com', 465, timeout=30, context=ssl.create_default_context()) as smtp:
        smtp.login(sender, password)
        refused = smtp.send_message(msg)
        if refused:
            raise RuntimeError('Recipient was refused')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Fetch prices only; no email/state mutation')
    parser.add_argument('--test-email', action='store_true', help='Send test; do not change alert state')
    args = parser.parse_args()
    if args.check or args.test_email:
        quote = prices()
        if args.test_email:
            send(quote)
            print('Test email accepted by SMTP server')
        else:
            print(json.dumps(quote, indent=2))
        return
    # Fail before mutating state if mail configuration is missing.
    for name in ('SMTP_USER', 'SMTP_PASSWORD', 'MAIL_TO'):
        required(name)
    state = load_state()
    fetch_error = None
    try:
        quote = prices()
        observe(state, quote)
        save_state(state)
        print(f'BTC USD: {quote["BTC"]["usd"]}; pending: {len(state["pending"])}')
    except Exception as exc:
        fetch_error = exc
        print('Quote fetch failed; attempting any previously queued mail')
    for item in list(state['pending']):
        send(item['quote'], item['level'], item['observed_at'])
        state['sent'].append(item['level'])
        state['pending'].remove(item)
        save_state(state)
        print(f'Alert accepted by SMTP server: {item["level"]}')
    if fetch_error:
        raise fetch_error


if __name__ == '__main__':
    main()
