# REVERSE + TREND PRO — modified from your supplied AI.py.
# Requires Python 3.10+.
# Install: pip install "python-telegram-bot>=20,<23" aiohttp pytz colorama Pillow
# Run: BOT_TOKEN=<your-token> API_BASE_URL=<your-feed-url> python AI.py
# Set OWNER_ID in bot_config.json before exposing administrator functions.
# Feed schema: {"data":[{"time":"YYYY-MM-DD HH:MM:SS","open":1.0,
#   "high":1.1,"low":0.9,"close":1.05,"payout":80}]}
# time = candle OPEN time. Configure API_TIMEZONE for naive timestamps.
# Endpoint query parameters: Pair, Candle, Time=1m. No synthetic-data fallback.
# Existing users are migrated once to Reverse + Trend PRO and martingale OFF.
# Existing bot_config.json numeric values are retained; review cooldown/MTG limits.
# Signal/result images share the frozen pre-entry 60-candle price plot.
# Result footer shows entry-candle OHLC; this is NOT broker execution P&L.
# The process must remain running for automatic results. Snapshots are in RAM;
# restart recovery of an in-flight trade is not implemented.
# No profit/accuracy guarantee. Test with your feed and paper trading first.

import os
import sys
import json
import time
import asyncio
import logging
import math
import re
from urllib.parse import urlparse
import pytz
from datetime import datetime, timedelta, date
from io import BytesIO
from typing import Dict, List, Optional
import aiohttp

# Image processing
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ Pillow (PIL) not installed. Chart generation disabled.")

# Telegram PTB
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from colorama import Fore, Back, Style, init
init(autoreset=True)

# ================= Configuration =================
CONFIG_FILE = "bot_config.json"
USERS_FILE = "users.json"
USER_DATA_FILE = "users_data.json"
USER_STATS_FILE = "user_stats.json"

DEFAULT_CONFIG = {
    "TELEGRAM_BOT_TOKEN": "",  # Set BOT_TOKEN in Railway Variables
    "BOT_USERNAME": "@Mahabub_iX",
    "PARTIAL_RESULT_TIME_MIN": 50,
    "MAX_MTG_LEVEL": 0,
    "OWNER_ID": 6690775077,
    "ADMINS": [],
    "API_BASE_URL": "https://ravith-trading.up.railway.app",
    "API_CANDLE_COUNT": 240,
    "API_INTERVAL": "1m",
    "RISK_LEVEL": "medium",
    "AUTO_TRADE": True,
    "SIGNAL_COOLDOWN": 180,
    "MAX_DAILY_SIGNALS": 50,
    "SOUND_ALERT": True,
    "LANGUAGE": "en",
    "THEME": "dark",
    "NOTIFICATION_MODE": "all",
    "MARTINGALE_ENABLED": False,
    "PROFIT_TARGET": 0,
    "LOSS_LIMIT": 0,
    "SESSION_DURATION": 0,
    "TIMEZONE": "Asia/Dhaka",
    "CREDIT_MODE": False,
    "DAILY_FREE_CREDITS": 5,
    "API_TIMEZONE": "Asia/Dhaka",
    "MIN_ENTRY_LEAD_SECONDS": 12,
    "RESULT_TIMEOUT_SECONDS": 600,
    "SNAPSHOT_CACHE_LIMIT": 128,
    "MIN_ATR_RATIO": 0.00001,
}

CONFIG = {}
BOT_APPLICATION = None
USER_TRADING_SESSIONS = {}
USER_DATA = {}
USER_STATS = {}
USERS = {"allowed": [], "banned": [], "mode": "public"}

OWNER_ID = 6690775077
UTC_PLUS_6 = pytz.timezone('Asia/Dhaka')

# ================= UPDATED ASSET LIST =================
# OTC Currency Pairs (42)
OTC_CURRENCIES = [
    "AUDCAD_otc", "AUDCHF_otc", "AUDJPY_otc", "AUDNZD_otc", "AUDUSD_otc",
    "CADCHF_otc", "CADJPY_otc", "CHFJPY_otc", "EURAUD_otc", "EURCAD_otc",
    "EURCHF_otc", "EURGBP_otc", "EURJPY_otc", "EURNZD_otc", "EURSGD_otc",
    "EURUSD_otc", "GBPAUD_otc", "GBPCAD_otc", "GBPCHF_otc", "GBPJPY_otc",
    "GBPNZD_otc", "GBPUSD_otc", "NZDCAD_otc", "NZDCHF_otc", "NZDJPY_otc",
    "NZDUSD_otc", "USDARS_otc", "USDBDT_otc", "USDCAD_otc", "USDCHF_otc",
    "USDCOP_otc", "USDDZD_otc", "USDEGP_otc", "USDIDR_otc", "USDINR_otc",
    "USDJPY_otc", "USDMXN_otc", "USDNGN_otc", "USDPHP_otc", "USDPKR_otc",
    "USDTRY_otc", "USDZAR_otc"
]
# OTC Commodities
OTC_COMMODITIES = ["UKBrent_otc", "USCrude_otc", "XAGUSD_otc", "XAUUSD_otc"]
# OTC Crypto
OTC_CRYPTO = [
    "ADAUSD_otc", "APTUSD_otc", "ARBUSD_otc", "ATOUSD_otc", "AVAUSD_otc",
    "AXSUSD_otc", "BCHUSD_otc", "BNBUSD_otc", "BONUSD_otc", "BTCUSD_otc",
    "DASUSD_otc", "DOGUSD_otc", "DOTUSD_otc", "ETCUSD_otc", "ETHUSD_otc",
    "FLOUSD_otc", "GALUSD_otc", "HMSUSD_otc", "LINUSD_otc", "LTCUSD_otc",
    "MELUSD_otc", "SHIUSD_otc", "SOLUSD_otc", "TIAUSD_otc", "TONUSD_otc",
    "TRUUSD_otc", "TRXUSD_otc", "WIFUSD_otc", "XRPUSD_otc", "ZECUSD_otc"
]
# Real Currency Pairs (without _otc)
REAL_CURRENCIES = [
    "AUDCAD", "AUDCHF", "AUDJPY", "AUDUSD", "CADJPY", "CHFJPY",
    "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
    "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPUSD",
    "USDCAD", "USDCHF", "USDJPY"
]

ASSETS = OTC_CURRENCIES + OTC_COMMODITIES + OTC_CRYPTO + REAL_CURRENCIES

# ================= FANCY FONT SYSTEM =================
def ff(text):
    """Convert text to fancy monospace Unicode font"""
    mapping = {
        'A':'𝙰','B':'𝙱','C':'𝙲','D':'𝙳','E':'𝙴','F':'𝙵','G':'𝙶','H':'𝙷','I':'𝙸','J':'𝙹',
        'K':'𝙺','L':'𝙻','M':'𝙼','N':'𝙽','O':'𝙾','P':'𝙿','Q':'𝚀','R':'𝚁','S':'𝚂','T':'𝚃',
        'U':'𝚄','V':'𝚅','W':'𝚆','X':'𝚇','Y':'𝚈','Z':'𝚉',
        'a':'𝚊','b':'𝚋','c':'𝚌','d':'𝚍','e':'𝚎','f':'𝚏','g':'𝚐','h':'𝚑','i':'𝚒','j':'𝚓',
        'k':'𝚔','l':'𝚕','m':'𝚖','n':'𝚗','o':'𝚘','p':'𝚙','q':'𝚚','r':'𝚛','s':'𝚜','t':'𝚝',
        'u':'𝚞','v':'𝚟','w':'𝚠','x':'𝚡','y':'𝚢','z':'𝚣',
        '0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿',
        ':':'：','.':'．','%':'٪','/':'╱','-':'—','_':'＿','+':'＋','=':'＝',
        '(':'❨',')':'❩','[':'⦋',']':'⦌','{':'❴','}':'❵',
        '!':'❕','?':'❓','@':'﹫','#':'﹟','$':'﹩','&':'﹠','*':'﹡',
        '<':'❮','>':'❯',',':'，',';':'；',"'":'ʼ','"':'ˮ',
        ' ':' '
    }
    return "".join(mapping.get(c, c) for c in text)

