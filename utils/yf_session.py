"""
utils/yf_session.py
共通 requests.Session を提供。
Yahoo Finance はデータセンター IP からのリクエストを bot 判定してブロックするため、
ブラウザに偽装した User-Agent ヘッダーを付与することで回避する。
"""

import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

# モジュールレベルで1つのセッションを共有（接続再利用でも効率化）
YF_SESSION: requests.Session = requests.Session()
YF_SESSION.headers.update(_HEADERS)