def fn(num_str):
    """Convert number string to fancy font"""
    result = []
    for c in str(num_str):
        if c == '.':
            result.append('．')
        elif c == '%':
            result.append('٪')
        elif c == '+':
            result.append('＋')
        elif c == '-':
            result.append('—')
        elif c == ',':
            result.append('，')
        elif c == ':':
            result.append('：')
        else:
            mapping = {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿'}
            result.append(mapping.get(c, c))
    return ''.join(result)

def fb(text):
    """Convert text to bold fancy Unicode"""
    mapping = {
        'A':'𝗔','B':'𝗕','C':'𝗖','D':'𝗗','E':'𝗘','F':'𝗙','G':'𝗚','H':'𝗛','I':'𝗜','J':'𝗝',
        'K':'𝗞','L':'𝗟','M':'𝗠','N':'𝗡','O':'𝗢','P':'𝗣','Q':'𝗤','R':'𝗥','S':'𝗦','T':'𝗧',
        'U':'𝗨','V':'𝗩','W':'𝗪','X':'𝗫','Y':'𝗬','Z':'𝗭',
        'a':'𝗮','b':'𝗯','c':'𝗰','d':'𝗱','e':'𝗲','f':'𝗳','g':'𝗴','h':'𝗵','i':'𝗶','j':'𝗷',
        'k':'𝗸','l':'𝗹','m':'𝗺','n':'𝗻','o':'𝗼','p':'𝗽','q':'𝗾','r':'𝗿','s':'𝘀','t':'𝘁',
        'u':'𝘂','v':'𝘃','w':'𝘄','x':'𝘅','y':'𝘆','z':'𝘇',
        '0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',
        ' ':' '
    }
    return "".join(mapping.get(c, c) for c in text)

def fi(text):
    """Convert text to italic fancy Unicode"""
    mapping = {
        'A':'𝘈','B':'𝘉','C':'𝘊','D':'𝘋','E':'𝘌','F':'𝘍','G':'𝘎','H':'𝘏','I':'𝘐','J':'𝘑',
        'K':'𝘒','L':'𝘓','M':'𝘔','N':'𝘕','O':'𝘖','P':'𝘗','Q':'𝘘','R':'𝘙','S':'𝘚','T':'𝘛',
        'U':'𝘜','V':'𝘝','W':'𝘞','X':'𝘟','Y':'𝘠','Z':'𝘡',
        'a':'𝘢','b':'𝘣','c':'𝘤','d':'𝘥','e':'𝘦','f':'𝘧','g':'𝘨','h':'𝘩','i':'𝘪','j':'𝘫',
        'k':'𝘬','l':'𝘭','m':'𝘮','n':'𝘯','o':'𝘰','p':'𝘱','q':'𝘲','r':'𝘳','s':'𝘴','t':'𝘵',
        'u':'𝘶','v':'𝘷','w':'𝘸','x':'𝘹','y':'𝘺','z':'𝘻',
        ' ':' '
    }
    return "".join(mapping.get(c, c) for c in text)

def fancy_asset_name(asset_raw):
    base = asset_raw.replace('_otc', '').replace('-OTC', '').replace('-otc', '').upper()
    fancy_base = ff(base)
    if '_otc' in asset_raw.lower() or '-otc' in asset_raw.lower() or 'OTC' in asset_raw.upper():
        return f"{fancy_base}⁻𝙾𝚃𝙲"
    return fancy_base

def fancy_time(time_str):
    result = []
    num_map = {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿'}
    for c in time_str:
        if c == ':':
            result.append('⁚')
        elif c in num_map:
            result.append(num_map[c])
        else:
            result.append(c)
    return ''.join(result)

def fancy_direction(direction):
    d = direction.upper().strip()
    if d in ('BUY', 'CALL'):
        return ff('BUY')
    elif d in ('PUT', 'SELL'):
        return ff('PUT')
    return ff(d)

# ================= Config & Data Load/Save =================
def load_config():
    global CONFIG
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                CONFIG = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                CONFIG.setdefault(k, v)
        else:
            CONFIG = DEFAULT_CONFIG.copy()
            save_config()
    except:
        CONFIG = DEFAULT_CONFIG.copy()

def save_config():
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(CONFIG, f, indent=2)
        return True
    except:
        return False

def load_users():
    global USERS
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                USERS = json.load(f)
            USERS.setdefault("allowed", [])
            USERS.setdefault("banned", [])
            USERS.setdefault("mode", "public")
        else:
            USERS = {"allowed": [], "banned": [], "mode": "public"}
            save_users()
    except:
        USERS = {"allowed": [], "banned": [], "mode": "public"}

def save_users():
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(USERS, f, indent=2)
        return True
    except:
        return False

def load_user_data():
    global USER_DATA
    try:
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                USER_DATA = json.load(f)
        else:
            USER_DATA = {}
            save_user_data()
    except:
        USER_DATA = {}

def save_user_data():
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(USER_DATA, f, indent=2)
        return True
    except:
        return False

def load_user_stats():
    global USER_STATS
    try:
        if os.path.exists(USER_STATS_FILE):
            with open(USER_STATS_FILE, 'r', encoding='utf-8') as f:
                USER_STATS = json.load(f)
        else:
            USER_STATS = {}
            save_user_stats()
    except:
        USER_STATS = {}

def save_user_stats():
    try:
        with open(USER_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(USER_STATS, f, indent=2)
        return True
    except:
        return False

def get_user_stats(user_id):
    uid = str(user_id)
    if uid not in USER_STATS:
        USER_STATS[uid] = {"win": 0, "loss": 0, "all_results": [], "pair_wins": 0, "pair_losses": 0, "streak": 0, "best_streak": 0, "total_payout": 0.0}
        save_user_stats()
    else:
        USER_STATS[uid].setdefault("pair_wins", 0)
        USER_STATS[uid].setdefault("pair_losses", 0)
        USER_STATS[uid].setdefault("streak", 0)
        USER_STATS[uid].setdefault("best_streak", 0)
        USER_STATS[uid].setdefault("total_payout", 0.0)
    return USER_STATS[uid]

def update_user_activity(user_id, username=None):
    now = datetime.now(UTC_PLUS_6).isoformat()
    uid = str(user_id)
    if uid not in USER_DATA:
        USER_DATA[uid] = {
            "last_active": now,
            "first_seen": now,
            "commands": 0,
            "chat_id": "",
            "telegram_enabled": False,
            "username": username or "",
            "signals_received": 0,
            "credits": CONFIG.get("DAILY_FREE_CREDITS", 5),
            "last_credit_date": date.today().isoformat(),
            "settings": {
                "watermark": "RAVITH AI PRO",
                "contact": CONFIG.get("BOT_USERNAME", "@Mahabub_iX"),
                "risk_level": "medium",
                "signal_type": "all",
                "chart_style": "pro",
                "sound_alert": True,
                "auto_result": True,
                "show_payout": True,
                "martingale": False,
                "language": "en",
                "timezone": "Asia/Dhaka",
                "preferred_assets": [],
                "blocked_assets": [],
                "min_payout": 0,
                "notification_mode": "all",
                "strategy": "REVERSE_TREND_PRO", "pro_engine_version": 1,            # new
                "footer_text": "RAVITH AI PRO"        # new
            }
        }
    else:
        USER_DATA[uid]["last_active"] = now
        USER_DATA[uid]["commands"] = USER_DATA[uid].get("commands", 0) + 1
        if username:
            USER_DATA[uid]["username"] = username
        USER_DATA[uid].setdefault("first_seen", now)
        USER_DATA[uid].setdefault("signals_received", 0)
        USER_DATA[uid].setdefault("credits", CONFIG.get("DAILY_FREE_CREDITS", 5))
        USER_DATA[uid].setdefault("last_credit_date", date.today().isoformat())
        settings = USER_DATA[uid].setdefault("settings", {})
        settings.setdefault("watermark", "RAVITH AI PRO")
        settings.setdefault("contact", CONFIG.get("BOT_USERNAME", "@Mahabub_iX"))
        settings.setdefault("risk_level", "medium")
        settings.setdefault("signal_type", "all")
        settings.setdefault("chart_style", "pro")
        settings.setdefault("sound_alert", True)
        settings.setdefault("auto_result", True)
        settings.setdefault("show_payout", True)
        settings.setdefault("martingale", False)
        settings.setdefault("language", "en")
        settings.setdefault("timezone", "Asia/Dhaka")
        settings.setdefault("preferred_assets", [])
        settings.setdefault("blocked_assets", [])
        settings.setdefault("min_payout", 0)
        settings.setdefault("notification_mode", "all")
        settings.setdefault("strategy", "REVERSE_TREND_PRO")
        settings.setdefault("footer_text", "RAVITH AI PRO")
    save_user_data()

def is_authorized(user_id):
    if user_id == OWNER_ID or user_id in CONFIG.get("ADMINS", []):
        return True
    if USERS.get("mode") == "public":
        return user_id not in USERS.get("banned", [])
    else:
        return user_id in USERS.get("allowed", []) and user_id not in USERS.get("banned", [])

def is_admin(user_id):
    return user_id == OWNER_ID or user_id in CONFIG.get("ADMINS", [])

def is_owner(user_id):
    return user_id == OWNER_ID

# ================= Credit System =================
def reset_credits_if_needed(user_id):
    if not CONFIG.get("CREDIT_MODE", False):
        return
    uid = str(user_id)
    if uid not in USER_DATA:
        return
    user_data = USER_DATA[uid]
    if user_id in USERS.get("allowed", []) or is_admin(user_id):
        user_data["credits"] = 999999
        user_data["last_credit_date"] = date.today().isoformat()
        save_user_data()
        return
    today = date.today().isoformat()
    if user_data.get("last_credit_date") != today:
        user_data["credits"] = CONFIG.get("DAILY_FREE_CREDITS", 5)
        user_data["last_credit_date"] = today
        save_user_data()

def get_user_credits(user_id):
    reset_credits_if_needed(user_id)
    uid = str(user_id)
    if uid in USER_DATA:
        return USER_DATA[uid].get("credits", 0)
    return 0

def deduct_credit(user_id, amount=1):
    if not CONFIG.get("CREDIT_MODE", False):
        return True
    uid = str(user_id)
    reset_credits_if_needed(user_id)
    if uid not in USER_DATA:
        return False
    if user_id in USERS.get("allowed", []) or is_admin(user_id):
        return True
    credits = USER_DATA[uid].get("credits", 0)
    if credits >= amount:
        USER_DATA[uid]["credits"] = credits - amount
        save_user_data()
        return True
    else:
        return False

def get_credits_message(user_id):
    if not CONFIG.get("CREDIT_MODE", False):
        return f"💳 {ff('Unlimited')}"
    uid = str(user_id)
    if user_id in USERS.get("allowed", []) or is_admin(user_id):
        return f"💳 {ff('Unlimited')}"
    credits = get_user_credits(user_id)
    daily = CONFIG.get("DAILY_FREE_CREDITS", 5)
    return f"💳 {fn(str(credits))}/{fn(str(daily))}"

# ================= Utilities =================
def get_current_time():
    return datetime.now(UTC_PLUS_6)

def round_to_minute(dt):
    return dt.replace(second=0, microsecond=0)

def get_next_minute(dt):
    return dt + timedelta(minutes=1)

def timestamp_to_dhaka_time(ts):
    return datetime.fromtimestamp(ts, UTC_PLUS_6)

def ts_to_dt(ts):
    if ts is None:
        return None
    try:
        ts = int(ts)
        if ts > 1_000_000_000_000:
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=pytz.utc).astimezone(UTC_PLUS_6)
    except:
        try:
            dt = datetime.fromisoformat(str(ts))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pytz.utc)
            return dt.astimezone(UTC_PLUS_6)
        except:
            return None

# ================= API Data Fetching =================

async def get_candles(asset: str, count: int = None, interval: str = None) -> Optional[List[Dict]]:
    return await fetch_candles_from_api(asset, count, interval)

# ================= Indicator Functions =================
def compute_sma(closes, period):
    if len(closes) < period: return [None] * len(closes)
    sma = [None] * (period - 1)
    for i in range(period, len(closes) + 1):
        sma.append(sum(closes[i-period:i]) / period)
    return sma

def compute_ema(closes, period):
    if len(closes) < period: return [None] * len(closes)
    ema = []
    s = sum(closes[:period]) / period
    ema.append(s)
    multiplier = 2 / (period + 1)
    for price in closes[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return [None] * (period - 1) + ema


def compute_macd(closes, fast=12, slow=26, signal=9):
    ema_fast = compute_ema(closes, fast)
    ema_slow = compute_ema(closes, slow)
    macd_line = [f - s if f is not None and s is not None else None for f, s in zip(ema_fast, ema_slow)]
    valid_macd = [m for m in macd_line if m is not None]
    if len(valid_macd) < signal:
        return macd_line, [None]*len(macd_line), [None]*len(macd_line)
    signal_line = compute_ema(valid_macd, signal)
    full_signal = [None] * (len(macd_line) - len(signal_line)) + signal_line
    histogram = [m - s if m is not None and s is not None else None for m, s in zip(macd_line, full_signal)]
    return macd_line, full_signal, histogram

def compute_stochastic(closes, highs, lows, period=14, k_smooth=3, d_smooth=3):
    k_values = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        high_window = max(highs[i-period+1:i+1])
        low_window = min(lows[i-period+1:i+1])
        if high_window != low_window:
            k_values[i] = 100 * (closes[i] - low_window) / (high_window - low_window)
    k_smooth_vals = [None] * len(k_values)
    for i in range(len(k_values)):
        if i >= k_smooth - 1:
            valid = [v for v in k_values[i-k_smooth+1:i+1] if v is not None]
            if valid: k_smooth_vals[i] = sum(valid) / len(valid)
    d_values = [None] * len(k_smooth_vals)
    for i in range(d_smooth - 1, len(k_smooth_vals)):
        valid = [v for v in k_smooth_vals[i-d_smooth+1:i+1] if v is not None]
        if valid: d_values[i] = sum(valid) / len(valid)
    return k_smooth_vals, d_values

def compute_williams_r(highs, lows, closes, period=14):
    wr = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        hh = max(highs[i-period+1:i+1])
        ll = min(lows[i-period+1:i+1])
        if hh != ll:
            wr[i] = (hh - closes[i]) / (hh - ll) * -100
    return wr

def compute_cci(highs, lows, closes, period=20):
    cci = [None] * len(closes)
    tp = [(h+l+c)/3 for h, l, c in zip(highs, lows, closes)]
    sma_tp = compute_sma(tp, period)
    for i in range(period - 1, len(closes)):
        if sma_tp[i] is not None:
            mean_dev = sum(abs(tp[j] - sma_tp[i]) for j in range(i-period+1, i+1)) / period
            if mean_dev != 0:
                cci[i] = (tp[i] - sma_tp[i]) / (0.015 * mean_dev)
    return cci

# ================= FUTURE CHECKER PARSER (unchanged) =================
def parse_pasted_signals(text: str) -> List[Dict]:
    reverse_mono = {}
    mono_upper = {
        '𝙰':'A','𝙱':'B','𝙲':'C','𝙳':'D','𝙴':'E','𝙵':'F','𝙶':'G','𝙷':'H','𝙸':'I','𝙹':'J',
        '𝙺':'K','𝙻':'L','𝙼':'M','𝙽':'N','𝙾':'O','𝙿':'P','𝚀':'Q','𝚁':'R','𝚂':'S','𝚃':'T',
        '𝚄':'U','𝚅':'V','𝚆':'W','𝚇':'X','𝚈':'Y','𝚉':'Z'
    }
    mono_lower = {
        '𝚊':'a','𝚋':'b','𝚌':'c','𝚍':'d','𝚎':'e','𝚏':'f','𝚐':'g','𝚑':'h','𝚒':'i','𝚓':'j',
        '𝚔':'k','𝚕':'l','𝚖':'m','𝚗':'n','𝚘':'o','𝚙':'p','𝚚':'q','𝚛':'r','𝚜':'s','𝚝':'t',
        '𝚞':'u','𝚟':'v','𝚠':'w','𝚡':'x','𝚢':'y','𝚣':'z'
    }
    mono_nums = {
        '𝟶':'0','𝟷':'1','𝟸':'2','𝟹':'3','𝟺':'4','𝟻':'5','𝟼':'6','𝟽':'7','𝟾':'8','𝟿':'9'
    }
    reverse_mono.update(mono_upper)
    reverse_mono.update(mono_lower)
    reverse_mono.update(mono_nums)
    reverse_mono['⁚'] = ':'
    reverse_mono['⁻'] = '-'
    reverse_mono['：'] = ':'
    reverse_mono['．'] = '.'
    reverse_mono['—'] = '-'
    reverse_mono['–'] = '-'
    reverse_mono['⇨'] = '-'
    reverse_mono['➔'] = '-'
    reverse_mono['➡'] = '-'
    reverse_mono['→'] = '-'
    reverse_mono['⟩'] = '-'

    def defancy(s):
        result = []
        for ch in s:
            if ch in reverse_mono:
                result.append(reverse_mono[ch])
            else:
                result.append(ch)
        return ''.join(result)

    signals = []
    lines = text.strip().split('\n')

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        plain_tmp = defancy(line)
        tokens = re.split(r'[;\s,|]+', plain_tmp.strip())
        tokens = [t for t in tokens if t]
        if len(tokens) < 3:
            continue

        plain = defancy(line)
        plain = re.sub(r'^[⧉•\-\s]+', '', plain).strip()
        plain = re.sub(r'\s+', ' ', plain)
        for delim in [';', ',', '|', '\t']:
            plain = plain.replace(delim, ' ')
        plain = re.sub(r'\s+', ' ', plain)

        time_match = re.search(r'(\d{1,2}:\d{2})', plain)
        time_str = time_match.group(1) if time_match else None

        dir_match = re.search(r'\b(BUY|SELL|CALL|PUT)\b', plain, re.IGNORECASE)
        direction = dir_match.group(1).upper() if dir_match else None
        if direction in ('BUY', 'CALL'):
            direction = 'CALL'
        elif direction in ('SELL', 'PUT'):
            direction = 'PUT'

        if time_match and dir_match:
            asset_candidates = re.sub(r'\b(BUY|SELL|CALL|PUT)\b', '', plain, flags=re.IGNORECASE)
            asset_candidates = re.sub(r'\d{1,2}:\d{2}', '', asset_candidates)
            asset_candidates = re.sub(r'[^\w\s]', ' ', asset_candidates)
            asset_candidates = re.sub(r'\s+', ' ', asset_candidates).strip()

            tokens = asset_candidates.split()
            asset_str = None
            for token in tokens:
                clean_token = re.sub(r'[-_]OTC', '', token, flags=re.IGNORECASE)
                if len(clean_token) >= 6 and clean_token.isalpha():
                    asset_str = clean_token.upper()
                    break
            if not asset_str:
                if tokens:
                    asset_str = re.sub(r'[-_]OTC', '', tokens[0], flags=re.IGNORECASE).upper()
                else:
                    asset_str = None

            if asset_str:
                if 'OTC' in plain.upper():
                    asset_api = f"{asset_str}_otc"
                else:
                    asset_api = asset_str
                signals.append({
                    'asset': asset_api,
                    'time': time_str,
                    'direction': direction,
                    'asset_display': asset_str
                })

    return signals

# ================= CHECK SIGNAL RESULT (unchanged) =================

# ================= BEAUTIFUL TELEGRAM UI (modified for new settings) =================
def get_user_chat_id(user_id: int) -> int:
    uid = str(user_id)
    user_data = USER_DATA.get(uid, {})
    if user_data.get('telegram_enabled', False) and user_data.get('chat_id'):
        try:
            return int(user_data['chat_id'])
        except ValueError:
            pass
    return user_id

def get_welcome_message(user, is_admin_user=False, is_owner_user=False):
    name = user.first_name or "User"
    username = f"@{user.username}" if user.username else ff("Unknown")
    now = get_current_time()
    date_str = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H:%M:%S")

    hour = now.hour
    if 5 <= hour < 12:
        greeting = "🌅 𝙶𝚘𝚘𝚍 𝙼𝚘𝚛𝚗𝚒𝚗𝚐"
    elif 12 <= hour < 17:
        greeting = "☀️ 𝙶𝚘𝚘𝚍 𝙰𝚏𝚝𝚎𝚛𝚗𝚘𝚘𝚗"
    elif 17 <= hour < 21:
        greeting = "🌆 𝙶𝚘𝚘𝚍 𝙴𝚟𝚎𝚗𝚒𝚗𝚐"
    else:
        greeting = "🌙 𝙶𝚘𝚘𝚍 𝙽𝚒𝚐𝚑𝚝"

    role = "👑 𝙾𝚆𝙽𝙴𝚁" if is_owner_user else ("⚡ 𝙰𝙳𝙼𝙸𝙽" if is_admin_user else "👤 𝚄𝚂𝙴𝚁")
    mode = ff(USERS.get('mode', 'public').upper())
    total_users = len(USER_DATA)
    active_bots = sum(1 for s in USER_TRADING_SESSIONS.values() if s.get('active'))

    stats = get_user_stats(user.id)
    wins = stats.get('win', 0)
    losses = stats.get('loss', 0)
    total = wins + losses
    acc = (wins / total * 100) if total > 0 else 0
    streak = stats.get('best_streak', 0)

    credits_line = get_credits_message(user.id)

    msg = f"""
╔═══════════════════════════════════╗
║  ✦  𝗥𝗔𝗩𝗜𝗧𝗛  𝗔𝗜  𝗣𝗥𝗢  𝗧𝗥𝗔𝗗𝗜𝗡𝗚  ✦  ║
║     ═══════════════════════       ║
║    🤖 𝙰𝙸 𝙿𝚘𝚠𝚎𝚛𝚎𝚍 𝚃𝚛𝚊𝚍𝚒𝚗𝚐 𝙱𝚘𝚝    ║
╚═══════════════════════════════════╝

{greeting}，{name}！

╭━━━━━━━━【👤】━━━━━━━━╮
│  🆔 𝙸𝙳：{fn(str(user.id))}
│  📛 𝙽𝚊𝚖𝚎：{name}
│  🏷️ 𝚄𝚜𝚎𝚛：{username}
│  🎭 𝚁𝚘𝚕𝚎：{role}
│  📅 𝙳𝚊𝚝𝚎：{fn(date_str)}
│  🕐 𝚃𝚒𝚖𝚎：{fn(time_str)} 𝙱𝙳𝚃
│  {credits_line}
╰━━━━━━━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━━【📊】━━━━━━━━╮
│  🏆 𝚆𝚒𝚗𝚜：{fn(str(wins))}
│  💔 𝙻𝚘𝚜𝚜𝚎𝚜：{fn(str(losses))}
│  🎯 𝙰𝚌𝚌𝚞𝚛𝚊𝚌𝚢：{fn(f"{acc:.1f}")}٪
│  🔥 𝙱𝚎𝚜𝚝 𝚂𝚝𝚛𝚎𝚊𝚔：{fn(str(streak))}
╰━━━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━━【🌐】━━━━━━━━╮
│  📡 𝙼𝚘𝚍𝚎：{mode}
│  👥 𝚄𝚜𝚎𝚛𝚜：{fn(str(total_users))}
│  🤖 𝙰𝚌𝚝𝚒𝚟𝚎 𝙱𝚘𝚝𝚜：{fn(str(active_bots))}
│  📈 𝙰𝚜𝚜𝚎𝚝𝚜：{fn(str(len(ASSETS)))} 𝙿𝚊𝚒𝚛𝚜
╰━━━━━━━━━━━━━━━━━━━━━╯

━━━━━━━━━━━━━━━━━━━━━━━━━━
   ⚡ {ff("Select an option below")} ⚡
━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    return msg





def get_admin_panel_keyboard(user_id):
    is_own = is_owner(user_id)
    mode = USERS.get('mode', 'public')
    mode_icon = "🌐" if mode == "public" else "??"
    mode_text = ff(mode.upper())
    credit_mode = CONFIG.get("CREDIT_MODE", False)
    credit_icon = "✅" if credit_mode else "❌"
    daily_credits = CONFIG.get("DAILY_FREE_CREDITS", 5)

    keyboard = [
        [InlineKeyboardButton(f"━━━━━ 👑 𝙰𝙳𝙼𝙸𝙽 𝙿𝙰𝙽𝙴𝙻 ━━━━━", callback_data="noop")],
        [InlineKeyboardButton(f"━━━ 👥 𝚄𝚂𝙴𝚁 𝙼𝙰𝙽𝙰𝙶𝙴𝙼𝙴𝙽𝚃 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"➕ 𝙰𝙳𝙳 𝚄𝚂𝙴𝚁", callback_data="add_user"),
         InlineKeyboardButton(f"➖ 𝚁𝙴𝙼𝙾𝚅𝙴 𝚄𝚂𝙴𝚁", callback_data="rem_user")],
        [InlineKeyboardButton(f"🚫 𝙱𝙰𝙽 𝚄𝚂𝙴𝚁", callback_data="ban_user"),
         InlineKeyboardButton(f"✅ 𝚄𝙽𝙱𝙰𝙽 𝚄𝚂𝙴𝚁", callback_data="unban_user")],
        [InlineKeyboardButton(f"📋 𝙻𝙸𝚂𝚃 𝚄𝚂𝙴𝚁𝚂", callback_data="list_users"),
         InlineKeyboardButton(f"🚫 𝙱𝙰𝙽 𝙻𝙸𝚂𝚃", callback_data="ban_list")],
        [InlineKeyboardButton(f"👥 𝚄𝚂𝙴𝚁 𝙰𝙲𝚃𝙸𝚅𝙸𝚃𝚈", callback_data="user_activity"),
         InlineKeyboardButton(f"🔍 𝚂𝙴𝙰𝚁𝙲𝙷 𝚄𝚂𝙴𝚁", callback_data="search_user")],
        [InlineKeyboardButton(f"━━━ 🔐 𝙰𝙲𝙲𝙴𝚂𝚂 𝙲𝙾𝙽𝚃𝚁𝙾𝙻 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"{mode_icon} 𝙼𝙾𝙳𝙴：{mode_text}", callback_data="toggle_mode")],
        [InlineKeyboardButton(f"━━━ 💳 𝙲𝚁𝙴𝙳𝙸𝚃 𝙲𝙾𝙽𝚃𝚁𝙾𝙻 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"{credit_icon} 𝙲𝚁𝙴𝙳𝙸𝚃 𝙼𝙾𝙳𝙴：{'𝙾𝙽' if credit_mode else '𝙾𝙵𝙵'}", callback_data="toggle_credit_mode")],
        [InlineKeyboardButton(f"🎯 𝚂𝙴𝚃 𝙳𝙰𝙸𝙻𝚈 𝙲𝚁𝙴𝙳𝙸𝚃𝚂：{fn(str(daily_credits))}", callback_data="set_daily_credits")],
    ]

    if is_own:
        keyboard.extend([
            [InlineKeyboardButton(f"━━━ ⚡ 𝙰𝙳𝙼𝙸𝙽𝚂 ━━━", callback_data="noop")],
            [InlineKeyboardButton(f"➕ 𝙰𝙳𝙳 𝙰𝙳𝙼𝙸𝙽", callback_data="add_admin"),
             InlineKeyboardButton(f"➖ 𝚁𝙴𝙼𝙾𝚅𝙴 𝙰𝙳𝙼𝙸𝙽", callback_data="remove_admin")],
            [InlineKeyboardButton(f"👥 𝙰𝙳𝙼𝙸𝙽 𝙻𝙸𝚂𝚃", callback_data="admin_list")],
        ])
    else:
        keyboard.append([InlineKeyboardButton(f"👥 𝙰𝙳𝙼𝙸𝙽 𝙻𝙸𝚂𝚃", callback_data="admin_list")])

    keyboard.extend([
        [InlineKeyboardButton(f"━━━ 📨 𝙱𝚁𝙾𝙰𝙳𝙲𝙰𝚂𝚃 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"📨 𝚂𝙴𝙽𝙳 𝙱𝚁𝙾𝙰𝙳𝙲𝙰𝚂𝚃", callback_data="broadcast"),
         InlineKeyboardButton(f"📢 𝙰𝙽𝙽𝙾𝚄𝙽𝙲𝙴", callback_data="announce")],
        [InlineKeyboardButton(f"━━━ 🤖 𝙱𝙾𝚃 𝙲𝙾𝙽𝙵𝙸𝙶 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"⏱️ 𝙲𝙾𝙾𝙻𝙳𝙾𝚆𝙽", callback_data="set_cooldown"),
         InlineKeyboardButton(f"📊 𝙼𝙰𝚇 𝙼𝚃𝙶", callback_data="set_max_mtg")],
        [InlineKeyboardButton(f"📡 𝙰𝙿𝙸 𝚂𝙴𝚃𝚃𝙸𝙽𝙶𝚂", callback_data="api_settings"),
         InlineKeyboardButton(f"⏰ 𝙸𝙽𝚃𝙴𝚁𝚅𝙰𝙻", callback_data="set_interval")],
        [InlineKeyboardButton(f"📊 𝙱𝙾𝚃 𝚂𝚃𝙰𝚃𝚂", callback_data="bot_stats"),
         InlineKeyboardButton(f"🔄 𝚁𝙴𝚂𝙴𝚃 𝙰𝙻𝙻", callback_data="reset_all_stats")],
        [InlineKeyboardButton(f"━━━ 📈 𝙶𝙻𝙾𝙱𝙰𝙻 𝚂𝚃𝙰𝚃𝚂 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"📊 𝙶𝙻𝙾𝙱𝙰𝙻 𝚂𝚃𝙰𝚃𝙸𝚂𝚃𝙸𝙲𝚂", callback_data="global_stats"),
         InlineKeyboardButton(f"🏆 𝚃𝙾𝙿 𝚃𝚁𝙰𝙳𝙴𝚁𝚂", callback_data="top_traders")],
        [InlineKeyboardButton(f"📜 𝙶𝙻𝙾𝙱𝙰𝙻 𝙻𝙾𝙶", callback_data="global_log")],
        [InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺 𝚃𝙾 𝙼𝙰𝙸𝙽", callback_data="back_main")],
    ])
    return InlineKeyboardMarkup(keyboard)

def get_admin_panel_message():
    mode = USERS.get('mode', 'public')
    total_users = len(USER_DATA)
    allowed = len(USERS.get('allowed', []))
    banned = len(USERS.get('banned', []))
    admins = len(CONFIG.get('ADMINS', []))
    active_bots = sum(1 for s in USER_TRADING_SESSIONS.values() if s.get('active'))
    mtg = CONFIG.get('MAX_MTG_LEVEL', 1)
    interval = CONFIG.get('API_INTERVAL', '1m')
    cooldown = CONFIG.get('SIGNAL_COOLDOWN', 60)
    credit_mode = CONFIG.get('CREDIT_MODE', False)
    daily_credits = CONFIG.get('DAILY_FREE_CREDITS', 5)

    msg = f"""
╔═══════════════════════════════════╗
║      👑 𝙰𝙳𝙼𝙸𝙽 𝙲𝙾𝙽𝚃𝚁𝙾𝙻 𝙿𝙰𝙽𝙴𝙻     ║
╚═══════════════════════════════════╝

╭━━━━━━━【👥】━━━━━━━╮
│ 📡 𝙼𝚘𝚍𝚎：{ff(mode.upper())}
│ 👥 𝚃𝚘𝚝𝚊𝚕 𝚄𝚜𝚎𝚛𝚜：{fn(str(total_users))}
│ ✅ 𝙰𝚕𝚕𝚘𝚠𝚎𝚍：{fn(str(allowed))}
│ 🚫 𝙱𝚊𝚗𝚗𝚎𝚍：{fn(str(banned))}
│ ⚡ 𝙰𝚍𝚖𝚒𝚗𝚜：{fn(str(admins))}
╰━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━【🤖】━━━━━━━╮
│ 🟢 𝙰𝚌𝚝𝚒𝚟𝚎 𝙱𝚘𝚝𝚜：{fn(str(active_bots))}
│ 🔄 𝙼𝙰𝚇 𝙼𝚃𝙶：{fn(str(mtg))}
│ ⏰ 𝙸𝚗𝚝𝚎𝚛𝚟𝚊𝚕：{ff(interval)}
│ ⏱️ 𝙲𝚘𝚘𝚕𝚍𝚘𝚠𝚗：{fn(str(cooldown))}𝚜
│ 📈 𝙰𝚜𝚜𝚎𝚝𝚜：{fn(str(len(ASSETS)))} 𝙿𝚊𝚒𝚛𝚜
╰━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━【💳】━━━━━━━╮
│ 💳 𝙲𝚛𝚎𝚍𝚒𝚝 𝙼𝚘𝚍𝚎：{'✅ 𝙾𝙽' if credit_mode else '❌ 𝙾𝙵𝙵'}
│ 🎯 𝙳𝚊𝚒𝚕𝚢 𝙲𝚛𝚎𝚍𝚒𝚝𝚜：{fn(str(daily_credits))}
╰━━━━━━━━━━━━━━━━━━━╯

━━━━━━━━━━━━━━━━━━━━━━━━━━
   ⚡ {ff("Select admin action")} ⚡
━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    return msg

def get_status_message(user_id):
    session = USER_TRADING_SESSIONS.get(user_id, {})
    stats = get_user_stats(user_id)
    overall = get_user_statistics(user_id)
    today = get_user_statistics(user_id, get_user_today_results(user_id))

    pair_wins = stats.get('pair_wins', 0)
    pair_losses = stats.get('pair_losses', 0)
    pair_total = pair_wins + pair_losses
    pair_acc = (pair_wins / pair_total * 100) if pair_total > 0 else 0
    streak = stats.get('streak', 0)
    best_streak = stats.get('best_streak', 0)

    is_active = session.get('active', False)
    active_sig = session.get('active_signal')
    status_icon = "🟢" if is_active else "🔴"
    status_text = ff("RUNNING") if is_active else ff("STOPPED")

    sig_info = ""
    if active_sig:
        sig_info = f"""
╭━━━━━━━【🎯】━━━━━━━╮
│ 📡 𝙰𝚌𝚝𝚒𝚟𝚎 𝚂𝚒𝚐𝚗𝚊𝚕：
│ 💎 {fancy_asset_name(active_sig['asset'])}
│ {'🟢' if active_sig['direction']=='CALL' else '🔴'} {ff(active_sig['direction'])}
│ 🔄 𝙼𝚃𝙶：{fn(str(active_sig['mtg']))}
╰━━━━━━━━━━━━━━━━━━━╯"""

    msg = f"""
╔═══════════════════════════════════╗
║      📊 𝚃𝚁𝙰𝙳𝙸𝙽𝙶 𝚂𝚃𝙰𝚃𝚄𝚂         ║
╚═══════════════════════════════════╝

╭━━━━━━━【🤖】━━━━━━━╮
│ {status_icon} 𝚂𝚝𝚊𝚝𝚞𝚜：{status_text}
│ 🔢 𝙼𝚃𝙶 𝙻𝚎𝚟𝚎𝚕：{fn(str(CONFIG['MAX_MTG_LEVEL']))}
│ ⏰ 𝙸𝚗𝚝𝚎𝚛𝚟𝚊𝚕：{ff(CONFIG['API_INTERVAL'])}
╰━━━━━━━━━━━━━━━━━━━╯
{sig_info}
╭━━━━━━━【📈】━━━━━━━╮
│ 🏆 𝙾𝚟𝚎𝚛𝚊𝚕𝚕 𝚂𝚝𝚊𝚝𝚜：
│ ✅ 𝚆𝚒𝚗𝚜：{fn(str(overall['wins']))}
│ ❌ 𝙻𝚘𝚜𝚜𝚎𝚜：{fn(str(overall['losses']))}
│ 🎯 𝙰𝚌𝚌𝚞𝚛𝚊𝚌𝚢：{fn(f"{overall['accuracy']:.1f}")}٪
╰━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━【📅】━━━━━━━╮
│ 📅 𝚃𝚘𝚍𝚊𝚢 𝚂𝚝𝚊𝚝𝚜：
│ ✅ 𝚆𝚒𝚗𝚜：{fn(str(today['wins']))}
│ ❌ 𝙻𝚘𝚜𝚜𝚎𝚜：{fn(str(today['losses']))}
│ 🎯 𝙰𝚌𝚌𝚞𝚛𝚊𝚌𝚢：{fn(f"{today['accuracy']:.1f}")}٪
╰━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━【⚖️】━━━━━━━╮
│ ⚖️ 𝙿𝚊𝚒𝚛𝚜：{fn(str(pair_wins))}𝚆╱{fn(str(pair_losses))}𝙻 ({fn(f"{pair_acc:.1f}")}٪)
│ 🔥 𝙲𝚞𝚛𝚛𝚎𝚗𝚝 𝚂𝚝𝚛𝚎𝚊𝚔：{fn(str(streak))}
│ 🏅 𝙱𝚎𝚜𝚝 𝚂𝚝𝚛𝚎𝚊𝚔：{fn(str(best_streak))}
╰━━━━━━━━━━━━━━━━━━━╯

━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    return msg

def get_help_message():
    msg = f"""
╔═══════════════════════════════════╗
║        💡 𝙷𝙴𝙻𝙿 & 𝙶𝚄𝙸𝙳𝙴          ║
╚═══════════════════════════════════╝

╭━━━━━━━【🤖】━━━━━━━╮
│ ▶️ {ff("START BOT")}
│    𝚂𝚝𝚊𝚛𝚝 𝚢𝚘𝚞𝚛 𝚝𝚛𝚊𝚍𝚒𝚗𝚐 𝚋𝚘𝚝
│
│ ⏹ {ff("STOP BOT")}
│    𝚂𝚝𝚘𝚙 𝚢𝚘𝚞𝚛 𝚝𝚛𝚊𝚍𝚒𝚗𝚐 𝚋𝚘𝚝
│
│ 🔮 {ff("FUTURE CHECKER")}
│    𝙿𝚊𝚜𝚝𝚎 𝚜𝚒𝚐𝚗𝚊𝚕𝚜 𝚊𝚗𝚍 𝚌𝚑𝚎𝚌𝚔
│    𝚛𝚎𝚜𝚞𝚕𝚝𝚜 𝚠𝚒𝚝𝚑 𝙼𝚃𝙶
│    𝚂𝚞𝚙𝚙𝚘𝚛𝚝𝚜 𝚃𝙾𝙳𝙰𝚈 & 𝚈𝙴𝚂𝚃𝙴𝚁𝙳𝙰𝚈
╰━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━【📊】━━━━━━━╮
│ 📊 {ff("STATUS")}
│    𝚅𝚒𝚎𝚠 𝚢𝚘𝚞𝚛 𝚝𝚛𝚊𝚍𝚒𝚗𝚐 𝚜𝚝𝚊𝚝𝚜
│
│ 📋 {ff("PARTIAL")}
│    𝚅𝚒𝚎𝚠 𝚝𝚘𝚍𝚊𝚢'𝚜 𝚛𝚎𝚜𝚞𝚕𝚝𝚜
│
│ 📜 {ff("HISTORY")}
│    𝚅𝚒𝚎𝚠 𝚊𝚕𝚕 𝚝𝚛𝚊𝚍𝚎 𝚑𝚒𝚜𝚝𝚘𝚛𝚢
╰━━━━━━━━━━━━━━━━━━━╯

╔═══════════════════════════════════╗
║     ✦ 𝗥𝗔𝗩𝗜𝗧𝗛 𝗔𝗜 𝗣𝗥𝗢 ✦          ║
╚═══════════════════════════════════╝"""
    return msg

def get_profile_message(user_id):
    uid = str(user_id)
    user_data = USER_DATA.get(uid, {})
    stats = get_user_stats(user_id)
    wins = stats.get('win', 0)
    losses = stats.get('loss', 0)
    total = wins + losses
    acc = (wins / total * 100) if total > 0 else 0
    streak = stats.get('streak', 0)
    best_streak = stats.get('best_streak', 0)
    pair_wins = stats.get('pair_wins', 0)
    pair_losses = stats.get('pair_losses', 0)
    pair_total = pair_wins + pair_losses
    pair_acc = (pair_wins / pair_total * 100) if pair_total > 0 else 0
    username = user_data.get('username', 'Unknown')
    first_seen = user_data.get('first_seen', 'Unknown')
    last_active = user_data.get('last_active', 'Unknown')
    role = "👑 Owner" if is_owner(user_id) else ("⚡ Admin" if is_admin(user_id) else "👤 User")
    is_allowed = user_id in USERS.get('allowed', [])
    is_banned = user_id in USERS.get('banned', [])

    if CONFIG.get("CREDIT_MODE", False) and user_id not in USERS.get("allowed", []) and not is_admin(user_id):
        credits = get_user_credits(user_id)
        daily = CONFIG.get('DAILY_FREE_CREDITS', 5)
        credit_display = f"💳 {fn(str(credits))}/{fn(str(daily))}"
    else:
        credit_display = "💳 Unlimited"

    msg = f"""
╔═══════════════════════════════════╗
║        📱 𝙿𝚁𝙾𝙵𝙸𝙻𝙴 𝙳𝙴𝚃𝙰𝙸𝙻𝚂        ║
╚═══════════════════════════════════╝

╭━━━━━━━【👤】━━━━━━━╮
│ 🆔 𝙸𝙳：{fn(str(user_id))}
│ 📛 𝙽𝚊𝚖𝚎：{username}
│ 🎭 𝚁𝚘𝚕𝚎：{role}
│ 📅 𝙵𝚒𝚛𝚜𝚝 𝚂𝚎𝚎𝚗：{first_seen[:16]}
│ 🕐 𝙻𝚊𝚜𝚝 𝙰𝚌𝚝𝚒𝚟𝚎：{last_active[:16]}
│ ✅ 𝙰𝚕𝚕𝚘𝚠𝚎𝚍：{'✅' if is_allowed else '❌'}
│ 🚫 𝙱𝚊𝚗𝚗𝚎𝚍：{'🚫' if is_banned else '✅'}
│ {credit_display}
╰━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━【📈】━━━━━━━╮
│ 🏆 𝚆𝚒𝚗𝚜：{fn(str(wins))}
│ ❌ 𝙻𝚘𝚜𝚜𝚎𝚜：{fn(str(losses))}
│ 🎯 𝙰𝚌𝚌𝚞𝚛𝚊𝚌𝚢：{fn(f"{acc:.1f}")}٪
│ 🔥 𝙲𝚞𝚛𝚛𝚎𝚗𝚝 𝚂𝚝𝚛𝚎𝚊𝚔：{fn(str(streak))}
│ 🏅 𝙱𝚎𝚜𝚝 𝚂𝚝𝚛𝚎𝚊𝚔：{fn(str(best_streak))}
│ ⚖️ 𝙿𝚊𝚒𝚛 𝚆/𝙻：{fn(str(pair_wins))}/{fn(str(pair_losses))} ({fn(f"{pair_acc:.1f}")}٪)
╰━━━━━━━━━━━━━━━━━━━╯

━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✦ 𝗥𝗔𝗩𝗜𝗧𝗛 𝗔𝗜 𝗣𝗥𝗢 ✦
━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    return msg

# ================= BOT TELEGRAM SENDING WITH CHART =================



# ================= TRADING LOOP (modified to pass user settings) =================


async def send_partial_summary_for_user(user_id: int):
    date_str = datetime.now(UTC_PLUS_6).strftime("%d.%m.%Y")
    today = get_user_today_results(user_id)
    otc = [r for r in today if '_otc' in r.get('asset', '')]
    real = [r for r in today if '_otc' not in r.get('asset', '')]

    def format_result_lines(res, name):
        if not res:
            return f"——— {ff('NO')} {name} {ff('SIGNALS')} {ff('PLACED')} ———"
        lines = []
        for r in res[-20:]:
            ts = r.get('display_time', '??:??')
            asset_fancy = fancy_asset_name(r.get('asset', ''))
            dir_display = fancy_direction(r.get('direction', 'BUY'))
            result_icon = "✅" if r.get('result') == 'WIN' else "✖️"
            mt = ""
            if r.get('result') == 'WIN' and r.get('mtg_level', 0) == 1:
                mt = '¹'
            elif r.get('result') == 'WIN' and r.get('mtg_level', 0) == 2:
                mt = '²'
            elif r.get('result') == 'WIN' and r.get('mtg_level', 0) >= 3:
                mt = f'{"³" if r["mtg_level"]==3 else str(r["mtg_level"])}'
            lines.append(f"⧉ {fancy_time(ts)} - {asset_fancy} - {dir_display} {result_icon}{mt}")
        return "\n".join(lines)

    real_lines = format_result_lines(real, ff("REAL"))
    otc_lines = format_result_lines(otc, ff("OTC"))

    overall = get_user_statistics(user_id, today)
    total = overall['total_trades']
    wins = overall['wins']
    losses = overall['losses']
    acc = overall['accuracy']

    msg = f"""========= {ff("PARTIAL RESULTS")} ==========
━━━━━━━━━・━━━━━━━━━
                  📆 — {fn(date_str)}
━━━━━━━━━・━━━━━━━━━
                  📈 {ff("REAL MARKET")}
━━━━━━━━━・━━━━━━━━━
{real_lines}
━━━━━━━━━・━━━━━━━━━
                  📉 {ff("OTC MARKET")}
━━━━━━━━━・━━━━━━━━━
{otc_lines}
━━━━━━━━━・━━━━━━━━━
 🧮 {ff("PLACER")} : {fn(str(total))} 𝘅 {fn(str(losses))} ◈ ({fn(f"{acc:.1f}")}٪)
━━━━━━━━━・━━━━━━━━━
 🚀 {ff("WIN")} : {fn(str(wins))} ┃ {ff("LOSS")} : {fn(str(losses))} ┃ ◈ ({fn(f"{acc:.1f}")}٪)
━━━━━━━━━・━━━━━━━━━"""

    chat_id = get_user_chat_id(user_id)
    await send_telegram_photo_with_caption(chat_id, None, msg, reply_markup=None)

# ================= USER STATS FUNCTIONS =================
def save_user_result_entry(user_id, result_data):
    try:
        stats = get_user_stats(user_id)
        existing = next((r for r in stats['all_results']
                        if r['signal_time'] == result_data['signal_time']
                        and r['asset'] == result_data['asset']
                        and r['mtg_level'] == result_data['mtg_level']), None)
        if not existing:
            stats['all_results'].append(result_data)
            if len(stats['all_results']) > 1000:
                stats['all_results'] = stats['all_results'][-1000:]
            save_user_stats()
            return True
        return False
    except:
        return True

def get_user_today_results(user_id):
    today = datetime.now(UTC_PLUS_6).date().isoformat()
    stats = get_user_stats(user_id)
    return [r for r in stats['all_results'] if r.get('date') == today]


# ================= FORMAT FUNCTIONS (with footer) =================


# ================= TRADING LOOP (modified) =================

# ================= TELEGRAM HANDLERS =================
async def safe_edit_or_reply(query, text, reply_markup=None, parse_mode='HTML'):
    message = query.message
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except telegram.error.BadRequest as e:
        if "There is no text in the message to edit" in str(e):
            await message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            await query.answer()
        else:
            await message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            await query.answer()
    except Exception:
        await message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        await query.answer()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    user_id = user.id
    update_user_activity(user_id, user.username)

    if not is_authorized(user_id):
        keyboard = [[InlineKeyboardButton("📞 𝙲𝙾𝙽𝚃𝙰𝙲𝚃 𝙾𝚆𝙽𝙴𝚁", url="https://t.me/MAHABUB_iX")]]
        msg = f"""
╔═══════════════════════════════════╗
║        ❌ 𝙰𝙲𝙲𝙴𝚂𝚂 𝙳𝙴𝙽𝙸𝙴𝙳         ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━━━╮
│  🚫 {ff("You are not authorized")}
│  📞 {ff("Please contact the owner")}
│  🆔 {ff("Your ID")}: {fn(str(user_id))}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if CONFIG.get("CREDIT_MODE", False) and user_id not in USERS.get("allowed", []) and not is_admin(user_id):
        credits = get_user_credits(user_id)
        if credits <= 0:
            msg = f"""
╔═══════════════════════════════════╗
║      ⛔ 𝙲𝚁𝙴𝙳𝙸𝚃𝚂 𝙴𝚇𝙷𝙰𝚄𝚂𝚃𝙴𝙳        ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━━━╮
│  💳 {ff("You have used all free credits")}
│  📞 {ff("Contact admin for more")}
│  🔄 {ff("Next reset at midnight (BDT)")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
            keyboard = [[InlineKeyboardButton("📞 𝙲𝙾𝙽𝚃𝙰𝙲𝚃 𝙾𝚆𝙽𝙴𝚁", url=f"https://t.me/{CONFIG.get('BOT_USERNAME','Mahabub_iX').lstrip('@')}")]]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            return

    is_admin_user = is_admin(user_id)
    is_owner_user = is_owner(user_id)
    welcome_msg = get_welcome_message(user, is_admin_user, is_owner_user)

    if is_admin_user:
        keyboard = get_owner_keyboard(user_id)
    else:
        keyboard = get_main_keyboard(user_id)

    await update.message.reply_text(welcome_msg, parse_mode='HTML', reply_markup=keyboard)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"⚠️ Error: {context.error}")
    import traceback
    traceback.print_exception(type(context.error), context.error, context.error.__traceback__)
    if update and update.effective_chat:
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ An error occurred. Please try again later.")
        except:
            pass

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        await query.answer("❌ Invalid user")
        return

    update_user_activity(user_id)
    await query.answer()
    data = query.data

    if data == "noop":
        return

    if user_id not in USER_TRADING_SESSIONS:
        USER_TRADING_SESSIONS[user_id] = {
            'active': False,
            'trading_task': None,
            'active_signal': None,
            'last_summary_time': time.time()
        }
    session = USER_TRADING_SESSIONS[user_id]
    uid = str(user_id)

    # ============ PROFILE ============
    if data == "profile":
        msg = get_profile_message(user_id)
        keyboard = [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    # ============ FUTURE CHECKER ============
    if data == "future_checker":
        context.user_data['expecting_future_signals'] = True
        context.user_data.pop('future_parsed_signals', None)
        context.user_data.pop('future_mtg_level', None)
        context.user_data.pop('future_payout_filter', None)
        context.user_data.pop('future_check_date', None)
        context.user_data.pop('future_date_mode', None)
        msg = f"""
╔═══════════════════════════════════╗
║     🔮 𝙵𝚄𝚃𝚄𝚁𝙴 𝙲𝙷𝙴𝙲𝙺𝙴𝚁           ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━━━╮
│  📋 {ff("Paste your signals below")}
│
│  {ff("Supported formats:")}
│  ANY format, ANY font, ANY order.
│  Examples:
│  ⧉ 𝙱𝚁𝙻𝚄𝚂𝙳⁻𝙾𝚃𝙲 - 𝟷𝟶⁚𝟹𝟸 ⇨ 𝙿𝚄𝚃
│  ⧉ 𝚄𝚂𝙳𝙼𝚇𝙽⁻𝙾𝚃𝙲 - 𝟷𝟶⁚𝟺𝟶 ⇨ 𝙱𝚄𝚈
│  BRLUSD_otc 10:32 PUT
│  USDMXN-OTC - 10:40 - BUY
│  BUY USDPKR 10:45
│  M1;EURUSD;12:00;CALL
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await query.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="back_main")]]
            ),
            parse_mode='HTML'
        )
        return

    # MTG selection for future checker — after MTG, ask payout filter
    if data == "fc_mtg_0":
        context.user_data['future_mtg_level'] = 0
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  💰 {ff("PAYOUT FILTER")}
│
│  {ff(">80 PAYOUT = Signals with <80%")}
│  {ff("payout shown with actual % only")}
│  {ff("NOT counted in W/L stats")}
│
│  {ff("NO = Count all signals")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        keyboard = [
            [InlineKeyboardButton(f"💰 {ff('>80 PAYOUT')}", callback_data="fc_payout_80"),
             InlineKeyboardButton(f"❌ {ff('NO FILTER')}", callback_data="fc_payout_no")],
            [InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="back_main")]
        ]
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data == "fc_mtg_1":
        context.user_data['future_mtg_level'] = 1
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  💰 {ff("PAYOUT FILTER")}
│
│  {ff(">80 PAYOUT = Signals with <80%")}
│  {ff("payout shown with actual % only")}
│  {ff("NOT counted in W/L stats")}
│
│  {ff("NO = Count all signals")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        keyboard = [
            [InlineKeyboardButton(f"💰 {ff('>80 PAYOUT')}", callback_data="fc_payout_80"),
             InlineKeyboardButton(f"❌ {ff('NO FILTER')}", callback_data="fc_payout_no")],
            [InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="back_main")]
        ]
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    # Payout filter selection — after payout, ask TODAY or YESTERDAY
    if data == "fc_payout_80":
        context.user_data['future_payout_filter'] = 80
        today_date = datetime.now(UTC_PLUS_6).date()
        yesterday_date = today_date - timedelta(days=1)
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  📅 {ff("SELECT DATE")}
│
│  📆 {ff("TODAY")}: {fn(today_date.strftime("%Y-%m-%d"))}
│  📆 {ff("YESTERDAY")}: {fn(yesterday_date.strftime("%Y-%m-%d"))}
│
│  {ff("Which date to check results?")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        keyboard = [
            [InlineKeyboardButton(f"📅 {ff('TODAY')} ({fn(today_date.strftime('%d.%m'))})", callback_data="fc_date_today"),
             InlineKeyboardButton(f"📅 {ff('YESTERDAY')} ({fn(yesterday_date.strftime('%d.%m'))})", callback_data="fc_date_yesterday")],
            [InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="back_main")]
        ]
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data == "fc_payout_no":
        context.user_data['future_payout_filter'] = 0
        today_date = datetime.now(UTC_PLUS_6).date()
        yesterday_date = today_date - timedelta(days=1)
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  📅 {ff("SELECT DATE")}
│
│  📆 {ff("TODAY")}: {fn(today_date.strftime("%Y-%m-%d"))}
│  📆 {ff("YESTERDAY")}: {fn(yesterday_date.strftime("%Y-%m-%d"))}
│
│  {ff("Which date to check results?")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        keyboard = [
            [InlineKeyboardButton(f"📅 {ff('TODAY')} ({fn(today_date.strftime('%d.%m'))})", callback_data="fc_date_today"),
             InlineKeyboardButton(f"📅 {ff('YESTERDAY')} ({fn(yesterday_date.strftime('%d.%m'))})", callback_data="fc_date_yesterday")],
            [InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="back_main")]
        ]
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    # Date selection — then process
    if data == "fc_date_today":
        context.user_data['future_check_date'] = datetime.now(UTC_PLUS_6).date()
        context.user_data['future_date_mode'] = "today"
        await process_future_checker(query, context, user_id)
        return

    if data == "fc_date_yesterday":
        context.user_data['future_check_date'] = datetime.now(UTC_PLUS_6).date() - timedelta(days=1)
        context.user_data['future_date_mode'] = "yesterday"
        await process_future_checker(query, context, user_id)
        return

    # ============ LOSS SS ============
    if data == "loss_ss":
        loss_signals = context.user_data.get('loss_signals', [])
        loss_date = context.user_data.get('loss_ss_date', None)
        if not loss_signals:
            await safe_edit_or_reply(query, "❌ No loss signals to show.")
            return
        summary_lines = ""
        for loss in loss_signals:
            asset_fancy = fancy_asset_name(loss['asset'])
            time_fancy = fancy_time(loss['time'])
            dir_fancy = fancy_direction(loss['direction'])
            summary_lines += f"⧉ {asset_fancy} - {time_fancy} ⇨ {dir_fancy} ✖️\n"

        summary_msg = f"""
╔═══════════════════════════════════╗
║     📸 𝙻𝙾𝚂𝚂 𝚂𝙸𝙶𝙽𝙰𝙻𝚂              ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━━━╮
│  {ff("The following signals are losses:")}
╰━━━━━━━━━━━━━━━━━━━━━━╯
{summary_lines}
━━━━━━━━━━━ • ━━━━━━━━━━━
   📸 {ff("Sending charts for each loss...")}
"""
        await query.message.reply_text(summary_msg, parse_mode='HTML')

        for loss in loss_signals:
            try:
                if loss_date:
                    use_date = loss_date
                else:
                    use_date = datetime.now(UTC_PLUS_6).date()
                hour, minute = map(int, loss['time'].split(':'))
                target_dt = UTC_PLUS_6.localize(datetime(use_date.year, use_date.month, use_date.day, hour, minute, 0))
            except:
                continue
            img_buffer = await generate_signal_chart(loss['asset'], target_dt, loss['direction'], user_id=user_id, mtg_level=loss.get('mtg_used',0))
            if img_buffer:
                caption = f"❌ LOSS\n{fancy_asset_name(loss['asset'])} - {fancy_time(loss['time'])} - {fancy_direction(loss['direction'])}"
                await BOT_APPLICATION.bot.send_photo(chat_id=user_id, photo=img_buffer, caption=caption, parse_mode='HTML')
            else:
                await BOT_APPLICATION.bot.send_message(chat_id=user_id, text=f"❌ Could not generate chart for {loss['asset']} at {loss['time']}")
            await asyncio.sleep(0.5)

        final_msg = f"""
╔═══════════════════════════════════╗
║     📸 𝙻𝙾𝚂𝚂 𝚂𝙸𝙶𝙽𝙰𝙻𝚂              ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━━━╮
│  {ff("The following signals are losses:")}
╰━━━━━━━━━━━━━━━━━━━━━━╯
{summary_lines}
━━━━━━━━━━━ • ━━━━━━━━━━━
   ✅ {ff("All loss charts have been sent.")}
"""
        await query.message.reply_text(final_msg, parse_mode='HTML')
        # Preserve loss list and original Future Checker output for repeat viewing.
        return

    # ============ STRATEGY SELECTION ============
    if data == "select_strategy":
        strategies = [
            ("REVERSE_TREND_PRO", "💎 Reverse + Trend PRO • Default"),
            ("SUPPORT_RESISTANCE", "📈 Level Rejection Only"),
            ("RSI_REVERSE", "🌀 Confirmed Reversal Only"),
            ("EMA_TREND", "📊 Trend Pullback Only"),
            ("STRONG_SIGNAL", "💪 Strict Confluence")
        ]
        current_strategy = USER_DATA.get(uid, {}).get("settings", {}).get("strategy", "REVERSE_TREND_PRO")
        keyboard = []
        for key, label in strategies:
            icon = "✅" if key == current_strategy else "⬜"
            keyboard.append([InlineKeyboardButton(f"{icon} {label}", callback_data=f"strategy_{key}")])
        keyboard.append([InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="settings")])
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  🧠 {ff("SELECT STRATEGY")}
│  {ff("Current")}: {ff(current_strategy)}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("strategy_"):
        strategy = data[9:]
        if strategy not in STRATEGY_LABELS:
            return
        USER_DATA[uid]["settings"]["strategy"] = strategy
        save_user_data()
        msg = get_settings_message(user_id)
        await safe_edit_or_reply(query, msg, get_settings_keyboard(user_id))
        return

    # ============ CUSTOM FOOTER TEXT ============
    if data == "set_footer_text":
        context.user_data['expecting_footer_text'] = True
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  ✏️ {ff("SET FOOTER TEXT")}
│  {ff("Send any text (max 30 chars)")}
│  {ff("It will appear in bold at bottom")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="settings")]]
        ))
        return

    # ============ SETTINGS ============
    if data == "settings":
        msg = get_settings_message(user_id)
        keyboard = get_settings_keyboard(user_id)
        await safe_edit_or_reply(query, msg, keyboard)
        return

    if data == "set_watermark":
        context.user_data['expecting_watermark'] = True
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  💧 {ff("SET WATERMARK")}
│  {ff("Send new text (max 20 chars)")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="settings")]]
        ))
        return

    if data == "set_contact":
        context.user_data['expecting_contact'] = True
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  📞 {ff("SET CONTACT")}
│  {ff("Send @username")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="settings")]]
        ))
        return

    if data == "toggle_chart_style":
        USER_DATA[uid]["settings"]["chart_style"] = "pro"
        save_user_data()
        await safe_edit_or_reply(query, get_settings_message(user_id), get_settings_keyboard(user_id))
        return

    if data == "toggle_sound":
        settings = USER_DATA.get(uid, {}).get("settings", {})
        USER_DATA[uid]["settings"]["sound_alert"] = not settings.get("sound_alert", True)
        save_user_data()
        msg = get_settings_message(user_id)
        await safe_edit_or_reply(query, msg, get_settings_keyboard(user_id))
        return

    if data == "toggle_notif_mode":
        settings = USER_DATA.get(uid, {}).get("settings", {})
        modes = ["all", "signals", "results", "minimal"]
        current = settings.get("notification_mode", "all")
        idx = (modes.index(current) + 1) % len(modes) if current in modes else 0
        USER_DATA[uid]["settings"]["notification_mode"] = modes[idx]
        save_user_data()
        msg = get_settings_message(user_id)
        await safe_edit_or_reply(query, msg, get_settings_keyboard(user_id))
        return

    if data == "toggle_risk":
        settings = USER_DATA.get(uid, {}).get("settings", {})
        levels = ["low", "medium", "high", "aggressive"]
        current = settings.get("risk_level", "medium")
        idx = (levels.index(current) + 1) % len(levels) if current in levels else 0
        USER_DATA[uid]["settings"]["risk_level"] = levels[idx]
        save_user_data()
        msg = get_settings_message(user_id)
        await safe_edit_or_reply(query, msg, get_settings_keyboard(user_id))
        return

    if data == "toggle_signal_type":
        settings = USER_DATA.get(uid, {}).get("settings", {})
        types = ["all", "otc", "real", "call_only", "put_only"]
        current = settings.get("signal_type", "all")
        idx = (types.index(current) + 1) % len(types) if current in types else 0
        USER_DATA[uid]["settings"]["signal_type"] = types[idx]
        save_user_data()
        msg = get_settings_message(user_id)
        await safe_edit_or_reply(query, msg, get_settings_keyboard(user_id))
        return

    if data == "toggle_auto_result":
        settings = USER_DATA.get(uid, {}).get("settings", {})
        USER_DATA[uid]["settings"]["auto_result"] = not settings.get("auto_result", True)
        save_user_data()
        msg = get_settings_message(user_id)
        await safe_edit_or_reply(query, msg, get_settings_keyboard(user_id))
        return

    if data == "toggle_show_payout":
        settings = USER_DATA.get(uid, {}).get("settings", {})
        USER_DATA[uid]["settings"]["show_payout"] = not settings.get("show_payout", True)
        save_user_data()
        msg = get_settings_message(user_id)
        await safe_edit_or_reply(query, msg, get_settings_keyboard(user_id))
        return

    if data == "toggle_martingale":
        settings = USER_DATA.get(uid, {}).get("settings", {})
        USER_DATA[uid]["settings"]["martingale"] = not settings.get("martingale", False)
        save_user_data()
        msg = get_settings_message(user_id)
        await safe_edit_or_reply(query, msg, get_settings_keyboard(user_id))
        return

    if data == "preferred_assets":
        settings = USER_DATA.get(uid, {}).get("settings", {})
        pref = settings.get("preferred_assets", [])
        keyboard = []
        row = []
        for asset in ASSETS:
            icon = "⭐" if asset in pref else "⬜"
            short = asset.replace("_otc", "").replace("USD", "")
            row.append(InlineKeyboardButton(f"{icon} {ff(short)}", callback_data=f"pref_{asset}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="settings")])
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  ⭐ {ff("PREFERRED ASSETS")}
│  {ff("Tap to toggle")}
│  𝚂𝚎𝚕𝚎𝚌𝚝𝚎𝚍：{fn(str(len(pref)))}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("pref_"):
        asset = data[5:]
        settings = USER_DATA.get(uid, {}).get("settings", {})
        pref = settings.get("preferred_assets", [])
        if asset in pref:
            pref.remove(asset)
        else:
            pref.append(asset)
        USER_DATA[uid]["settings"]["preferred_assets"] = pref
        save_user_data()
        keyboard = []
        row = []
        for a in ASSETS:
            icon = "⭐" if a in pref else "⬜"
            short = a.replace("_otc", "").replace("USD", "")
            row.append(InlineKeyboardButton(f"{icon} {ff(short)}", callback_data=f"pref_{a}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="settings")])
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  ⭐ {ff("PREFERRED ASSETS")}
│  {ff("Tap to toggle")}
│  𝚂𝚎𝚕𝚎𝚌𝚝𝚎𝚍：{fn(str(len(pref)))}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data == "blocked_assets":
        settings = USER_DATA.get(uid, {}).get("settings", {})
        blocked = settings.get("blocked_assets", [])
        keyboard = []
        row = []
        for asset in ASSETS:
            icon = "🚫" if asset in blocked else "⬜"
            short = asset.replace("_otc", "").replace("USD", "")
            row.append(InlineKeyboardButton(f"{icon} {ff(short)}", callback_data=f"block_{asset}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="settings")])
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  🚫 {ff("BLOCKED ASSETS")}
│  {ff("Tap to toggle")}
│  𝙱𝚕𝚘𝚌𝚔𝚎𝚍：{fn(str(len(blocked)))}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("block_"):
        asset = data[6:]
        settings = USER_DATA.get(uid, {}).get("settings", {})
        blocked = settings.get("blocked_assets", [])
        if asset in blocked:
            blocked.remove(asset)
        else:
            blocked.append(asset)
        USER_DATA[uid]["settings"]["blocked_assets"] = blocked
        save_user_data()
        keyboard = []
        row = []
        for a in ASSETS:
            icon = "🚫" if a in blocked else "⬜"
            short = a.replace("_otc", "").replace("USD", "")
            row.append(InlineKeyboardButton(f"{icon} {ff(short)}", callback_data=f"block_{a}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="settings")])
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  🚫 {ff("BLOCKED ASSETS")}
│  {ff("Tap to toggle")}
│  𝙱𝚕𝚘𝚌𝚔𝚎𝚍：{fn(str(len(blocked)))}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data == "set_min_payout":
        context.user_data['expecting_min_payout'] = True
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  💵 {ff("SET MIN PAYOUT")}
│  {ff("Send a number (0-100)")}
│  {ff("0 = no minimum")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="settings")]]
        ))
        return

    if data == "set_timezone":
        timezones = ["Asia/Dhaka", "Asia/Kolkata", "Asia/Dubai", "Europe/London", "America/New_York", "Asia/Tokyo"]
        keyboard = []
        current_tz = USER_DATA.get(uid, {}).get("settings", {}).get("timezone", "Asia/Dhaka")
        for tz in timezones:
            icon = "✅" if tz == current_tz else "⬜"
            keyboard.append([InlineKeyboardButton(f"{icon} {ff(tz)}", callback_data=f"tz_{tz}")])
        keyboard.append([InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="settings")])
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  🌍 {ff("SELECT TIMEZONE")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("tz_"):
        tz = data[3:]
        USER_DATA[uid]["settings"]["timezone"] = tz
        save_user_data()
        msg = get_settings_message(user_id)
        await safe_edit_or_reply(query, msg, get_settings_keyboard(user_id))
        return

    if data == "set_language":
        languages = [("🇬🇧 English", "en"), ("🇧🇩 Bangla", "bn"), ("🇮🇳 Hindi", "hi"), ("🇸🇦 Arabic", "ar")]
        keyboard = []
        current_lang = USER_DATA.get(uid, {}).get("settings", {}).get("language", "en")
        for name, code in languages:
            icon = "✅" if code == current_lang else "⬜"
            keyboard.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"lang_{code}")])
        keyboard.append([InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="settings")])
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  🌐 {ff("SELECT LANGUAGE")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("lang_"):
        lang = data[5:]
        USER_DATA[uid]["settings"]["language"] = lang
        save_user_data()
        msg = get_settings_message(user_id)
        await safe_edit_or_reply(query, msg, get_settings_keyboard(user_id))
        return

    # ============ ADMIN PANEL ============
    if data == "admin_panel":
        if not is_admin(user_id):
            await safe_edit_or_reply(query, f"❌ {ff('Admin only')}", InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
            ))
            return
        msg = get_admin_panel_message()
        keyboard = get_admin_panel_keyboard(user_id)
        await safe_edit_or_reply(query, msg, keyboard)
        return

    if data == "toggle_mode":
        if not is_admin(user_id):
            return
        USERS['mode'] = 'private' if USERS.get('mode') == 'public' else 'public'
        save_users()
        msg = get_admin_panel_message()
        await safe_edit_or_reply(query, msg, get_admin_panel_keyboard(user_id))
        return

    if data == "toggle_credit_mode":
        if not is_admin(user_id):
            return
        CONFIG['CREDIT_MODE'] = not CONFIG.get('CREDIT_MODE', False)
        save_config()
        msg = get_admin_panel_message()
        await safe_edit_or_reply(query, msg, get_admin_panel_keyboard(user_id))
        return

    if data == "set_daily_credits":
        if not is_admin(user_id):
            return
        context.user_data['admin_action'] = "set_daily_credits"
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  🎯 {ff("SET DAILY CREDITS")}
│  {ff("Send number (1-100)")}
│  𝙲𝚞𝚛𝚛𝚎𝚗𝚝：{fn(str(CONFIG.get('DAILY_FREE_CREDITS', 5)))}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="admin_panel")]]
        ))
        return

    if data in ["add_user", "rem_user", "ban_user", "unban_user"]:
        if not is_admin(user_id):
            return
        context.user_data['admin_action'] = data
        action_names = {"add_user": "ADD USER", "rem_user": "REMOVE USER", "ban_user": "BAN USER", "unban_user": "UNBAN USER"}
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  👥 {ff(action_names.get(data, data))}
│  {ff("Send user ID")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="admin_panel")]]
        ))
        return

    if data == "list_users":
        if not is_admin(user_id):
            return
        allowed = USERS.get('allowed', [])
        lines = "\n".join(f"  │ 👤 {fn(str(u))}" for u in allowed) if allowed else f"  │ {ff('None')}"
        msg = f"""
╭━━━━━━━【📋】━━━━━━━╮
│  {ff("ALLOWED USERS")}
{lines}
╰━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
        ))
        return

    if data == "ban_list":
        if not is_admin(user_id):
            return
        banned = USERS.get('banned', [])
        lines = "\n".join(f"  │ 🚫 {fn(str(u))}" for u in banned) if banned else f"  │ {ff('None')}"
        msg = f"""
╭━━━━━━━【🚫】━━━━━━━╮
│  {ff("BANNED USERS")}
{lines}
╰━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
        ))
        return

    if data == "admin_list":
        if not is_admin(user_id):
            return
        admins = CONFIG.get("ADMINS", [])
        lines = "\n".join(f"  │ ⚡ {fn(str(a))}" for a in admins) if admins else f"  │ {ff('None')}"
        msg = f"""
╭━━━━━━━【👑】━━━━━━━╮
│  {ff("ADMIN LIST")}
│  👑 𝙾𝚠𝚗𝚎𝚛：{fn(str(OWNER_ID))}
{lines}
╰━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
        ))
        return

    if data == "add_admin":
        if not is_owner(user_id):
            await safe_edit_or_reply(query, f"❌ {ff('Only owner can add admins')}", InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
            ))
            return
        context.user_data['admin_action'] = "add_admin"
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  ➕ {ff("ADD ADMIN")}
│  {ff("Send user ID")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="admin_panel")]]
        ))
        return

    if data == "remove_admin":
        if not is_owner(user_id):
            await safe_edit_or_reply(query, f"❌ {ff('Only owner can remove admins')}", InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰??𝙺", callback_data="admin_panel")]]
            ))
            return
        context.user_data['admin_action'] = "remove_admin"
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  ➖ {ff("REMOVE ADMIN")}
│  {ff("Send user ID")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="admin_panel")]]
        ))
        return

    if data == "broadcast":
        if not is_admin(user_id):
            return
        context.user_data['expecting_broadcast'] = True
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  📨 {ff("BROADCAST")}
│  {ff("Send your message")}
│  {ff("Type /cancel to cancel")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="admin_panel")]]
        ))
        return

    if data == "announce":
        if not is_admin(user_id):
            return
        context.user_data['expecting_announce'] = True
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  📢 {ff("ANNOUNCEMENT")}
│  {ff("Send announcement text")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="admin_panel")]]
        ))
        return

    if data == "search_user":
        if not is_admin(user_id):
            return
        context.user_data['admin_action'] = "search_user"
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  🔍 {ff("SEARCH USER")}
│  {ff("Send user ID")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="admin_panel")]]
        ))
        return

    if data == "set_cooldown":
        if not is_admin(user_id):
            return
        context.user_data['admin_action'] = "set_cooldown"
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  ⏱️ {ff("SET COOLDOWN")}
│  {ff("Send seconds (10-300)")}
│  𝙲𝚞𝚛𝚛𝚎𝚗𝚝：{fn(str(CONFIG.get('SIGNAL_COOLDOWN', 60)))}𝚜
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="admin_panel")]]
        ))
        return

    if data == "set_max_mtg":
        if not is_admin(user_id):
            return
        context.user_data['admin_action'] = "set_max_mtg"
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  📊 {ff("SET MAX MTG LEVEL")}
│  {ff("Send number (0-5)")}
│  𝙲𝚞𝚛𝚛𝚎𝚗𝚝：{fn(str(CONFIG.get('MAX_MTG_LEVEL', 1)))}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="admin_panel")]]
        ))
        return

    if data == "set_interval":
        if not is_admin(user_id):
            return
        intervals = ["1m", "5m", "15m", "30m", "1h"]
        keyboard = []
        current_int = CONFIG.get("API_INTERVAL", "1m")
        for iv in intervals:
            icon = "✅" if iv == current_int else "⬜"
            keyboard.append([InlineKeyboardButton(f"{icon} {ff(iv)}", callback_data=f"interval_{iv}")])
        keyboard.append([InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")])
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  ⏰ {ff("SET INTERVAL")}
│  𝙲𝚞𝚛𝚛𝚎𝚗𝚝：{ff(current_int)}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("interval_"):
        if not is_admin(user_id):
            return
        iv = data[9:]
        CONFIG["API_INTERVAL"] = iv
        save_config()
        msg = get_admin_panel_message()
        await safe_edit_or_reply(query, msg, get_admin_panel_keyboard(user_id))
        return

    if data == "api_settings":
        if not is_admin(user_id):
            return
        msg = f"""
╭━━━━━━━【📡】━━━━━━━╮
│  {ff("API SETTINGS")}
│  📡 𝚄𝚁𝙻：{CONFIG.get('API_BASE_URL', '')}
│  🕯️ 𝙲𝚊𝚗𝚍𝚕𝚎𝚜：{fn(str(CONFIG.get('API_CANDLE_COUNT', 5000)))}
│  ⏰ 𝙸𝚗𝚝𝚎𝚛𝚟𝚊𝚕：{ff(CONFIG.get('API_INTERVAL', '1m'))}
╰━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ CHANGE API URL", callback_data="set_api_url")],
            [InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]
        ]))
        return

    if data == "set_api_url":
        if not is_admin(user_id):
            return
        context.user_data['admin_action'] = "set_api_url"
        current_url = CONFIG.get("API_BASE_URL", "")
        msg = f"""╭━━━━━━━━━━━━━━━━━━━━━━╮
│ ✏️ {ff("CHANGE API URL")}
│
│ {ff("Current URL:")}
│ {current_url}
│
│ {ff("Send the new API base URL")}
│ {ff("Example: https://ravith-trading.up.railway.app")}
│
│ {ff("Send /cancel to cancel")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 CANCEL", callback_data="admin_panel")]
        ]))
        return

    if data == "bot_stats":
        if not is_admin(user_id):
            return
        total_users = len(USER_DATA)
        active_bots = sum(1 for s in USER_TRADING_SESSIONS.values() if s.get('active'))
        total_signals = sum(d.get('signals_received', 0) for d in USER_DATA.values())
        total_wins = sum(get_user_stats(int(u)).get('win', 0) for u in USER_DATA.keys())
        total_losses = sum(get_user_stats(int(u)).get('loss', 0) for u in USER_DATA.keys())
        total_trades = total_wins + total_losses
        overall_acc = (total_wins / total_trades * 100) if total_trades > 0 else 0

        msg = f"""
╔═══════════════════════════════════╗
║      📊 𝙱𝙾𝚃 𝚂𝚃𝙰𝚃𝙸𝚂𝚃𝙸𝙲𝚂          ║
╚═══════════════════════════════════╝

╭━━━━━━━【🤖】━━━━━━━╮
│ 👥 𝚃𝚘𝚝𝚊𝚕 𝚄𝚜𝚎𝚛𝚜：{fn(str(total_users))}
│ 🟢 𝙰𝚌𝚝𝚒𝚟𝚎 𝙱𝚘𝚝𝚜：{fn(str(active_bots))}
│ 📡 𝚃𝚘𝚝𝚊𝚕 𝚂𝚒𝚐𝚗𝚊𝚕𝚜：{fn(str(total_signals))}
╰━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━【📈】━━━━━━━╮
│ ✅ 𝚃𝚘𝚝𝚊𝚕 𝚆𝚒𝚗𝚜：{fn(str(total_wins))}
│ ❌ 𝚃𝚘𝚝𝚊𝚕 𝙻𝚘𝚜𝚜𝚎𝚜：{fn(str(total_losses))}
│ 🎯 𝙾𝚟𝚎𝚛𝚊𝚕𝚕 𝙰𝚌𝚌：{fn(f"{overall_acc:.1f}")}٪
╰━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
        ))
        return

    if data == "global_stats":
        if not is_admin(user_id):
            return
        total_wins = sum(get_user_stats(int(u)).get('win', 0) for u in USER_DATA.keys())
        total_losses = sum(get_user_stats(int(u)).get('loss', 0) for u in USER_DATA.keys())
        total_trades = total_wins + total_losses
        overall_acc = (total_wins / total_trades * 100) if total_trades > 0 else 0
        msg = f"""
╔═══════════════════════════════════╗
║     📊 𝙶𝙻𝙾𝙱𝙰𝙻 𝚂𝚃𝙰𝚃𝙸𝚂𝚃𝙸𝙲𝚂       ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━╮
│ ✅ 𝚃𝚘𝚝𝚊𝚕 𝚆𝚒𝚗𝚜：{fn(str(total_wins))}
│ ❌ 𝚃𝚘𝚝𝚊𝚕 𝙻𝚘𝚜𝚜：{fn(str(total_losses))}
│ 🎯 𝙰𝚌𝚌𝚞𝚛𝚊𝚌𝚢：{fn(f"{overall_acc:.1f}")}٪
│ 📊 𝚃𝚘𝚝𝚊𝚕 𝚃𝚛𝚊𝚍𝚎𝚜：{fn(str(total_trades))}
╰━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
        ))
        return

    if data == "top_traders":
        if not is_admin(user_id):
            return
        traders = []
        for uid_str in USER_DATA.keys():
            s = get_user_stats(int(uid_str))
            w = s.get('win', 0)
            l = s.get('loss', 0)
            t = w + l
            acc = (w / t * 100) if t > 0 else 0
            username = USER_DATA.get(uid_str, {}).get('username', uid_str)
            traders.append((username or uid_str, w, l, acc, t))
        traders.sort(key=lambda x: x[3], reverse=True)
        lines = ""
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, (name, w, l, acc, t) in enumerate(traders[:10]):
            medal = medals[i] if i < len(medals) else f"{fn(str(i+1))}."
            lines += f"│ {medal} {name} — {fn(str(w))}𝚆/{fn(str(l))}𝙻 ({fn(f'{acc:.0f}')}٪)\n"
        if not lines:
            lines = f"│ {ff('No traders yet')}\n"
        msg = f"""
╔═══════════════════════════════════╗
║       🏆 𝚃𝙾𝙿 𝚃𝚁𝙰𝙳𝙴𝚁𝚂            ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━╮
{lines}╰━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
        ))
        return

    if data == "global_log":
        if not is_admin(user_id):
            return
        all_results = []
        for uid_str in USER_DATA.keys():
            s = get_user_stats(int(uid_str))
            for r in s.get('all_results', [])[-5:]:
                r_copy = r.copy()
                r_copy['_user'] = USER_DATA.get(uid_str, {}).get('username', uid_str)
                all_results.append(r_copy)
        all_results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        lines = ""
        for r in all_results[:15]:
            ic = "✅" if r.get('result') == 'WIN' else "❌"
            lines += f"│ {ic} {r.get('_user', '?')} — {fancy_asset_name(r.get('asset', '?'))} {fancy_time(r.get('display_time', ''))}\n"
        if not lines:
            lines = f"│ {ff('No trades yet')}\n"
        msg = f"""
╭━━━━━━━【📜】━━━━━━━╮
│  {ff("GLOBAL LOG (Last 15)")}
{lines}╰━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
        ))
        return

    if data == "reset_all_stats":
        if not is_owner(user_id):
            await safe_edit_or_reply(query, f"❌ {ff('Only owner')}", InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
            ))
            return
        keyboard = [
            [InlineKeyboardButton(f"✅ {ff('YES RESET ALL')}", callback_data="confirm_reset_all"),
             InlineKeyboardButton(f"❌ {ff('CANCEL')}", callback_data="admin_panel")]
        ]
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  ⚠️ {ff("RESET ALL STATS?")}
│  {ff("This cannot be undone!")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data == "confirm_reset_all":
        if not is_owner(user_id):
            return
        USER_STATS.clear()
        save_user_stats()
        msg = f"✅ {ff('All stats reset successfully')}"
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
        ))
        return

    if data == "user_activity":
        if not is_admin(user_id):
            return
        if not USER_DATA:
            msg = f"╭━━━━━━━━━━━━━━━━━━━━╮\n│  {ff('No user activity yet')}\n╰━━━━━━━━━━━━━━━━━━━━╯"
            await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
            ))
            return
        lines = ""
        sorted_users = sorted(USER_DATA.items(), key=lambda x: x[1].get('last_active', ''), reverse=True)
        for uid_str, info in sorted_users[:15]:
            last = info.get('last_active', 'Never')[:16]
            cmds = info.get('commands', 0)
            uname = info.get('username', '')
            display = f"@{uname}" if uname else uid_str
            active_icon = "🟢" if uid_str in [str(k) for k, v in USER_TRADING_SESSIONS.items() if v.get('active')] else "⚪"
            lines += f"│ {active_icon} {display} — 📝{fn(str(cmds))} — {fn(last)}\n"
        msg = f"""
╔═══════════════════════════════════╗
║       👥 𝚄𝚂𝙴𝚁 𝙰𝙲𝚃𝙸𝚅𝙸𝚃𝚈          ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━╮
{lines}╰━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        return

    # ============ BOT CONTROL ============
    if data in ["start_bot", "stop_bot", "restart_bot"]:
        if not is_authorized(user_id):
            await safe_edit_or_reply(query, f"❌ {ff('Not authorized')}", InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
            ))
            return
        if data == "start_bot":
            if session.get('active'):
                msg = f"╭━━━━━━━━━━━━━━━━━━━━╮\n│  ⚠️ {ff('Bot already running!')}\n╰━━━━━━━━━━━━━━━━━━━━╯"
                await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
                ))
                return
            if CONFIG.get("CREDIT_MODE", False) and user_id not in USERS.get("allowed", []) and not is_admin(user_id):
                credits = get_user_credits(user_id)
                if credits <= 0:
                    msg = f"""
╔═══════════════════════════════════╗
║      ⛔ 𝙽𝙾 𝙲𝚁𝙴𝙳𝙸𝚃𝚂              ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━━━╮
│  💳 {ff("You have no credits left.")}
│  📞 {ff("Contact admin or wait for reset.")}
│  🔄 {ff("Next reset at midnight")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
                    await safe_edit_or_reply(query, msg, InlineKeyboardMarkup([
                        [InlineKeyboardButton("📞 𝙲𝙾𝙽𝚃𝙰𝙲𝚃", url=f"https://t.me/{CONFIG.get('BOT_USERNAME','Mahabub_iX').lstrip('@')}")],
                        [InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]
                    ]))
                    return
            session['active'] = True
            session['trading_task'] = asyncio.create_task(trading_loop_for_user(user_id))
            msg = f"""
╔═══════════════════════════════════╗
║      ✅ 𝙱𝙾𝚃 𝚂𝚃𝙰𝚁𝚃𝙴𝙳!            ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━━━╮
│  🤖 {ff("Trading bot is now active")}
│  📡 {ff("Fetching market data...")}
│  🎯 {ff("Analyzing signals...")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
            await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
                [[InlineKeyboardButton("⏹ 𝚂𝚃𝙾𝙿 𝙱𝙾𝚃", callback_data="stop_bot"),
                  InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
            ))

        elif data == "stop_bot":
            if not session.get('active'):
                msg = f"╭━━━━━━━━━━━━━━━━━━━━╮\n│  ⚠️ {ff('Bot already stopped!')}\n╰━━━━━━━━━━━━━━━━━━━━╯"
                await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
                ))
                return
            session['active'] = False
            if session.get('trading_task'):
                session['trading_task'].cancel()
                session['trading_task'] = None
            msg = f"""
╔═══════════════════════════════════╗
║      ⏹ 𝙱𝙾𝚃 𝚂𝚃𝙾𝙿𝙿𝙴𝙳!            ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━━━╮
│  🔴 {ff("Trading bot stopped")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
            await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
                [[InlineKeyboardButton("▶️ 𝚂𝚃𝙰𝚁𝚃 𝙱𝙾𝚃", callback_data="start_bot"),
                  InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
            ))
        return

    # ============ STATUS ============
    if data == "status":
        msg = get_status_message(user_id)
        keyboard = [
            [InlineKeyboardButton("📋 𝙿𝙰𝚁𝚃𝙸𝙰𝙻", callback_data="partial"),
             InlineKeyboardButton("📈 𝚃𝙾𝙳𝙰𝚈", callback_data="today_stats")],
            [InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]
        ]
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data == "partial":
        try:
            await send_partial_summary_for_user(user_id)
            await query.answer("📋 Partial summary sent")
        except Exception as e:
            print(f"Partial error: {e}")
            await safe_edit_or_reply(query, "⚠️ Error sending partial summary.", InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
            ))
        return

    if data == "today_stats":
        today = get_user_statistics(user_id, get_user_today_results(user_id))
        date_str = datetime.now(UTC_PLUS_6).strftime("%d.%m.%Y")
        msg = f"""
╔═══════════════════════════════════╗
║      📈 𝚃𝙾𝙳𝙰𝚈'𝚂 𝚂𝚃𝙰𝚃𝚂           ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━━━╮
│ 📅 𝙳𝚊𝚝𝚎：{fn(date_str)}
│ 📊 𝚃𝚘𝚝𝚊𝚕 𝚃𝚛𝚊𝚍𝚎𝚜：{fn(str(today['total_trades']))}
│ ✅ 𝚆𝚒𝚗𝚜：{fn(str(today['wins']))}
│ ❌ 𝙻𝚘𝚜𝚜𝚎𝚜：{fn(str(today['losses']))}
│ 🎯 𝙰𝚌𝚌𝚞𝚛𝚊𝚌𝚢：{fn(f"{today['accuracy']:.1f}")}٪
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("📋 𝙿𝙰𝚁𝚃𝙸𝙰𝙻", callback_data="partial"),
              InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        return

    if data == "history":
        stats = get_user_stats(user_id)
        results = stats.get('all_results', [])[-20:]
        lines = ""
        for r in reversed(results):
            ic = "✅" if r.get('result') == 'WIN' else "✖️"
            mt = ""
            if r.get('result') == 'WIN' and r.get('mtg_level', 0) > 0:
                sups = {1:'¹', 2:'²', 3:'³'}
                mt = sups.get(r['mtg_level'], str(r['mtg_level']))
            lines += f"│ ⧉ {fancy_time(r.get('display_time', '??'))} - {fancy_asset_name(r.get('asset', '?'))} - {fancy_direction(r.get('direction', '?'))} {ic}{mt}\n"
        if not lines:
            lines = f"│ {ff('No history yet')}\n"
        msg = f"""
╔═══════════════════════════════════╗
║       📜 𝚃𝚁𝙰𝙳𝙴 𝙷𝙸𝚂𝚃𝙾𝚁𝚈          ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━╮
{lines}╰━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        return

    if data == "leaderboard":
        traders = []
        for uid_str in USER_DATA.keys():
            s = get_user_stats(int(uid_str))
            w = s.get('win', 0)
            l = s.get('loss', 0)
            t = w + l
            acc = (w / t * 100) if t > 0 else 0
            username = USER_DATA.get(uid_str, {}).get('username', uid_str)
            traders.append((username or uid_str, w, l, acc, t))
        traders.sort(key=lambda x: x[3], reverse=True)
        lines = ""
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, (name, w, l, acc, t) in enumerate(traders[:10]):
            medal = medals[i] if i < len(medals) else f"{fn(str(i+1))}."
            lines += f"│ {medal} {name} — {fn(str(w))}𝚆/{fn(str(l))}𝙻 ({fn(f'{acc:.0f}')}٪)\n"
        if not lines:
            lines = f"│ {ff('No traders yet')}\n"
        msg = f"""
╔═══════════════════════════════════╗
║       🏆 𝙻𝙴𝙰𝙳𝙴𝚁𝙱𝙾𝙰𝚁𝙳            ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━╮
{lines}╰━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        return

    if data == "reset":
        try:
            stats = get_user_stats(user_id)
            stats['win'] = 0
            stats['loss'] = 0
            stats['all_results'] = []
            stats['pair_wins'] = 0
            stats['pair_losses'] = 0
            stats['streak'] = 0
            stats['best_streak'] = 0
            save_user_stats()
            await query.answer()
        except:
            await query.answer()
        return

    if data == "help":
        msg = get_help_message()
        keyboard = [
            [InlineKeyboardButton("📖 𝙶𝚄𝙸𝙳𝙴", callback_data="guide"),
             InlineKeyboardButton("📞 𝚂𝚄𝙿𝙿𝙾𝚁𝚃", callback_data="support")],
            [InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]
        ]
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data == "guide":
        msg = f"""
╔═══════════════════════════════════╗
║       📖 𝚄𝚂𝙴𝚁 𝙶𝚄𝙸𝙳𝙴              ║
╚═══════════════════════════════════╝

╭━━━━━━━【🔮】━━━━━━━╮
│ {ff("FUTURE CHECKER")}:
│ {ff("1. Paste signals from any bot")}
│ {ff("2. Select MTG level (0 or 1)")}
│ {ff("3. Select Payout Filter")}
│ {ff("4. Select Date (Today/Yesterday)")}
│ {ff("5. Get instant results!")}
╰━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="help")]]
        ))
        return

    if data == "support":
        contact = CONFIG.get("BOT_USERNAME", "@Mahabub_iX")
        contact_clean = contact.lstrip('@')
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│ 📞 {ff("Contact")}: {contact}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"📞 {ff('CONTACT OWNER')}", url=f"https://t.me/{contact_clean}")],
             [InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="help")]]
        ), parse_mode='HTML')
        return

    if data == "tg_connect":
        user_cfg = USER_DATA.get(uid, {})
        enabled = user_cfg.get('telegram_enabled', False)
        chat_id = user_cfg.get('chat_id', ff('Not set'))
        enabled_icon = "✅" if enabled else "❌"
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│ 📡 𝙴𝚡𝚝𝚎𝚛𝚗𝚊𝚕 𝙲𝚑𝚊𝚝：{enabled_icon}
│ 🆔 𝙲𝚑𝚊𝚝 𝙸𝙳：{chat_id}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        keyboard = [
            [InlineKeyboardButton(f"🔄 {ff('TOGGLE EXTERNAL')}", callback_data="toggle_telegram")],
            [InlineKeyboardButton(f"✏️ {ff('SET CHAT ID')}", callback_data="set_chatid")],
            [InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]
        ]
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data == "toggle_telegram":
        USER_DATA[uid]['telegram_enabled'] = not USER_DATA[uid].get('telegram_enabled', False)
        save_user_data()
        is_enabled = USER_DATA[uid]['telegram_enabled']
        icon = "✅" if is_enabled else "❌"
        msg = f"╭━━━━━━━━━━━━━━━━━━━━╮\n│  📡 𝙴𝚡𝚝𝚎𝚛𝚗𝚊𝚕：{icon}\n╰━━━━━━━━━━━━━━━━━━━━╯"
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="tg_connect")]]
        ))
        return

    if data == "set_chatid":
        context.user_data['expecting_chatid'] = True
        msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  ✏️ {ff("SET CHAT ID")}
│  {ff("Send numeric chat ID")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="tg_connect")]]
        ))
        return

    # ============ LIVE PRICE ============
    if data == "live_price":
        msg_lines = f"╭━━━━━━━━━━━━━━━━━━╮\n│  ⏳ {ff('Fetching prices...')}\n╰━━━━━━━━━━━━━━━━━━╯"
        await safe_edit_or_reply(query, msg_lines, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        lines = ""
        for asset in ASSETS[:5]:
            candles = await get_candles(asset, count=5)
            if candles and len(candles) > 0:
                last = candles[-1]
                change = last['close'] - last['open']
                icon = "🟢" if change >= 0 else "🔴"
                close_val = last['close']
                change_val = change
                lines += f"│ {icon} {fancy_asset_name(asset)}：{fn(f'{close_val:.4f}')} ({fn(f'{change_val:+.4f}')})\n"
            else:
                lines += f"│ ⚪ {fancy_asset_name(asset)}：{ff('N/A')}\n"
        msg = f"""
╔═══════════════════════════════════╗
║       💹 𝙻𝙸𝚅𝙴 𝙿𝚁𝙸𝙲𝙴𝚂             ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━╮
{lines}╰━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"🔄 {ff('REFRESH')}", callback_data="live_price"),
              InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        return

    if data == "market_scan":
        msg = f"╭━━━━━━━━━━━━━━━━━━╮\n│  ⏳ {ff('Scanning...')}\n╰━━━━━━━━━━━━━━━━━━╯"
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        current_time = get_current_time()
        signals_found = []
        # need user settings for strategy; use default for scan
        user_settings = USER_DATA.get(uid, {}).get("settings", {})
        for asset in ASSETS[:8]:
            sig = await analyze_and_update(asset, current_time, user_settings)
            if sig:
                signals_found.append(sig)
            await asyncio.sleep(0.2)
        lines = ""
        for s in signals_found:
            dir_icon = "🟢" if s['direction'] == 'CALL' else "🔴"
            lines += f"│ {dir_icon} {fancy_asset_name(s['asset'])} — {fancy_direction(s['direction'])} — {fn(str(int(s.get('payout', 0))))}٪\n"
        if not lines:
            lines = f"│ {ff('No signals found right now')}\n"
        msg = f"""
╔═══════════════════════════════════╗
║       📈 𝙼𝙰𝚁𝙺𝙴𝚃 𝚂𝙲𝙰𝙽             ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━╮
{lines}╰━━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"🔄 {ff('RESCAN')}", callback_data="market_scan"),
              InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        return

    if data == "asset_info":
        keyboard = []
        row = []
        for asset in ASSETS:
            short = asset.replace("_otc", "").replace("USD", "")
            row.append(InlineKeyboardButton(ff(short), callback_data=f"ainfo_{asset}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")])
        msg = f"╭━━━━━━━━━━━━━━━━━━━━╮\n│  🔍 {ff('SELECT ASSET')}\n╰━━━━━━━━━━━━━━━━━━━━╯"
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("ainfo_"):
        asset = data[6:]
        candles = await get_candles(asset, count=50)
        if candles and len(candles) > 0:
            last = candles[-1]
            rsi, ema = calculate_rsi_ema(candles)
            change = last['close'] - last['open']
            msg = f"""
╭━━━━━━━━━━━━━━━━━━━━╮
│ 💰 𝙿𝚛𝚒𝚌𝚎：{fn(f"{last['close']:.5f}")}
│ 💸 𝙿𝚊𝚢𝚘𝚞𝚝：{fn(str(int(last.get('payout', 0))))}٪
│ 📐 𝚁𝚂𝙸：{fn(f"{rsi:.2f}" if rsi else "N/A")}
╰━━━━━━━━━━━━━━━━━━━━╯"""
        else:
            msg = f"╭━━━━━━━━━━╮\n│ ❌ {ff('Failed to fetch data')}\n╰━━━━━━━━━━╯"
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="asset_info")]]
        ))
        return

    if data == "chart_now":
        msg = f"╭━━━━━━━━━━━━━╮\n│  📊 {ff('Generating chart...')}\n╰━━━━━━━━━━━━━╯"
        await safe_edit_or_reply(query, msg)
        asset = ASSETS[0]
        candles = await get_candles(asset, count=60)
        if candles and PIL_AVAILABLE:
            try:
                loop = asyncio.get_running_loop()
                buf = await loop.run_in_executor(None, create_ultimate_dashboard, asset, candles)
                if buf:
                    chat_id = get_user_chat_id(user_id)
                    await BOT_APPLICATION.bot.send_photo(chat_id=chat_id, photo=buf, caption=f"📊 {fancy_asset_name(asset)}", parse_mode='HTML')
            except Exception as e:
                print(f"Chart error: {e}")
        msg = f"╭━━━━━━━━━━╮\n│ ✅ {ff('Chart sent!')}\n╰━━━━━━━━━━╯"
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        return

    if data == "last_signal":
        if session.get('active_signal'):
            sig = session['active_signal']
            msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  📡 {ff("LAST SIGNAL")}
│  💎 {fancy_asset_name(sig['asset'])}
│  {'🟢' if sig['direction']=='CALL' else '🔴'} {fancy_direction(sig['direction'])}
│  🔄 𝙼𝚃𝙶：{fn(str(sig['mtg']))}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
        else:
            msg = f"╭━━━━━━━━━━━━━━━━━━━━╮\n│  📡 {ff('No active signal')}\n╰━━━━━━━━━━━━━━━━━━━━╯"
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        return

    if data == "signal_log":
        stats = get_user_stats(user_id)
        results = stats.get('all_results', [])[-10:]
        lines = ""
        for r in reversed(results):
            ic = "✅" if r.get('result') == 'WIN' else "✖️"
            mt = ""
            if r.get('result') == 'WIN' and r.get('mtg_level', 0) > 0:
                sups = {1:'¹', 2:'²', 3:'³'}
                mt = sups.get(r['mtg_level'], '')
            lines += f"│ ⧉ {fancy_time(r.get('display_time', ''))} - {fancy_asset_name(r.get('asset', ''))} - {fancy_direction(r.get('direction', ''))} {ic}{mt}\n"
        if not lines:
            lines = f"│ {ff('No signals logged')}\n"
        msg = f"""
╭━━━━━━━【📋】━━━━━━━╮
│  {ff("SIGNAL LOG (Last 10)")}
{lines}╰━━━━━━━━━━━━━━━━━━━╯"""
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        return

    if data == "manual_signal":
        keyboard = []
        row = []
        for asset in ASSETS:
            short = asset.replace("_otc", "").replace("USD", "")
            row.append(InlineKeyboardButton(ff(short), callback_data=f"msig_{asset}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")])
        msg = f"╭━━━━━━━━━━━━━━━━━━━━╮\n│  🎰 {ff('SELECT ASSET')}\n╰━━━━━━━━━━━━━━━━━━━━╯"
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("msig_"):
        asset = data[5:]
        current_time = get_current_time()
        user_settings = USER_DATA.get(uid, {}).get("settings", {})
        sig = await analyze_and_update(asset, current_time, user_settings)
        if sig:
            if CONFIG.get("CREDIT_MODE", False) and user_id not in USERS.get("allowed", []) and not is_admin(user_id):
                if get_user_credits(user_id) <= 0:
                    msg = f"⛔ {ff('No credits left!')}"
                    await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
                    ))
                    return
            candles = sig['candles']
            delivered = await send_signal_with_chart(user_id, sig['asset'], sig['direction'],
                                     sig['signal_time'], candles[-1]['close'],
                                     sig.get('payout', 0), candles)
            if delivered and CONFIG.get('CREDIT_MODE',False) and user_id not in USERS.get('allowed',[]) and not is_admin(user_id):
                deduct_credit(user_id,1)
            msg = '✅ Signal and 60-candle chart sent.' if delivered else '⏳ Not sent: active trade, cooldown, expired entry, or chart/delivery unavailable.'
        else:
            msg = f"╭━━━━━━━━━━━━━╮\n│ ❌ {ff('No signal for')} {fancy_asset_name(asset)}\n╰━━━━━━━━━━━━━╯"
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="manual_signal")]]
        ))
        return

    # ============ BACK MAIN ============
    if data == "back_main":
        if is_admin(user_id):
            welcome_msg = get_welcome_message(update.effective_user, True, is_owner(user_id))
            await safe_edit_or_reply(query, welcome_msg, get_owner_keyboard(user_id))
        else:
            welcome_msg = get_welcome_message(update.effective_user, False, False)
            await safe_edit_or_reply(query, welcome_msg, get_main_keyboard(user_id))
        return

    # ============ UNKNOWN ============
    msg = f"╭━━━━━━━━━━╮\n│ ❓ {ff('Unknown option')}\n╰━━━━━━━━━━╯"
    await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
    ))


# ================= FUTURE CHECKER — OPTIMIZED BATCH RESULT CHECKER =================


async def process_future_checker(query, context, user_id):
    parsed_signals = context.user_data.get('future_parsed_signals', [])
    mtg_level = context.user_data.get('future_mtg_level', 0)
    payout_filter = context.user_data.get('future_payout_filter', 0)
    check_date = context.user_data.get('future_check_date', datetime.now(UTC_PLUS_6).date())
    date_mode = context.user_data.get('future_date_mode', 'today')

    if not parsed_signals:
        msg = f"╭━━━━━━━━━━╮\n│ ❌ {ff('No signals to check')}\n╰━━━━━━━━━━╯"
        await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
        ))
        return

    if CONFIG.get("CREDIT_MODE", False) and user_id not in USERS.get("allowed", []) and not is_admin(user_id):
        credits = get_user_credits(user_id)
        if credits < 1:
            msg = f"""
╔═══════════════════════════════════╗
║      ⛔ 𝙸𝙽𝚂𝚄𝙵𝙵𝙸𝙲𝙸𝙴𝙽𝚃 𝙲𝚁𝙴𝙳𝙸𝚃𝚂     ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━━━╮
│  💳 {ff("You need 1 credit but have 0")}
│  🔄 {ff("Please wait for daily reset")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
            await safe_edit_or_reply(query, msg, InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]
            ]))
            return
        if not deduct_credit(user_id, 1):
            msg = f"⛔ {ff('Failed to deduct credits')}"
            await safe_edit_or_reply(query, msg, InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]
            ]))
            return

    date_display = check_date.strftime("%Y-%m-%d")
    date_label = ff("TODAY") if date_mode == "today" else ff("YESTERDAY")

    # Group signals by asset for batch processing
    asset_groups = {}
    for sig in parsed_signals:
        asset = sig['asset']
        if asset not in asset_groups:
            asset_groups[asset] = []
        asset_groups[asset].append(sig)

    total_assets = len(asset_groups)
    total_signals = len(parsed_signals)
    
    # Process each asset group with a single API call per asset
    all_results = []
    
    for asset, signals in asset_groups.items():
        # Batch check all signals for this asset in one API call
        asset_results = await check_signal_result_batch(asset, signals, mtg_level, check_date)
        all_results.extend(asset_results)
        
        # Small delay to avoid rate limits
        await asyncio.sleep(0.2)

    losses = []
    for r in all_results:
        if r.get('result') == 'LOSS' and r.get('checked', False):
            sig_payout = r.get('payout', 0)
            if payout_filter == 0 or sig_payout >= payout_filter:
                losses.append(r)

    context.user_data['loss_signals'] = losses
    context.user_data['loss_ss_date'] = check_date

    date_str = check_date.strftime("%Y.%m.%d")

    # Build result lines - same format as before
    result_lines = ""
    total_wins = 0
    total_losses = 0
    total_checked_final = 0
    skipped_low_payout = 0

    # Sort results by time for display
    sorted_results = sorted(all_results, key=lambda x: x['time'])
    
    for r in sorted_results:
        asset_fancy = fancy_asset_name(r['asset'])
        time_fancy = fancy_time(r['time'])
        dir_fancy = fancy_direction(r['direction'])
        sig_payout = r.get('payout', 0)

        if not r.get('checked', False):
            result_lines += f"⧉ {asset_fancy} - {time_fancy} ⇨ {dir_fancy} ⏳\n"
            continue

        if payout_filter > 0 and sig_payout < payout_filter:
            result_lines += f"⧉ {asset_fancy} - {time_fancy} ⇨ {dir_fancy} 💰{fn(str(int(sig_payout)))}٪\n"
            skipped_low_payout += 1
            continue

        total_checked_final += 1

        if r['result'] == 'WIN':
            total_wins += 1
            mtg_used = r.get('mtg_used', 0)
            if mtg_used > 0:
                sups = {1:'¹', 2:'²', 3:'³'}
                mt_sup = sups.get(mtg_used, str(mtg_used))
                result_lines += f"⧉ {asset_fancy} - {time_fancy} ⇨ {dir_fancy} ✅{mt_sup}\n"
            else:
                result_lines += f"⧉ {asset_fancy} - {time_fancy} ⇨ {dir_fancy} ✅\n"
        elif r['result'] == 'LOSS':
            total_losses += 1
            result_lines += f"⧉ {asset_fancy} - {time_fancy} ⇨ {dir_fancy} ✖️\n"
        elif r['result'] == 'TIE':
            result_lines += f"⧉ {asset_fancy} - {time_fancy} ⇨ {dir_fancy} ➖\n"
        else:
            result_lines += f"⧉ {asset_fancy} - {time_fancy} ⇨ {dir_fancy} ❓\n"

    if not result_lines:
        result_lines = f"{ff('No results available')}\n"

    total = total_wins + total_losses
    acc = (total_wins / total * 100) if total > 0 else 0

    buttons = [[InlineKeyboardButton(f"🔮 {ff('CHECK AGAIN')}", callback_data="future_checker")]]
    if losses:
        buttons[0].append(InlineKeyboardButton(f"📸 {ff('LOSS SS')}", callback_data="loss_ss"))
    buttons.append([InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")])

    # Build final message in exact format
    msg = f"""▰▱▱ {ff("BOT CHECKER")} ▱▱▰
  ┏━━━━━━━━━━━┓
    📆 {date_label} — {fn(date_str)}
  ┗━━━━━━━━━━━┛
━━━━━━━━━━━ • ━━━━━━━━━━━
{result_lines}━━━━━━━━━━━ • ━━━━━━━━━━━
🏆 {ff("Total")} : {fn(str(total_checked_final))}
✅ {ff("Win")}: {fn(str(total_wins))}
❌ {ff("Loss")}: {fn(str(total_losses))}
🎯 {ff("Accuracy")}: {fn(f"{acc:.1f}")}٪
🔄 {ff("MTG")}: {fn(str(mtg_level))}
📅 {ff("Date")}: {date_label} ({fn(date_display)})
━━━━━━━━━━━ • ━━━━━━━━━━━"""

    context.user_data.pop('future_parsed_signals', None)
    context.user_data.pop('future_mtg_level', None)
    context.user_data.pop('future_payout_filter', None)
    context.user_data.pop('expecting_future_signals', None)
    context.user_data.pop('future_check_date', None)
    context.user_data.pop('future_date_mode', None)

    await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(buttons))

# ================= TEXT HANDLER (modified) =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    uid = str(user_id)

    # ============ FUTURE CHECKER INPUT ============
    if context.user_data.get('expecting_future_signals'):
        text = update.message.text.strip()
        if text.startswith('/cancel'):
            context.user_data.pop('expecting_future_signals', None)
            context.user_data.pop('future_parsed_signals', None)
            await update.message.reply_text(f"❌ {ff('Cancelled')}", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
            ))
            return

        parsed = parse_pasted_signals(text)

        if not parsed:
            msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  ❌ {ff("No signals found!")}
│
│  {ff("Make sure format has:")}
│  {ff("ASSET + TIME + DIRECTION")}
│  {ff("Try again!")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(f"🔮 {ff('TRY AGAIN')}", callback_data="future_checker"),
                  InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
            ))
            return

        context.user_data['future_parsed_signals'] = parsed
        context.user_data['expecting_future_signals'] = False

        signal_lines = ""
        for s in parsed:
            asset_fancy = fancy_asset_name(s['asset'])
            time_fancy = fancy_time(s['time'])
            dir_fancy = fancy_direction(s['direction'])
            signal_lines += f"⧉ {asset_fancy} - {time_fancy} ⇨ {dir_fancy}\n"

        msg = f"""
╔═══════════════════════════════════╗
║     🔮 𝚂𝙸𝙶𝙽𝙰𝙻𝚂 𝙵𝙾𝚄𝙽𝙳            ║
╚═══════════════════════════════════╝

╭━━━━━━━━━━━━━━━━━━━━━━╮
│  📡 {ff("Found")} {fn(str(len(parsed)))} {ff("signals")}
╰━━━━━━━━━━━━━━━━━━━━━━╯

━━━━━━━━━━━ • ━━━━━━━━━━━
{signal_lines}━━━━━━━━━━━ • ━━━━━━━━━━━

╭━━━━━━━━━━━━━━━━━━━━━━╮
│  🔄 {ff("SELECT MTG LEVEL")}
│  {ff("0 = No Martingale")}
│  {ff("1 = 1 Step Martingale")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""

        keyboard = [
            [InlineKeyboardButton(f"0️⃣ {ff('0 MTG')}", callback_data="fc_mtg_0"),
             InlineKeyboardButton(f"1️⃣ {ff('1 MTG')}", callback_data="fc_mtg_1")],
            [InlineKeyboardButton("🔙 𝙲𝙰𝙽𝙲𝙴𝙻", callback_data="back_main")]
        ]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Chat ID input
    if context.user_data.get('expecting_chatid'):
        chat_id_str = update.message.text.strip()
        try:
            chat_id_int = int(chat_id_str)
        except ValueError:
            await update.message.reply_text(f"❌ {ff('Invalid ID')}")
            return
        USER_DATA[uid]['chat_id'] = str(chat_id_int)
        USER_DATA[uid]['telegram_enabled'] = True
        save_user_data()
        context.user_data['expecting_chatid'] = False
        msg = f"╭━━━━━━━━━━━━━╮\n│ ✅ {ff('Chat ID set!')}\n│ 🆔 {fn(str(chat_id_int))}\n╰━━━━━━━━━━━━━╯"
        keyboard = get_owner_keyboard(user_id) if is_admin(user_id) else get_main_keyboard(user_id)
        await update.message.reply_text(msg, reply_markup=keyboard)
        return

    # Watermark input
    if context.user_data.get('expecting_watermark'):
        text = update.message.text.strip()
        if len(text) > 20:
            await update.message.reply_text(f"❌ {ff('Max 20 chars')}")
            return
        USER_DATA[uid]['settings']['watermark'] = text
        save_user_data()
        context.user_data['expecting_watermark'] = False
        msg = f"╭━━━━━━━━━━━━━╮\n│ ✅ {ff('Watermark updated!')}\n│ 💧 {ff(text)}\n╰━━━━━━━━━━━━━╯"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="settings")]]
        ))
        return

    # Contact input
    if context.user_data.get('expecting_contact'):
        text = update.message.text.strip()
        if not text.startswith('@'):
            text = '@' + text
        USER_DATA[uid]['settings']['contact'] = text
        save_user_data()
        context.user_data['expecting_contact'] = False
        msg = f"╭━━━━━━━━━━━━━╮\n│ ✅ {ff('Contact updated!')}\n│ 📞 {text}\n╰━━━━━━━━━━━━━╯"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="settings")]]
        ))
        return

    # Min payout input
    if context.user_data.get('expecting_min_payout'):
        text = update.message.text.strip()
        try:
            val = int(text)
            if 0 <= val <= 100:
                USER_DATA[uid]['settings']['min_payout'] = val
                save_user_data()
                context.user_data['expecting_min_payout'] = False
                msg = f"╭━━━━━━━━━━━━━╮\n│ ✅ {ff('Min payout set!')}\n│ 💵 {fn(str(val))}٪\n╰━━━━━━━━━━━━━╯"
                await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="settings")]]
                ))
                return
            else:
                await update.message.reply_text(f"❌ {ff('Must be 0-100')}")
                return
        except:
            await update.message.reply_text(f"❌ {ff('Invalid number')}")
            return

    # Footer text input
    if context.user_data.get('expecting_footer_text'):
        text = update.message.text.strip()
        if len(text) > 30:
            await update.message.reply_text(f"❌ {ff('Max 30 chars')}")
            return
        USER_DATA[uid]['settings']['footer_text'] = text
        save_user_data()
        context.user_data['expecting_footer_text'] = False
        msg = f"╭━━━━━━━━━━━━━╮\n│ ✅ {ff('Footer text updated!')}\n│ ✏️ {fb(text)}\n╰━━━━━━━━━━━━━╯"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="settings")]]
        ))
        return

    # Broadcast input
    if context.user_data.get('expecting_broadcast'):
        if not is_admin(user_id):
            context.user_data.pop('expecting_broadcast', None)
            return
        text = update.message.text.strip()
        if text.startswith('/cancel'):
            context.user_data.pop('expecting_broadcast', None)
            await update.message.reply_text(f"❌ {ff('Cancelled')}", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
            ))
            return
        sent = 0
        for uid_str in USER_DATA.keys():
            try:
                await BOT_APPLICATION.bot.send_message(chat_id=uid_str, text=text, parse_mode=constants.ParseMode.HTML)
                sent += 1
                await asyncio.sleep(0.1)
            except:
                pass
        context.user_data.pop('expecting_broadcast', None)
        msg = f"╭━━━━━━━━━━━━━╮\n│ ✅ {ff('Broadcast sent!')}\n│ 📨 {fn(str(sent))} {ff('users')}\n╰━━━━━━━━━━━━━╯"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
        ))
        return

    # Announce input
    if context.user_data.get('expecting_announce'):
        if not is_admin(user_id):
            context.user_data.pop('expecting_announce', None)
            return
        text = update.message.text.strip()
        if text.startswith('/cancel'):
            context.user_data.pop('expecting_announce', None)
            await update.message.reply_text(f"❌ {ff('Cancelled')}", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
            ))
            return
        announce_msg = f"""
╔═══════════════════════════════════╗
║       📢 𝙰𝙽𝙽𝙾𝚄𝙽𝙲𝙴𝙼𝙴𝙽𝚃            ║
╚═══════════════════════════════════╝

{text}

╔═══════════════════════════════════╗
║     ✦ 𝗥𝗔𝗩𝗜𝗧𝗛 𝗔𝗜 𝗣𝗥𝗢 ✦          ║
╚═══════════════════════════════════╝"""
        sent = 0
        for uid_str in USER_DATA.keys():
            try:
                await BOT_APPLICATION.bot.send_message(chat_id=uid_str, text=announce_msg, parse_mode=constants.ParseMode.HTML)
                sent += 1
                await asyncio.sleep(0.1)
            except:
                pass
        context.user_data.pop('expecting_announce', None)
        msg = f"╭━━━━━━━━━━━━━╮\n│ ✅ {ff('Announced!')}\n│ 📢 {fn(str(sent))} {ff('users')}\n╰━━━━━━━━━━━━━╯"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
        ))
        return

    # Admin actions
    action = context.user_data.get('admin_action')
    if action and is_admin(user_id):
        text = update.message.text.strip()
        if text.startswith('/cancel'):
            context.user_data.pop('admin_action', None)
            await update.message.reply_text(f"❌ {ff('Cancelled')}", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
            ))
            return

        if action == "set_api_url":
            candidate = text.strip().rstrip("/")
            parsed = urlparse(candidate)
            if (parsed.scheme not in ("http", "https") or not parsed.netloc
                    or not parsed.hostname or any(ch.isspace() for ch in candidate)):
                await update.message.reply_text(
                    f"❌ {ff('Invalid URL. Use a complete http:// or https:// URL.')}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 CANCEL", callback_data="admin_panel")]
                    ])
                )
                return

            CONFIG["API_BASE_URL"] = candidate
            if save_config():
                context.user_data.pop('admin_action', None)
                msg = f"✅ {ff('API URL updated and saved!')}\\n\\n📡 {candidate}"
            else:
                msg = f"❌ {ff('Could not save config. Please try again.')}"
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 ADMIN PANEL", callback_data="admin_panel")]
            ]))
            return

        if action == "search_user":
            try:
                search_uid = int(text)
            except:
                await update.message.reply_text(f"❌ {ff('Invalid ID')}")
                return
            search_uid_str = str(search_uid)
            if search_uid_str in USER_DATA:
                info = USER_DATA[search_uid_str]
                s = get_user_stats(search_uid)
                w, l = s.get('win', 0), s.get('loss', 0)
                t = w + l
                acc = (w / t * 100) if t > 0 else 0
                msg = f"""
╭━━━━━━━━━━━━━━━━━━━━╮
│ 🔍 𝚄𝚜𝚎𝚛：{fn(search_uid_str)}
│ 📛 𝙽𝚊𝚖𝚎：{info.get('username', ff('Unknown'))}
│ ✅ 𝚆𝚒𝚗𝚜：{fn(str(w))}
│ ❌ 𝙻𝚘𝚜𝚜：{fn(str(l))}
│ 🎯 𝙰𝚌𝚌：{fn(f"{acc:.1f}")}٪
╰━━━━━━━━━━━━━━━━━━━━╯"""
            else:
                msg = f"╭━━━━━━━━━━╮\n│ ❌ {ff('User not found')}\n╰━━━━━━━━━━╯"
            context.user_data.pop('admin_action', None)
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
            ))
            return

        if action == "set_cooldown":
            try:
                val = int(text)
                if 10 <= val <= 300:
                    CONFIG['SIGNAL_COOLDOWN'] = val
                    save_config()
                    msg = f"✅ {ff('Cooldown set!')} {fn(str(val))}𝚜"
                else:
                    msg = f"❌ {ff('Must be 10-300')}"
            except:
                msg = f"❌ {ff('Invalid number')}"
            context.user_data.pop('admin_action', None)
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
            ))
            return

        if action == "set_max_mtg":
            try:
                val = int(text)
                if 0 <= val <= 5:
                    CONFIG['MAX_MTG_LEVEL'] = val
                    save_config()
                    msg = f"✅ {ff('MTG Level set!')} {fn(str(val))}"
                else:
                    msg = f"❌ {ff('Must be 0-5')}"
            except:
                msg = f"❌ {ff('Invalid number')}"
            context.user_data.pop('admin_action', None)
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
            ))
            return

        if action == "add_admin":
            if not is_owner(user_id):
                context.user_data.pop('admin_action', None)
                return
            try:
                target_uid = int(text)
            except:
                await update.message.reply_text(f"❌ {ff('Invalid ID')}")
                return
            if target_uid in CONFIG.get("ADMINS", []):
                msg = f"⚠️ {ff('Already admin')}"
            else:
                CONFIG.setdefault("ADMINS", []).append(target_uid)
                save_config()
                msg = f"✅ {ff('Admin added!')} {fn(str(target_uid))}"
            context.user_data.pop('admin_action', None)
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
            ))
            return

        if action == "remove_admin":
            if not is_owner(user_id):
                context.user_data.pop('admin_action', None)
                return
            try:
                target_uid = int(text)
            except:
                await update.message.reply_text(f"❌ {ff('Invalid ID')}")
                return
            if target_uid == OWNER_ID:
                msg = f"❌ {ff('Cannot remove owner')}"
            elif target_uid in CONFIG.get("ADMINS", []):
                CONFIG["ADMINS"].remove(target_uid)
                save_config()
                msg = f"✅ {ff('Admin removed!')} {fn(str(target_uid))}"
            else:
                msg = f"⚠️ {ff('Not an admin')}"
            context.user_data.pop('admin_action', None)
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
            ))
            return

        if action == "set_daily_credits":
            try:
                val = int(text)
                if 1 <= val <= 100:
                    CONFIG['DAILY_FREE_CREDITS'] = val
                    save_config()
                    msg = f"✅ {ff('Daily credits set!')} {fn(str(val))}"
                else:
                    msg = f"❌ {ff('Must be 1-100')}"
            except:
                msg = f"❌ {ff('Invalid number')}"
            context.user_data.pop('admin_action', None)
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
            ))
            return

        # User management actions
        try:
            target_uid = int(text)
        except:
            await update.message.reply_text(f"❌ {ff('Invalid ID')}")
            return

        if action == "add_user":
            if target_uid in USERS.get('allowed', []):
                msg = f"⚠️ {ff('Already allowed')}"
            else:
                USERS.setdefault('allowed', []).append(target_uid)
                if target_uid in USERS.get('banned', []):
                    USERS['banned'].remove(target_uid)
                save_users()
                msg = f"✅ {ff('User added!')} {fn(str(target_uid))}"
        elif action == "rem_user":
            if target_uid in USERS.get('allowed', []):
                USERS['allowed'].remove(target_uid)
                save_users()
                msg = f"✅ {ff('User removed!')} {fn(str(target_uid))}"
            else:
                msg = f"⚠️ {ff('Not in list')}"
        elif action == "ban_user":
            if target_uid in USERS.get('banned', []):
                msg = f"⚠️ {ff('Already banned')}"
            else:
                USERS.setdefault('banned', []).append(target_uid)
                if target_uid in USERS.get('allowed', []):
                    USERS['allowed'].remove(target_uid)
                save_users()
                msg = f"🚫 {ff('User banned!')} {fn(str(target_uid))}"
        elif action == "unban_user":
            if target_uid in USERS.get('banned', []):
                USERS['banned'].remove(target_uid)
                save_users()
                msg = f"✅ {ff('User unbanned!')} {fn(str(target_uid))}"
            else:
                msg = f"⚠️ {ff('Not banned')}"
        else:
            msg = f"❓ {ff('Unknown action')}"

        context.user_data.pop('admin_action', None)
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="admin_panel")]]
        ))
        return

    # Default response
    msg = f"""
╭━━━━━━━━━━━━━━━━━━━━━━╮
│  💡 {ff("Please use the buttons")}
│  {ff("Send /start to begin")}
╰━━━━━━━━━━━━━━━━━━━━━━╯"""
    await update.message.reply_text(msg)

# ================= MAIN =================
# ================= REVERSE + TREND PRO / deterministic OHLC engine =================
# Real feed only. No random signals, filler candles, or estimated win probabilities.
# API timestamps must identify the OPEN of each 1-minute candle.
from html import escape as html_escape
from collections import OrderedDict

STRATEGY_LABELS = {
    'REVERSE_TREND_PRO': 'Reverse + Trend PRO',
    'SUPPORT_RESISTANCE': 'Level Rejection Only',
    'RSI_REVERSE': 'Confirmed Reversal Only',
    'EMA_TREND': 'Trend Pullback Only',
    'STRONG_SIGNAL': 'Strict Confluence',
}
_FEED_CACHE = {}
_FEED_LOCKS = {}
_SIGNAL_SNAPSHOTS = OrderedDict()
_DELIVERY_LOCKS = {}
_RESULT_LOCKS = {}


def compute_rsi(closes, period=14):
    """Wilder RSI, aligned to the candle being measured (including flat prices)."""
    out = [None] * len(closes)
    if len(closes) <= period:
        return out
    changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gain = sum(max(x, 0) for x in changes[:period]) / period
    loss = sum(max(-x, 0) for x in changes[:period]) / period
    def value(g, l):
        return 50.0 if g == l == 0 else 100.0 if l == 0 else 100 - 100/(1+g/l)
    out[period] = value(gain, loss)
    for i in range(period+1, len(closes)):
        gain = (gain*(period-1) + max(changes[i-1], 0))/period
        loss = (loss*(period-1) + max(-changes[i-1], 0))/period
        out[i] = value(gain, loss)
    return out


def calculate_rsi_ema(candles):
    rows=clean_ohlc(candles,get_current_time(),True)
    prices=[c['close'] for c in rows]
    return (compute_rsi(prices,14)[-1] if prices else None,
            compute_ema(prices,20)[-1] if prices else None)


def clean_ohlc(candles, now=None, closed_only=False):
    """Reject corrupt/duplicate rows and never silently reconstruct missing candles."""
    rows = {}
    for source in candles or []:
        try:
            c = dict(source)
            dt = c['dt']
            if not isinstance(dt, datetime) or dt.tzinfo is None or dt.second or dt.microsecond:
                continue
            vals = [float(c[k]) for k in ('open', 'high', 'low', 'close')]
            if not all(math.isfinite(x) and x > 0 for x in vals):
                continue
            o, h, l, cl = vals
            if h < max(o, cl) or l > min(o, cl) or h < l:
                continue
            if closed_only and dt + timedelta(minutes=1) > now:
                continue
            c.update(dict(zip(('open', 'high', 'low', 'close'), vals)))
            rows[dt] = c
        except (TypeError, KeyError, ValueError, OverflowError):
            continue
    return [rows[k] for k in sorted(rows)]


def contiguous(candles, count):
    tail = candles[-count:]
    return len(tail) == count and all(
        (tail[i]['dt']-tail[i-1]['dt']).total_seconds() == 60
        for i in range(1, len(tail)))


async def fetch_candles_from_api(asset, count=None, interval=None):
    """Read only OHLC/payout. API's own signal field is deliberately ignored."""
    count = int(count or CONFIG.get('API_CANDLE_COUNT', 240))
    interval = interval or CONFIG.get('API_INTERVAL', '1m')
    base = os.getenv('API_BASE_URL') or CONFIG.get('API_BASE_URL', '')
    if not base or interval != '1m':
        logging.warning('A working API_BASE_URL and API_INTERVAL=1m are required')
        return None
    key = (asset, count, interval)
    async with _FEED_LOCKS.setdefault(key, asyncio.Lock()):
        cached = _FEED_CACHE.get(key)
        if cached and time.monotonic()-cached[0] < 3:
            return [dict(c) for c in cached[1]]
        timeout = aiohttp.ClientTimeout(total=12)
        for attempt in range(2):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as client:
                    async with client.get(base, params={'Pair': asset, 'Candle': count, 'Time': interval}) as response:
                        response.raise_for_status()
                        payload = await response.json(content_type=None)
                raw = payload.get('data', []) if isinstance(payload, dict) else payload
                if not isinstance(raw, list):
                    return None
                tz = pytz.timezone(CONFIG.get('API_TIMEZONE', 'Asia/Dhaka'))
                rows = []
                for item in raw:
                    try:
                        stamp = item.get('time', item.get('timestamp'))
                        if isinstance(stamp, (float, int)) or (isinstance(stamp, str) and stamp.isdigit()):
                            stamp = float(stamp)
                            if stamp > 1e12:
                                stamp /= 1000
                            dt = datetime.fromtimestamp(stamp, tz=pytz.utc)
                        else:
                            dt = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
                            if dt.tzinfo is None:
                                dt = tz.localize(dt)
                        c = {k: float(item[k]) for k in ('open', 'high', 'low', 'close')}
                        payout = float(item.get('payout', 0) or 0)
                        c.update(dt=dt.astimezone(UTC_PLUS_6), payout=payout if math.isfinite(payout) else 0,
                                 volume=float(item.get('volume', 0) or 0))
                        rows.append(c)
                    except (ValueError, TypeError, KeyError, OverflowError):
                        continue
                rows = clean_ohlc(rows)
                if rows:
                    _FEED_CACHE[key] = (time.monotonic(), rows)
                    return [dict(c) for c in rows]
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
                logging.warning('Feed unavailable for %s: %s', asset, exc)
                if not attempt:
                    await asyncio.sleep(.4)
        return None


def analyze_api_candles(candles, strategy='REVERSE_TREND_PRO', now=None):
    """Strict pattern gates; quality is a checklist score, NOT a win probability.

    Reversal: an established level + a sweep/reclaim + pin/engulf confirmation
    + RSI exhaustion/recovery + incoming momentum; reject strong counter-trends.
    Trend: EMA20/50 alignment & slope + efficient structure + pullback touch
    + reclaim + directional close + RSI momentum + room before the next level.
    Both candidates at once => WAIT. No pattern => WAIT, never forced entries.
    """
    now = now or get_current_time()
    c = clean_ohlc(candles, now, True)
    if not contiguous(c, 100):
        return None
    c = c[-240:]
    o = [x['open'] for x in c]; h = [x['high'] for x in c]
    l = [x['low'] for x in c]; p = [x['close'] for x in c]
    tr = [max(h[i]-l[i], abs(h[i]-p[i-1]), abs(l[i]-p[i-1])) for i in range(1, len(c))]
    atr = sum(tr[-14:])/14
    if atr <= 0 or atr/p[-1] < float(CONFIG.get('MIN_ATR_RATIO', .00001)):
        return None
    span = h[-1]-l[-1]; body = abs(p[-1]-o[-1])
    if span <= 0 or body/span < .18 or span > 2.4*atr:
        return None
    # Reject shocks and substantially abnormal volatility on the most recent bars.
    baseline = sum(tr[-44:-14])/30
    if baseline <= 0 or atr/baseline > 2.0 or max(tr[-3:]) > 3.2*atr:
        return None
    e20 = compute_ema(p, 20); e50 = compute_ema(p, 50)
    rsi = compute_rsi(p, 14)
    r, prev_r = rsi[-1], rsi[-2]
    slope = (e20[-1]-e20[-6])/atr
    separation = abs(e20[-1]-e50[-1])/atr
    traveled = sum(abs(p[i]-p[i-1]) for i in range(len(p)-12, len(p)))
    efficiency = abs(p[-1]-p[-13])/traveled if traveled else 0
    bullish = p[-1] > o[-1]; bearish = p[-1] < o[-1]
    lower_wick = min(o[-1], p[-1])-l[-1]
    upper_wick = h[-1]-max(o[-1], p[-1])
    bull_pin = bullish and lower_wick >= body*1.7 and (p[-1]-l[-1])/span >= .68
    bear_pin = bearish and upper_wick >= body*1.7 and (h[-1]-p[-1])/span >= .68
    bull_engulf = bullish and p[-2] < o[-2] and o[-1] <= p[-2] and p[-1] >= o[-2]
    bear_engulf = bearish and p[-2] > o[-2] and o[-1] >= p[-2] and p[-1] <= o[-2]
    # Reference levels EXCLUDE the setup and the confirming candle.
    support = min(l[-42:-2]); resistance = max(h[-42:-2])
    level_window = c[-42:-2]
    support_touches = sum(abs(x['low']-support) <= .35*atr for x in level_window)
    resistance_touches = sum(abs(x['high']-resistance) <= .35*atr for x in level_window)
    candidates = []
    def add(side, mode, pattern, tests):
        if all(ok for _, ok in tests):
            candidates.append({'direction': side, 'mode': mode, 'pattern': pattern,
                               'evidence': [label for label, _ in tests]})
    reverse_enabled = strategy in ('REVERSE_TREND_PRO','SUPPORT_RESISTANCE','RSI_REVERSE','STRONG_SIGNAL')
    trend_enabled = strategy in ('REVERSE_TREND_PRO','EMA_TREND','STRONG_SIGNAL')
    if reverse_enabled:
        add('CALL', 'REVERSAL', 'Support sweep + bullish confirmation', [
            ('Established support', support_touches >= 2),
            ('Liquidity sweep and reclaim', min(l[-2:]) < support-.05*atr and p[-1] > support+.08*atr),
            ('Pin bar or engulfing', bull_pin or bull_engulf),
            ('RSI exhaustion/recovery', min(rsi[-5:-1]) <= 38 and r > prev_r and r < 58),
            ('Incoming decline', p[-3] < p[-7]),
            ('No extreme counter-trend', not(slope < -.85 and separation > 1.2)),
            ('Room to resistance', resistance-p[-1] >= .9*atr),
        ])
        add('PUT', 'REVERSAL', 'Resistance sweep + bearish confirmation', [
            ('Established resistance', resistance_touches >= 2),
            ('Liquidity sweep and reclaim', max(h[-2:]) > resistance+.05*atr and p[-1] < resistance-.08*atr),
            ('Pin bar or engulfing', bear_pin or bear_engulf),
            ('RSI exhaustion/recovery', max(rsi[-5:-1]) >= 62 and r < prev_r and r > 42),
            ('Incoming advance', p[-3] > p[-7]),
            ('No extreme counter-trend', not(slope > .85 and separation > 1.2)),
            ('Room to support', p[-1]-support >= .9*atr),
        ])
    if trend_enabled:
        prior_lows = l[-4:-1]; prior_highs = h[-4:-1]
        obstacles_up = [x for x in h[-42:-4] if x > p[-1]]
        obstacles_down = [x for x in l[-42:-4] if x < p[-1]]
        add('CALL', 'TREND', 'Bullish EMA pullback + reclaim', [
            ('EMA20 above EMA50', e20[-1] > e50[-1] and separation >= .30),
            ('Positive EMA slope', slope >= .20),
            ('Directional efficiency', efficiency >= .30),
            ('Pullback reached EMA20', any(l[i] <= e20[i]+.20*atr and p[i] >= e50[i] for i in range(len(c)-4,len(c)-1))),
            ('Bullish reclaim confirmation', bullish and p[-1] > e20[-1] and p[-1] > h[-2] and body/span >= .50),
            ('Momentum not exhausted', 52 <= r <= 68 and r > prev_r),
            ('Higher low structure', min(prior_lows) > min(l[-16:-4])),
            ('Not extended', 0 < (p[-1]-e20[-1])/atr <= 1.35),
            ('Room before overhead level', not obstacles_up or min(obstacles_up)-p[-1] >= .65*atr),
        ])
        add('PUT', 'TREND', 'Bearish EMA pullback + reclaim', [
            ('EMA20 below EMA50', e20[-1] < e50[-1] and separation >= .30),
            ('Negative EMA slope', slope <= -.20),
            ('Directional efficiency', efficiency >= .30),
            ('Pullback reached EMA20', any(h[i] >= e20[i]-.20*atr and p[i] <= e50[i] for i in range(len(c)-4,len(c)-1))),
            ('Bearish reclaim confirmation', bearish and p[-1] < e20[-1] and p[-1] < l[-2] and body/span >= .50),
            ('Momentum not exhausted', 32 <= r <= 48 and r < prev_r),
            ('Lower high structure', max(prior_highs) < max(h[-16:-4])),
            ('Not extended', 0 < (e20[-1]-p[-1])/atr <= 1.35),
            ('Room before lower level', not obstacles_down or p[-1]-max(obstacles_down) >= .65*atr),
        ])
    if len(candidates) != 1:
        return None
    result = candidates[0]
    if strategy == 'STRONG_SIGNAL' and (efficiency < .42 or body/span < .55):
        return None
    # Deterministic ranking, deliberately not called confidence/accuracy.
    quality = min(95, round(70+min(body/span, .8)*10+min(efficiency,.8)*10+min(separation,1)*5))
    result.update(strategy=strategy, quality=quality, latest_candle=c[-1], candles=c,
                  payout=float(c[-1].get('payout', 0) or 0),
                  indicators={'atr': atr, 'rsi': r, 'ema20': e20[-1], 'ema50': e50[-1],
                              'support': support, 'resistance': resistance, 'efficiency': efficiency})
    return result


async def analyze_and_update(asset, current_time, user_settings):
    candles = await get_candles(asset, count=240)
    now = get_current_time()  # Fetch may have crossed a minute boundary.
    result = analyze_api_candles(candles, user_settings.get('strategy','REVERSE_TREND_PRO'), now)
    if not result:
        return None
    last_dt = result['latest_candle']['dt']
    if (round_to_minute(now)-last_dt).total_seconds() != 60:
        return None
    # Inform ahead of next minute, NEVER enter an already-open candle.
    entry = round_to_minute(now)+timedelta(minutes=1)
    if (entry-now).total_seconds() < int(CONFIG.get('MIN_ENTRY_LEAD_SECONDS', 12)):
        return None
    if result['payout'] < float(user_settings.get('min_payout',0) or 0):
        return None
    if asset in user_settings.get('blocked_assets', []):
        return None
    preferred = user_settings.get('preferred_assets', [])
    if preferred and asset not in preferred:
        return None
    side = user_settings.get('signal_type','all').lower()
    if side in ('call','put','call_only','put_only') and side.split('_')[0].upper() != result['direction']:
        return None
    if side == 'otc' and not asset.endswith('_otc'):
        return None
    if side == 'real' and asset.endswith('_otc'):
        return None
    return {**result, 'asset': asset, 'signal_time': int(entry.timestamp()), 'signal_dt': entry,
            'mtg': 0, 'setup_id': f"{asset}:{int(last_dt.timestamp())}:{result['direction']}",
            'snapshot': [dict(c) for c in result['candles'][-60:]]}


# ================= Unified 60-candle chart / no generated market data =================
def _chart_font(size, bold=False):
    for path in ([ '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' ] if bold else
                 [ '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf' ]) + ['DejaVuSans.ttf','arial.ttf']:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            pass
    return ImageFont.load_default()


def render_pro_chart(asset, candles, context=None):
    """Render the SAME frozen 60-candle plot for signal and result.
    Outcome information lives below the plot: market history is not rewritten.
    """
    if not PIL_AVAILABLE:
        raise RuntimeError('Pillow is required for chart delivery')
    rows = clean_ohlc(candles)[-60:]
    if not contiguous(rows, 60):
        raise ValueError('Exactly 60 consecutive authentic candles are required')
    ctx = context or {}
    W, H = 1600, 1060
    img = Image.new('RGB', (W,H), '#090e1a')
    d = ImageDraw.Draw(img)
    text, muted, green, red = '#e7edf7','#8697b3','#25d0a0','#ff647e'
    accent = green if ctx.get('direction') == 'CALL' else red if ctx.get('direction') == 'PUT' else '#70a9ff'
    def label(x,y,s,size=20,color=text,bold=False):
        d.text((x,y),str(s),font=_chart_font(size,bold),fill=color)
    d.rounded_rectangle((24,24,1576,1036), radius=24, fill='#101827', outline='#26344b',width=2)
    label(55,47, str(ctx.get('brand','RAVITH AI PRO'))[:42], 27, text, True)
    label(55,89,'PRICE ACTION TERMINAL  /  REAL OHLC  /  1 MINUTE',16,muted)
    label(920,48,asset.replace('_otc',' OTC'),30,text,True)
    label(920,91,'60 CANDLES  |  CLOSED DATA  |  Asia/Dhaka',16,muted)
    d.line((55,129,1545,129),fill='#26344b',width=2)
    direction = ctx.get('direction','OBSERVE')
    label(55,151,direction,30,accent,True)
    mode = ctx.get('mode','MARKET VIEW')
    label(290,156,STRATEGY_LABELS.get(ctx.get('strategy'), 'Reverse + Trend PRO')+'  /  '+mode,22)
    entry_dt = ctx.get('entry_dt')
    label(1080,157,'ENTRY '+(entry_dt.strftime('%H:%M:%S') if entry_dt else '--:--:--'),24,accent,True)
    x1,y1,x2,y2 = 68,232,1400,701
    highs=[c['high'] for c in rows]; lows=[c['low'] for c in rows]; closes=[c['close'] for c in rows]
    lo,hi = min(lows),max(highs)
    padding = max((hi-lo)*.12, hi*.00001)
    lo-=padding; hi+=padding
    def yy(v): return y2-(v-lo)/(hi-lo)*(y2-y1)
    step=(x2-x1)/60
    def xx(i): return x1+step*(i+.5)
    for j in range(6):
        y=y1+(y2-y1)*j/5
        d.line((x1,y,x2,y),fill='#1b293d',width=1)
        label(1413,y-10,f'{hi-(hi-lo)*j/5:.6g}',17,muted)
    for i in range(0,60,10):
        x=xx(i)
        d.line((x,y1,x,y2),fill='#162237',width=1)
        label(x-22,y2+13,rows[i]['dt'].strftime('%H:%M'),15,muted)
    support=min(lows[:-2]); resistance=max(highs[:-2])
    for value,color in ((support,'#274f4a'),(resistance,'#573546')):
        y=yy(value)
        for x in range(x1,x2,16):
            d.line((x,y,min(x+8,x2),y),fill=color,width=1)
    for period,color in ((20,'#60a5fa'),(50,'#be9cff')):
        points=[(xx(i),yy(v)) for i,v in enumerate(compute_ema(closes,period)) if v is not None]
        if len(points)>1:
            d.line(points,fill=color,width=2)
    for i,c in enumerate(rows):
        x=xx(i); color=green if c['close']>=c['open'] else red
        d.line((x,yy(c['high']),x,yy(c['low'])),fill=color,width=2)
        top,bot=sorted((yy(c['open']),yy(c['close'])))
        d.rectangle((int(x-6),int(top),int(x+6),max(int(bot),int(top)+2)),fill=color)
    last_y=yy(closes[-1])
    d.ellipse((xx(59)-4,last_y-4,xx(59)+4,last_y+4),fill='#ffffff')
    label(68,749,'EMA 20',16,'#60a5fa'); label(185,749,'EMA 50',16,'#be9cff')
    label(316,749,'Muted levels: prior support / resistance',16,muted)
    label(1040,749,'REFERENCE '+f'{closes[-1]:.7g}',18,text,True)
    d.rounded_rectangle((55,791,1545,982),radius=15,fill='#0b1320',outline='#26344b')
    status=ctx.get('status','SIGNAL' if entry_dt else 'CHART')
    status_color=green if status=='WIN' else red if status=='LOSS' else '#70a9ff'
    label(78,809,status,30,status_color,True)
    pattern=str(ctx.get('pattern','Waiting for a confirmed setup'))[:95]
    label(330,816,pattern,20,text,True)
    if status in ('WIN','LOSS','TIE','UNKNOWN'):
        result_text=f"Settled stage: {ctx.get('mtg',0)}  |  Entry: {ctx.get('entry_price','--')}  |  Close: {ctx.get('exit_price','--')}"
        label(78,865,result_text[:118],21)
        label(78,907,'Original signal snapshot preserved. Result is from the entry candle, not a broker execution receipt.',17,muted)
    else:
        evidence=ctx.get('evidence',[])
        detail=' / '.join(evidence[:3]) if evidence else 'No synthetic candles. No forced signals. Insufficient data means WAIT.'
        label(78,865,detail[:116],19,muted)
        q=ctx.get('quality')
        label(78,907,('SETUP QUALITY '+str(q)+'/100  (rule score, not win probability)' if q is not None else 'Closed-candle analysis only'),17,muted)
    label(55,1002,'Research signal only. No guaranteed outcome. Feed-based results may differ from actual fills.',16,muted)
    buf=BytesIO(); img.save(buf,format='PNG'); buf.seek(0); buf.name='chart_60.png'
    return buf


def create_ultimate_dashboard(pair, candles):
    return render_pro_chart(pair, candles)


async def generate_signal_chart(asset, target_dt, direction, size=800, user_id=None, mtg_level=0):
    candles=clean_ohlc(await get_candles(asset,count=5000),get_current_time(),True)
    saved=_SIGNAL_SNAPSHOTS.get(_snapshot_key(user_id,asset,int(target_dt.timestamp()))) if user_id is not None else None
    if saved:
        history=saved['candles']; ctx=dict(saved['context'])
    else:
        # Reconstruct only when there is no original; label that distinction clearly.
        cutoff=target_dt-timedelta(minutes=1)
        history=[c for c in candles if c['dt']+timedelta(minutes=1)<=cutoff][-60:]
        ctx={'direction':direction,'entry_dt':target_dt,'pattern':'Historical reconstruction (original snapshot unavailable)'}
    if not contiguous(history,60):
        return None
    outcome=_settle_from_rows(candles,target_dt,direction,mtg_level,get_current_time())
    stage=outcome.get('mtg_used',0)
    target=next((c for c in candles if c['dt']==target_dt+timedelta(minutes=stage)),None)
    ctx.update(status=outcome['result'] if outcome.get('checked') else 'UNKNOWN',mtg=stage,
               entry_price=f"{target['open']:.7g}" if target else '--',
               exit_price=f"{target['close']:.7g}" if target else '--')
    return await asyncio.to_thread(render_pro_chart,asset,history,ctx)


def _snapshot_key(user_id, asset, stamp):
    return (int(user_id),asset,int(stamp))


def _trade_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📊 Session results',callback_data='partial'),InlineKeyboardButton('📈 Statistics',callback_data='today_stats')],
        [InlineKeyboardButton('⚙️ Strategy & settings',callback_data='settings'),InlineKeyboardButton('⏹ Stop scanning',callback_data='stop_bot')]])


def format_signal_message(asset,direction,signal_time_ts,price,payout,contact,footer_text):
    dt=timestamp_to_dhaka_time(signal_time_ts)
    return (f"<b>◆ REVERSE + TREND • SIGNAL</b>\n\n"
            f"<b>{html_escape(asset)}  |  {'🟢 CALL' if direction=='CALL' else '🔴 PUT'}</b>\n"
            f"Entry: <b>{dt:%Y-%m-%d %H:%M:%S} BDT</b>\nExpiry: 1 minute from entry\n"
            f"Reference close: <code>{price:.7g}</code> (not a fill)\n"
            f"Feed payout: {payout:g}%\n\n"
            f"<i>Pattern-confirmed setup, not a guaranteed outcome.</i>\n{html_escape(str(footer_text))}")


def format_result_message(asset,direction,signal_time_ts,win,mtg_level,individual_stats,pair_stats,contact,footer_text):
    status='TIE' if win is None else 'WIN' if win else 'LOSS'
    dt=timestamp_to_dhaka_time(signal_time_ts)
    w,l=individual_stats['wins'],individual_stats['losses']
    rate=f'{100*w/(w+l):.1f}%' if w+l else 'N/A'
    return (f"<b>◆ RESULT • {status}</b>\n\n<b>{html_escape(asset)} | {direction}</b>\n"
            f"Entry: {dt:%Y-%m-%d %H:%M} BDT\nSettlement stage: {mtg_level}\n"
            f"Wins: {w}  |  Losses: {l}  |  Win rate: {rate}\n"
            f"Ties: {individual_stats.get('ties',0)} (excluded from win rate)\n\n"
            f"<i>Feed OHLC result; not verified broker P&amp;L.</i>\n{html_escape(str(footer_text))}")


async def send_signal_with_chart(user_id,asset,direction,signal_time_ts,price,payout,candles):
    lock=_DELIVERY_LOCKS.setdefault(int(user_id),asyncio.Lock())
    async with lock:
        key=_snapshot_key(user_id,asset,signal_time_ts)
        if key in _SIGNAL_SNAPSHOTS:
            return False
        now=get_current_time()
        if signal_time_ts-now.timestamp()<int(CONFIG.get('MIN_ENTRY_LEAD_SECONDS',12)):
            return False
        settings=USER_DATA.get(str(user_id),{}).get('settings',{})
        session=USER_TRADING_SESSIONS.setdefault(int(user_id),{})
        active=session.get('active_signal')
        if active and (active['asset']!=asset or active['signal_time']!=signal_time_ts):
            return False
        if now.timestamp()-session.get('last_signal_sent',0)<int(CONFIG.get('SIGNAL_COOLDOWN',180)):
            return False
        today=now.date().isoformat()
        if session.get('signal_day')!=today:
            session['signal_day']=today; session['daily_signals']=0
        if session.get('daily_signals',0)>=int(CONFIG.get('MAX_DAILY_SIGNALS',50)):
            return False
        snapshot=clean_ohlc(candles,now,True)[-60:]
        if not contiguous(snapshot,60):
            return False
        analysis=active if active else analyze_api_candles(candles,settings.get('strategy','REVERSE_TREND_PRO'),now)
        if not analysis or analysis.get('direction') != direction:
            return False
        latest=analysis.get('latest_candle',snapshot[-1])['dt']
        if (round_to_minute(now)-latest).total_seconds()!=60:
            return False
        ctx={k:analysis.get(k) for k in ('mode','pattern','strategy','quality','evidence')}
        ctx.update(direction=direction,entry_dt=timestamp_to_dhaka_time(signal_time_ts),status='SIGNAL',
                   brand=settings.get('watermark','RAVITH AI PRO'))
        image=await asyncio.to_thread(render_pro_chart,asset,snapshot,ctx)
        if signal_time_ts-get_current_time().timestamp()<int(CONFIG.get('MIN_ENTRY_LEAD_SECONDS',12)):
            return False
        msg=format_signal_message(asset,direction,signal_time_ts,price,payout,settings.get('contact',''),settings.get('footer_text','RAVITH AI PRO'))
        details=f"\n\n<b>{html_escape(str(analysis.get('mode','SETUP')))}:</b> {html_escape(str(analysis.get('pattern','')))}"
        q=analysis.get('quality')
        if q is not None:
            details+=f"\nRule quality: {q}/100 — not win probability"
        ok=await send_telegram_photo_with_caption(get_user_chat_id(user_id),image,msg+details,_trade_keyboard())
        if not ok:
            return False
        _SIGNAL_SNAPSHOTS[key]={'candles':snapshot,'context':ctx,'image':image.getvalue()}
        while len(_SIGNAL_SNAPSHOTS)>int(CONFIG.get('SNAPSHOT_CACHE_LIMIT',128)):
            protected={_snapshot_key(uid,s['active_signal']['asset'],s['active_signal']['signal_time'])
                       for uid,s in USER_TRADING_SESSIONS.items() if s.get('active_signal')}
            victim=next((k for k in _SIGNAL_SNAPSHOTS if k not in protected and k!=key),None)
            if victim is None:
                break
            del _SIGNAL_SNAPSHOTS[victim]
        sig=dict(analysis)
        sig.update(asset=asset,direction=direction,signal_time=signal_time_ts,
                   signal_dt=timestamp_to_dhaka_time(signal_time_ts),mtg=0,snapshot=snapshot)
        session['active_signal']=sig
        session['last_signal_sent']=time.time()
        session['daily_signals']=session.get('daily_signals',0)+1
        user=USER_DATA.setdefault(str(user_id),{})
        user['signals_received']=user.get('signals_received',0)+1
        save_user_data()
        watcher=session.get('result_task')
        if watcher is None or watcher.done():
            session['result_task']=asyncio.create_task(_result_watcher(user_id))
        return True


async def _result_watcher(user_id):
    # Remains alive after Stop scanner, and also handles manual signals.
    session=USER_TRADING_SESSIONS.get(int(user_id),{})
    while session.get('active_signal'):
        try:
            await check_result_for_user(user_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception('Result watcher failed for %s',user_id)
        await asyncio.sleep(3)


async def send_result_with_chart(user_id,asset,direction,signal_time_ts,win,mtg_level,individual_stats,pair_stats,contact,candles,footer_text):
    saved=_SIGNAL_SNAPSHOTS.get(_snapshot_key(user_id,asset,signal_time_ts))
    if not saved:
        logging.error('Original snapshot missing; refusing to substitute another chart')
        return False
    ctx=dict(saved['context'])
    target_dt=timestamp_to_dhaka_time(signal_time_ts)+timedelta(minutes=mtg_level)
    target=next((c for c in candles if c['dt']==target_dt),None)
    ctx.update(status='TIE' if win is None else 'WIN' if win else 'LOSS',mtg=mtg_level,
               entry_price=f"{target['open']:.7g}" if target else '--',
               exit_price=f"{target['close']:.7g}" if target else '--')
    image=await asyncio.to_thread(render_pro_chart,asset,saved['candles'],ctx)
    msg=format_result_message(asset,direction,signal_time_ts,win,mtg_level,individual_stats,pair_stats,contact,footer_text)
    return await send_telegram_photo_with_caption(get_user_chat_id(user_id),image,msg,_trade_keyboard())


async def send_telegram_photo_with_caption(chat_id,image_buffer,caption,reply_markup=None):
    if BOT_APPLICATION is None:
        return False
    try:
        if image_buffer:
            image_buffer.seek(0)
            if len(caption)<=1024:
                await BOT_APPLICATION.bot.send_photo(chat_id=chat_id,photo=image_buffer,caption=caption,parse_mode='HTML',reply_markup=reply_markup)
            else:
                # Never truncate an HTML caption in the middle of a tag/entity.
                await BOT_APPLICATION.bot.send_photo(chat_id=chat_id,photo=image_buffer)
                await BOT_APPLICATION.bot.send_message(chat_id=chat_id,text=caption,parse_mode='HTML',reply_markup=reply_markup)
        else:
            await BOT_APPLICATION.bot.send_message(chat_id=chat_id,text=caption,parse_mode='HTML',reply_markup=reply_markup)
        return True
    except Exception as exc:
        logging.error('Telegram delivery failed for %s: %s',chat_id,exc)
        return False


async def check_result_for_user(user_id):
    async with _RESULT_LOCKS.setdefault(int(user_id),asyncio.Lock()):
        await _check_result_locked(user_id)


async def _check_result_locked(user_id):
    session=USER_TRADING_SESSIONS.get(user_id,{})
    active=session.get('active_signal')
    if not active:
        return
    stage=active.get('mtg',0)
    target_dt=active['signal_dt']+timedelta(minutes=stage)
    close_dt=target_dt+timedelta(minutes=1)
    now=get_current_time()
    if now<close_dt+timedelta(seconds=5):
        return
    candles=clean_ohlc(await get_candles(active['asset'],count=240),now,True)
    target=next((c for c in candles if c['dt']==target_dt),None)
    if not target:
        session['feed_status']='Result pending: exact closed candle not available'
        if now>close_dt+timedelta(seconds=int(CONFIG.get('RESULT_TIMEOUT_SECONDS',600))):
            sent=await send_telegram_photo_with_caption(get_user_chat_id(user_id),None,
                f"⚠️ Result UNKNOWN: {html_escape(active['asset'])}. Required candle missing; no win/loss recorded.")
            if sent:
                session['active_signal']=None
        return
    diff=target['close']-target['open']
    win=None if diff==0 else (diff>0 if active['direction']=='CALL' else diff<0)
    settings=USER_DATA.get(str(user_id),{}).get('settings',{})
    max_stage=min(2,int(CONFIG.get('MAX_MTG_LEVEL',0))) if settings.get('martingale',False) else 0
    if win is False and stage<max_stage:
        active['mtg']=stage+1
        return
    sent=await send_result_for_user(user_id,active['asset'],active['direction'],active['signal_time'],win,stage,candles)
    if sent:
        session['active_signal']=None


async def send_result_for_user(user_id,asset,direction,signal_time_ts,win,mtg_level=0,candles=None):
    settings=USER_DATA.get(str(user_id),{}).get('settings',{})
    stats=get_user_stats(user_id)
    status='TIE' if win is None else 'WIN' if win else 'LOSS'
    dt=timestamp_to_dhaka_time(signal_time_ts)
    existing=any(r.get('signal_time')==signal_time_ts and r.get('asset')==asset for r in stats.get('all_results',[]))
    if not existing:
        row={'asset':asset,'clean_asset':fancy_asset_name(asset),'direction':direction,'signal_time':signal_time_ts,
             'signal_datetime':dt.isoformat(),'result':status,'mtg_level':mtg_level,'date':dt.date().isoformat(),
             'display_time':dt.strftime('%H:%M'),'timestamp':get_current_time().isoformat()}
        stats.setdefault('all_results',[]).append(row)
        stats['all_results']=stats['all_results'][-1000:]
        if win is True:
            stats['win']=stats.get('win',0)+1; stats['pair_wins']=stats.get('pair_wins',0)+1
            stats['streak']=stats.get('streak',0)+1
            stats['best_streak']=max(stats.get('best_streak',0),stats['streak'])
        elif win is False:
            stats['loss']=stats.get('loss',0)+1; stats['pair_losses']=stats.get('pair_losses',0)+1
            stats['streak']=0
        else:
            stats['ties']=stats.get('ties',0)+1
        save_user_stats()
    individual={'wins':stats.get('win',0),'losses':stats.get('loss',0),'ties':stats.get('ties',0)}
    pairs={'pair_wins':stats.get('pair_wins',0),'pair_losses':stats.get('pair_losses',0)}
    return await send_result_with_chart(user_id,asset,direction,signal_time_ts,win,mtg_level,individual,pairs,
                                       settings.get('contact',''),candles or [],settings.get('footer_text','RAVITH AI PRO'))


def get_user_statistics(user_id,results_list=None):
    rows=results_list if results_list is not None else get_user_stats(user_id).get('all_results',[])
    wins=sum(r.get('result')=='WIN' for r in rows); losses=sum(r.get('result')=='LOSS' for r in rows)
    return {'total_trades':len(rows),'wins':wins,'losses':losses,'ties':sum(r.get('result')=='TIE' for r in rows),
            'accuracy':round(100*wins/(wins+losses),2) if wins+losses else 0}


def _settle_from_rows(candles,target_dt,direction,mtg_level,now):
    if direction not in ('CALL','PUT'):
        return {'result':'UNKNOWN','checked':False,'mtg_used':0,'error':'Invalid direction','payout':0}
    lookup={c['dt']:c for c in clean_ohlc(candles,now,True)}
    for stage in range(min(2,max(0,int(mtg_level)))+1):
        dt=target_dt+timedelta(minutes=stage)
        c=lookup.get(dt)
        if not c:
            return {'result':'PENDING','checked':False,'mtg_used':stage,'error':'Exact closed candle unavailable','payout':0}
        delta=c['close']-c['open']
        payout=c.get('payout',0)
        if delta==0:
            return {'result':'TIE','checked':True,'mtg_used':stage,'payout':payout}
        if (delta>0 if direction=='CALL' else delta<0):
            return {'result':'WIN','checked':True,'mtg_used':stage,'payout':payout}
    return {'result':'LOSS','checked':True,'mtg_used':stage,'payout':payout}


async def check_signal_result(asset,time_str,direction,mtg_level=0,check_date=None):
    candles=await get_candles(asset,count=5000)
    if not candles:
        return {'result':'UNKNOWN','checked':False,'mtg_used':0,'error':'Feed unavailable','payout':0}
    now=get_current_time(); day=check_date or now.date()
    try:
        hour,minute=map(int,time_str.split(':'))
        target=UTC_PLUS_6.localize(datetime(day.year,day.month,day.day,hour,minute))
        return _settle_from_rows(candles,target,direction,mtg_level,now)
    except (TypeError,ValueError):
        return {'result':'UNKNOWN','checked':False,'mtg_used':0,'error':'Invalid time','payout':0}


async def check_signal_result_batch(asset,signals,mtg_level=0,check_date=None):
    if not signals:
        return []
    candles=await get_candles(asset,count=5000)
    now=get_current_time(); day=check_date or now.date(); results=[]
    for sig in signals:
        try:
            hour,minute=map(int,sig['time'].split(':'))
            target=UTC_PLUS_6.localize(datetime(day.year,day.month,day.day,hour,minute))
            result=_settle_from_rows(candles,target,sig['direction'],mtg_level,now) if candles else {
                'result':'UNKNOWN','checked':False,'mtg_used':0,'error':'Feed unavailable','payout':0}
        except (ValueError,TypeError,KeyError):
            result={'result':'UNKNOWN','checked':False,'mtg_used':0,'error':'Invalid signal','payout':0}
        results.append({**sig,**result})
    return results


async def trading_loop_for_user(user_id):
    session=USER_TRADING_SESSIONS.setdefault(user_id,{})
    session['active']=True
    session.setdefault('last_summary_time',time.time())
    checked=set(); last_scan=None
    try:
        while session.get('active'):
            try:
                now=get_current_time()
                settings=USER_DATA.get(str(user_id),{}).get('settings',{})
                if not session.get('active_signal') and 5<=now.second<=38:
                    minute=int(now.timestamp())//60
                    if last_scan!=minute:
                        last_scan=minute
                        if time.time()-session.get('last_signal_sent',0)>=int(CONFIG.get('SIGNAL_COOLDOWN',180)):
                            pref=settings.get('preferred_assets',[]); blocked=settings.get('blocked_assets',[])
                            assets=[a for a in ASSETS if (not pref or a in pref) and a not in blocked]
                            sem=asyncio.Semaphore(6)
                            async def scan(asset):
                                async with sem:
                                    return await analyze_and_update(asset,get_current_time(),settings)
                            candidates=await asyncio.gather(*(scan(a) for a in assets),return_exceptions=True)
                            candidates=[s for s in candidates if isinstance(s,dict) and s['setup_id'] not in checked]
                            candidates.sort(key=lambda s:(-s['quality'],s['asset']))
                            session['feed_status']='Confirmed setup' if candidates else 'WAIT: no fully confirmed pattern'
                            for sig in candidates:
                                if sig['signal_time']-get_current_time().timestamp()<int(CONFIG.get('MIN_ENTRY_LEAD_SECONDS',12)):
                                    continue
                                credit_mode=CONFIG.get('CREDIT_MODE',False) and user_id not in USERS.get('allowed',[]) and not is_admin(user_id)
                                if credit_mode and get_user_credits(user_id)<=0:
                                    session['active']=False
                                    await send_telegram_photo_with_caption(get_user_chat_id(user_id),None,'⛔ No credits remaining. Scanning paused.')
                                    break
                                # send() revalidates freshness, one active trade, and all delivery gates.
                                ok=await send_signal_with_chart(user_id,sig['asset'],sig['direction'],sig['signal_time'],sig['candles'][-1]['close'],sig['payout'],sig['candles'])
                                if ok:
                                    checked.add(sig['setup_id'])
                                    if credit_mode:
                                        deduct_credit(user_id,1)
                                    break
                            if len(checked)>1000:
                                checked.clear()
                if time.time()-session.get('last_summary_time',time.time())>int(CONFIG.get('PARTIAL_RESULT_TIME_MIN',50))*60:
                    await send_partial_summary_for_user(user_id)
                    session['last_summary_time']=time.time()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.exception('Trading loop failure for %s',user_id)
                await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass
    finally:
        session['active']=False


def get_main_keyboard(user_id=None):
    rows=[
        [('▶️ Start scanner','start_bot'),('⏹ Stop scanner','stop_bot')],
        [('📊 Dashboard','status'),('📈 Today','today_stats')],
        [('🧠 Pattern scan','market_scan'),('🎯 Check asset','manual_signal')],
        [('🕯 60-candle chart','chart_now'),('💹 Live prices','live_price')],
        [('📋 Session results','partial'),('📜 History','history')],
        [('📡 Last signal','last_signal'),('🗂 Signal log','signal_log')],
        [('🔎 Assets','asset_info'),('🏆 Leaderboard','leaderboard')],
        [('⚙️ Strategy & settings','settings')],
        [('🔮 Historical result checker','future_checker')],
        [('👤 Profile','profile'),('💡 Help','help')],
        [('🔌 Telegram connect','tg_connect'),('🔄 Reset session','reset')],
    ]
    return InlineKeyboardMarkup([[InlineKeyboardButton(text,callback_data=cb) for text,cb in row] for row in rows])


def get_owner_keyboard(user_id=None):
    rows=list(get_main_keyboard(user_id).inline_keyboard)
    rows.append([InlineKeyboardButton('👑 Administration',callback_data='admin_panel')])
    return InlineKeyboardMarkup(rows)


def apply_pro_migration():
    """One-time per-user default migration; later explicit strategy choices survive."""
    for user in USER_DATA.values():
        settings=user.setdefault('settings',{})
        if settings.get('pro_engine_version')!=1:
            settings.update(strategy='REVERSE_TREND_PRO',pro_engine_version=1,chart_style='pro',martingale=False)
    if USER_DATA:
        save_user_data()


def get_settings_keyboard(user_id):
    s=USER_DATA.get(str(user_id),{}).get('settings',{})
    name=STRATEGY_LABELS.get(s.get('strategy','REVERSE_TREND_PRO'),'Reverse + Trend PRO')
    rows=[
        [('💎 '+name,'select_strategy')],
        [('🕯 Pro chart • 60 candles','toggle_chart_style')],
        [('📡 Asset / direction filter: '+s.get('signal_type','all'),'toggle_signal_type')],
        [('💵 Minimum payout: '+str(s.get('min_payout',0))+'%','set_min_payout')],
        [('⭐ Preferred assets','preferred_assets'),('🚫 Blocked assets','blocked_assets')],
        [('🔄 Martingale: '+('ON' if s.get('martingale',False) else 'OFF'),'toggle_martingale')],
        [('🎨 Chart brand','set_watermark'),('📝 Footer text','set_footer_text')],
        [('📞 Contact','set_contact'),('🔌 Telegram connect','tg_connect')],
        [('‹ Back to dashboard','back_main')],
    ]
    return InlineKeyboardMarkup([[InlineKeyboardButton(t,callback_data=c) for t,c in row] for row in rows])


def get_settings_message(user_id):
    s=USER_DATA.get(str(user_id),{}).get('settings',{})
    strategy=STRATEGY_LABELS.get(s.get('strategy','REVERSE_TREND_PRO'),'Reverse + Trend PRO')
    return (f"<b>⚙️ STRATEGY & SETTINGS</b>\n\n<b>{html_escape(strategy)}</b>\n"
            'Reversal: level sweep + reclaim + candle confirmation + RSI recovery.\n'
            'Trend: EMA alignment + pullback + reclaim + momentum + room to next level.\n\n'
            '<b>Always enforced</b>\n100 closed bars for analysis • 60 real bars per image\n'
            'Gap / stale feed / shock filters • one active signal\n'
            'No confirmed pattern = WAIT • no forced minute-by-minute signal\n'
            f"Cooldown: {CONFIG.get('SIGNAL_COOLDOWN',180)}s | Daily limit: {CONFIG.get('MAX_DAILY_SIGNALS',50)}\n"
            f"Minimum feed payout: {s.get('min_payout',0)}%\n"
            f"Martingale: {'ON (increased risk)' if s.get('martingale',False) else 'OFF'}\n\n"
            '<i>Quality is a rule score, not calibrated win probability. No guaranteed accuracy.</i>')


async def main():
    global BOT_APPLICATION, OWNER_ID

    load_config()
    OWNER_ID = int(os.getenv("OWNER_ID") or CONFIG.get("OWNER_ID", 0))
    load_users()
    load_user_data()
    load_user_stats()
    apply_pro_migration()
    if not PIL_AVAILABLE:
        raise RuntimeError("Install Pillow: charts are required; no text-only trading mode.")

    # Railway Variables take priority; never store the Telegram token in source code.
    token = (
        os.getenv("BOT_TOKEN")
        or os.getenv("TELEGRAM_BOT_TOKEN")
        or CONFIG.get("TELEGRAM_BOT_TOKEN")
    )
    if not token:
        raise RuntimeError(
            "BOT_TOKEN is missing. Add BOT_TOKEN in Railway → Service → Variables."
        )

    application = Application.builder().token(token).build()
    BOT_APPLICATION = application

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    application.add_error_handler(error_handler)

    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    print(Fore.GREEN + "✅ Telegram Bot is running. Send /start to interact.")
    print(Fore.YELLOW + f"👑 Owner ID: {OWNER_ID}")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    try:
        import signal
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_event.set)
            except (NotImplementedError, RuntimeError):
                pass
        await stop_event.wait()
    finally:
        print(Fore.CYAN + "\n🛑 Shutting down...")
        for uid_key, sess in USER_TRADING_SESSIONS.items():
            sess["active"] = False
            if sess.get("trading_task"):
                sess["trading_task"].cancel()
            if sess.get("result_task"):
                sess["result_task"].cancel()

        await application.updater.stop()
        await application.stop()
        await application.shutdown()

        save_user_data()
        save_user_stats()
        save_users()

        print(Fore.GREEN + "✅ Saved. Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())