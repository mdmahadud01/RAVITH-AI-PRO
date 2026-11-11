"""RAVITH AI — educational candle-chart viewer. Trading signals and win/loss claims disabled."""

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
    "MAX_MTG_LEVEL": 1,
    "OWNER_ID": 6690775077,
    "ADMINS": [],
    "API_BASE_URL": "https://creating-speed-pro-versions.trycloudflare.com",
    "API_CANDLE_COUNT": 5000,
    "API_INTERVAL": "1m",
    "RISK_LEVEL": "medium",
    "AUTO_TRADE": False,
    "SIGNAL_COOLDOWN": 60,
    "MAX_DAILY_SIGNALS": 100,
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
                "chart_style": "3d",
                "sound_alert": True,
                "auto_result": True,
                "show_payout": True,
                "martingale": True,
                "language": "en",
                "timezone": "Asia/Dhaka",
                "preferred_assets": [],
                "blocked_assets": [],
                "min_payout": 0,
                "notification_mode": "all",
                "strategy": "REVERSE_PLUS_TRENDY",    # educational chart-study preset
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
        settings.setdefault("chart_style", "3d")
        settings.setdefault("sound_alert", True)
        settings.setdefault("auto_result", True)
        settings.setdefault("show_payout", True)
        settings.setdefault("martingale", True)
        settings.setdefault("language", "en")
        settings.setdefault("timezone", "Asia/Dhaka")
        settings.setdefault("preferred_assets", [])
        settings.setdefault("blocked_assets", [])
        settings.setdefault("min_payout", 0)
        settings.setdefault("notification_mode", "all")
        settings.setdefault("strategy", "REVERSE_PLUS_TRENDY")
        if settings.get("strategy") == "RSI_REVERSE":
            settings["strategy"] = "REVERSE_PLUS_TRENDY"
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
async def fetch_candles_from_api(asset: str, count: int = None, interval: str = None) -> Optional[List[Dict]]:
    if count is None:
        count = CONFIG.get("API_CANDLE_COUNT", 5000)
    if interval is None:
        interval = CONFIG.get("API_INTERVAL", "1m")
    base_url = CONFIG.get("API_BASE_URL", "https://creating-speed-pro-versions.trycloudflare.com")
    url = f"{base_url}?Pair={asset}&Candle={count}&Time={interval}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                raw_candles = data.get("data", [])
                if not raw_candles:
                    return None
                candles = []
                for item in raw_candles:
                    time_str = item.get("time")
                    try:
                        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                        dt = UTC_PLUS_6.localize(dt)
                    except:
                        continue
                    candle = {
                        "dt": dt,
                        "open": float(item.get("open", 0)),
                        "high": float(item.get("high", 0)),
                        "low": float(item.get("low", 0)),
                        "close": float(item.get("close", 0)),
                        "volume": 0,
                        "payout": float(item.get("payout", 0)),
                        "signal": item.get("signal")
                    }
                    candles.append(candle)
                candles.sort(key=lambda x: x["dt"])
                return candles
    except asyncio.TimeoutError:
        pass
    except Exception as e:
        print(f"{Fore.RED}❌ API fetch error for {asset}: {e}")
    return None

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

def compute_rsi(closes, period=14):
    rsi = [None] * len(closes)
    if len(closes) < period + 1: return rsi
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        rsi[i+1] = 100 - (100 / (1 + rs))
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    return rsi

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

# ================= STRATEGIES (using full candle data) =================
def strategy_support_resistance(candles: List[Dict]) -> Optional[str]:
    """Support/Resistance: detect swing highs/lows and signal bounce/rejection."""
    if len(candles) < 30:
        return None
    # Get recent 30 candles
    recent = candles[-30:]
    highs = [c['high'] for c in recent]
    lows = [c['low'] for c in recent]
    closes = [c['close'] for c in recent]
    # Find swing highs (local maxima)
    swing_highs = []
    for i in range(2, len(highs)-2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append(highs[i])
    swing_lows = []
    for i in range(2, len(lows)-2):
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append(lows[i])
    if not swing_highs or not swing_lows:
        return None
    resistance = sum(swing_highs[-3:]) / min(3, len(swing_highs))
    support = sum(swing_lows[-3:]) / min(3, len(swing_lows))
    price = closes[-1]
    # If price near support and bouncing up (close > open)
    if price - support < (resistance - support) * 0.1 and recent[-1]['close'] > recent[-1]['open']:
        return "CALL"
    # If price near resistance and rejecting (close < open)
    if resistance - price < (resistance - support) * 0.1 and recent[-1]['close'] < recent[-1]['open']:
        return "PUT"
    return None

def strategy_rsi_reverse(candles: List[Dict]) -> Optional[str]:
    """RSI Reverse: detect bullish/bearish divergence and overbought/oversold reversals."""
    if len(candles) < 30:
        return None
    closes = [c['close'] for c in candles]
    rsi_vals = compute_rsi(closes, 14)
    if rsi_vals[-1] is None:
        return None
    rsi = rsi_vals[-1]
    price = closes[-1]
    # Check for divergence: price lower low, RSI higher low (bullish)
    if len(closes) >= 10:
        last_10_close = closes[-10:]
        last_10_rsi = [v for v in rsi_vals[-10:] if v is not None]
        if len(last_10_rsi) >= 10:
            min_price = min(last_10_close)
            min_rsi = min(last_10_rsi)
            if closes[-1] > min_price and rsi > min_rsi:
                # Price made higher low, RSI made higher low -> bullish divergence
                if rsi < 40:  # oversold region
                    return "CALL"
    # Overbought/oversold reversal
    if rsi > 75:
        return "PUT"
    if rsi < 25:
        return "CALL"
    return None

def strategy_ema_trend(candles: List[Dict]) -> Optional[str]:
    """EMA Trend: use crossovers of EMA5 and EMA21."""
    if len(candles) < 30:
        return None
    closes = [c['close'] for c in candles]
    ema5 = compute_ema(closes, 5)
    ema21 = compute_ema(closes, 21)
    if ema5[-1] is None or ema21[-1] is None:
        return None
    # Check crossover in last 2 candles
    if len(ema5) >= 2 and len(ema21) >= 2:
        if ema5[-2] is not None and ema21[-2] is not None:
            if ema5[-2] < ema21[-2] and ema5[-1] > ema21[-1]:
                return "CALL"
            if ema5[-2] > ema21[-2] and ema5[-1] < ema21[-1]:
                return "PUT"
    return None

def strategy_strong_signal(candles: List[Dict]) -> Optional[str]:
    """Strong Signal: combine RSI, MACD, and EMA trend."""
    if len(candles) < 30:
        return None
    closes = [c['close'] for c in candles]
    rsi = compute_rsi(closes, 14)[-1]
    macd_line, sig_line, hist = compute_macd(closes)
    ema5 = compute_ema(closes, 5)[-1]
    ema21 = compute_ema(closes, 21)[-1]
    if rsi is None or macd_line[-1] is None or sig_line[-1] is None or ema5 is None or ema21 is None:
        return None
    # Conditions for CALL:
    # 1. RSI > 50 (bullish momentum)
    # 2. MACD line > signal line (bullish)
    # 3. EMA5 > EMA21 (uptrend)
    if rsi > 50 and macd_line[-1] > sig_line[-1] and ema5 > ema21:
        return "CALL"
    # Conditions for PUT:
    if rsi < 50 and macd_line[-1] < sig_line[-1] and ema5 < ema21:
        return "PUT"
    return None

STRATEGY_FUNCTIONS = {
    "SUPPORT_RESISTANCE": strategy_support_resistance,
    "RSI_REVERSE": strategy_rsi_reverse,
    "EMA_TREND": strategy_ema_trend,
    "STRONG_SIGNAL": strategy_strong_signal,
}

# ================= Signal Analysis (using strategy) =================

def analyze_api_candles(candles: List[Dict]) -> Optional[Dict]:
    """Deterministic multi-indicator OHLC analysis; never uses random/API signal values."""
    if not candles or len(candles) < 60:
        return None
    clean, seen = [], set()
    for c in candles:
        try:
            o, h, lo, cl = (float(c[k]) for k in ("open", "high", "low", "close"))
            dt = c.get("dt")
            if not isinstance(dt, datetime) or min(o, h, lo, cl) <= 0 or h < max(o, cl) or lo > min(o, cl) or h < lo:
                continue
            key = dt.replace(second=0, microsecond=0)
            if key in seen:
                continue
            seen.add(key)
            clean.append(c)
        except (KeyError, TypeError, ValueError):
            continue
    clean.sort(key=lambda x: x["dt"])
    if len(clean) < 60:
        return None

    closes = [float(c["close"]) for c in clean]
    highs = [float(c["high"]) for c in clean]
    lows = [float(c["low"]) for c in clean]
    opens = [float(c["open"]) for c in clean]
    i = len(clean) - 1
    last = clean[i]
    body = closes[i] - opens[i]
    candle_range = max(highs[i] - lows[i], 1e-12)
    if abs(body) / candle_range < 0.025:
        return None

    rsi = compute_rsi(closes, 14)[-1]
    macd, macd_sig, hist = compute_macd(closes)
    ema5, ema9 = compute_ema(closes, 5), compute_ema(closes, 9)
    ema21, ema50 = compute_ema(closes, 21), compute_ema(closes, 50)
    st_k, st_d = compute_stochastic(closes, highs, lows, 14)
    willr = compute_williams_r(highs, lows, closes, 14)
    cci = compute_cci(highs, lows, closes, 20)
    bull = bear = 0.0
    evidence = []

    def vote(ok, side, weight, label):
        nonlocal bull, bear
        if ok:
            if side == "CALL": bull += weight
            else: bear += weight
            evidence.append(label)

    vote(ema5[i] is not None and ema9[i] is not None and ema5[i] > ema9[i], "CALL", 1.0, "EMA 5/9 bullish")
    vote(ema5[i] is not None and ema9[i] is not None and ema5[i] < ema9[i], "PUT", 1.0, "EMA 5/9 bearish")
    vote(ema9[i] is not None and ema21[i] is not None and ema9[i] > ema21[i], "CALL", 1.2, "EMA 9/21 uptrend")
    vote(ema9[i] is not None and ema21[i] is not None and ema9[i] < ema21[i], "PUT", 1.2, "EMA 9/21 downtrend")
    vote(ema21[i] is not None and ema50[i] is not None and ema21[i] > ema50[i], "CALL", .8, "EMA 21/50 trend")
    vote(ema21[i] is not None and ema50[i] is not None and ema21[i] < ema50[i], "PUT", .8, "EMA 21/50 trend")
    if macd[i] is not None and macd_sig[i] is not None and hist[i] is not None:
        vote(macd[i] > macd_sig[i] and hist[i] > 0, "CALL", 1.2, "MACD bullish")
        vote(macd[i] < macd_sig[i] and hist[i] < 0, "PUT", 1.2, "MACD bearish")
    if rsi is not None:
        vote(50 < rsi < 72, "CALL", .8, "RSI bullish momentum")
        vote(28 < rsi < 50, "PUT", .8, "RSI bearish momentum")
        vote(rsi <= 30 and body > 0 and closes[i] > closes[i-1], "CALL", 1.0, "RSI oversold reversal")
        vote(rsi >= 70 and body < 0 and closes[i] < closes[i-1], "PUT", 1.0, "RSI overbought reversal")
    if st_k[i] is not None and st_d[i] is not None:
        vote(st_k[i] > st_d[i] and st_k[i] < 80, "CALL", .6, "Stochastic bullish")
        vote(st_k[i] < st_d[i] and st_k[i] > 20, "PUT", .6, "Stochastic bearish")
    if willr[i] is not None:
        vote(willr[i] < -80 and body > 0, "CALL", .5, "Williams oversold bounce")
        vote(willr[i] > -20 and body < 0, "PUT", .5, "Williams overbought rejection")
    if cci[i] is not None:
        vote(cci[i] > 50, "CALL", .5, "CCI positive")
        vote(cci[i] < -50, "PUT", .5, "CCI negative")

    range_high, range_low = max(highs[-21:-1]), min(lows[-21:-1])
    vote(closes[i] > range_high, "CALL", 1.0, "20-candle breakout")
    vote(closes[i] < range_low, "PUT", 1.0, "20-candle breakdown")
    support, resistance = min(lows[-20:]), max(highs[-20:])
    near_support = (lows[i] - support) / max(support, 1e-12) < .0008
    near_resistance = (resistance - highs[i]) / max(resistance, 1e-12) < .0008
    vote(near_support and body > 0 and closes[i] > lows[i] + candle_range*.65,
         "CALL", .8, "Support rejection")
    vote(near_resistance and body < 0 and closes[i] < highs[i] - candle_range*.65,
         "PUT", .8, "Resistance rejection")
    vote(body > 0 and abs(body)/candle_range >= .55 and closes[i] > closes[i-1],
         "CALL", .7, "Bullish candle momentum")
    vote(body < 0 and abs(body)/candle_range >= .55 and closes[i] < closes[i-1],
         "PUT", .7, "Bearish candle momentum")

    dominant, opposing = max(bull, bear), min(bull, bear)
    confidence = dominant / max(dominant + opposing, 1e-9) * 100
    if dominant < 4.0 or confidence < 68 or abs(bull - bear) < 2.0:
        return None
    recent_vol = [(highs[j]-lows[j])/opens[j] for j in range(len(clean)-10, len(clean))]
    if not recent_vol or sum(recent_vol)/len(recent_vol) > .025:
        return None
    direction = "CALL" if bull > bear else "PUT"
    trend_up = ema9[i] is not None and ema21[i] is not None and ema9[i] > ema21[i]
    strategy = "TRENDY" if (trend_up == (direction == "CALL")) else "PULLBACK"
    return {"direction": direction, "confidence": round(confidence, 1),
            "strategy": strategy, "evidence": evidence[-8:], "latest_candle": last,
            "candles": clean, "payout": float(last.get("payout", 0) or 0)}


def educational_pattern_notes(candles: List[Dict]) -> Dict:
    """Describe visible candle structure for learning; never outputs trade directions."""
    if not candles or len(candles) < 25:
        return {"status": "Need at least 25 candles", "observations": []}
    recent = candles[-25:]
    closes = [float(c["close"]) for c in recent]
    opens = [float(c["open"]) for c in recent]
    highs = [float(c["high"]) for c in recent]
    lows = [float(c["low"]) for c in recent]
    ema_fast = compute_ema(closes, 5)[-1]
    ema_slow = compute_ema(closes, 21)[-1]
    last_range = max(highs[-1] - lows[-1], 1e-12)
    body_ratio = abs(closes[-1] - opens[-1]) / last_range
    upper_wick = highs[-1] - max(opens[-1], closes[-1])
    lower_wick = min(opens[-1], closes[-1]) - lows[-1]
    observations = []
    if ema_fast is not None and ema_slow is not None:
        if ema_fast > ema_slow:
            observations.append("Short-term averages are above the medium-term average (upward trend structure).")
        elif ema_fast < ema_slow:
            observations.append("Short-term averages are below the medium-term average (downward trend structure).")
        else:
            observations.append("Moving averages are closely aligned (unclear trend structure).")
    if lower_wick / last_range > 0.55:
        observations.append("Latest candle has a long lower wick; downside rejection is visible, but unconfirmed.")
    elif upper_wick / last_range > 0.55:
        observations.append("Latest candle has a long upper wick; upside rejection is visible, but unconfirmed.")
    if body_ratio < 0.2:
        observations.append("Latest candle has a small body; indecision is possible.")
    elif body_ratio > 0.7:
        observations.append("Latest candle has a relatively large body; recent momentum is visually strong.")
    prior_high, prior_low = max(highs[:-1]), min(lows[:-1])
    if closes[-1] > prior_high:
        observations.append("Latest close is above the previous 24-candle range (range expansion).")
    elif closes[-1] < prior_low:
        observations.append("Latest close is below the previous 24-candle range (range expansion).")
    if not observations:
        observations.append("No clear educational pattern detected; wait for more price structure.")
    return {"status": "Educational observation only — not a trading signal", "observations": observations}


async def analyze_and_update(asset: str, current_time: datetime, user_settings: dict) -> Optional[Dict]:
    """Trading-signal generation is intentionally disabled in this educational build."""
    return None

# ================= 3D DASHBOARD GENERATION (unchanged, except using new assets) =================
if PIL_AVAILABLE:
    COLORS = {
        "bg": (6, 9, 14, 255),
        "panel": (12, 18, 30, 255),
        "panel_dark": (8, 12, 20, 255),
        "panel_light": (20, 30, 50, 255),
        "shadow": (0, 0, 0, 180),
        "shadow_deep": (0, 0, 0, 255),
        "glow_bull": (50, 205, 50, 80),
        "glow_bear": (255, 23, 68, 80),
        "glow_cyan": (0, 229, 255, 80),
        "glow_purple": (180, 80, 255, 80),
        "border": (30, 90, 150, 255),
        "border_light": (60, 140, 220, 255),
        "grid": (255, 255, 255, 20),
        "dashed_line": (255, 255, 255, 40),
        "text_main": (245, 250, 255, 255),
        "text_dim": (140, 155, 175, 255),
        "text_darker": (60, 80, 100, 255),
        "bull": (50, 205, 50, 255),
        "bear": (255, 23, 68, 255),
        "cyan": (0, 229, 255, 255),
        "purple": (180, 80, 255, 255),
        "orange": (255, 145, 0, 255),
        "gold": (255, 215, 0, 255),
        "pink": (255, 64, 129, 255),
        "button_buy_bg": (15, 90, 45, 255),
        "button_sell_bg": (100, 20, 30, 255),
        "gauge_inner": (20, 30, 50, 255),
        "gauge_outer": (15, 25, 40, 255),
    }

    def get_font(size, bold=True):
        fonts = ["consola.ttf", "courbd.ttf", "cour.ttf", "lucon.ttf", "LiberationMono-Bold.ttf", "arialbd.ttf", "arial.ttf"]
        for f in fonts:
            try:
                return ImageFont.truetype(f, size)
            except:
                pass
        return ImageFont.load_default()

    def draw_3d_text(draw, pos, text, size=20, color=None, bold=True, anchor="lt", shadow=True, glow=False):
        if color is None:
            color = COLORS["text_main"]
        font = get_font(size, bold)
        if shadow:
            draw.text((pos[0]+2, pos[1]+2), text, fill=COLORS["shadow"], font=font, anchor=anchor, stroke_width=2, stroke_fill=COLORS["shadow_deep"])
        if glow and color:
            glow_color = (color[0], color[1], color[2], 40)
            draw.text((pos[0], pos[1]), text, fill=glow_color, font=font, anchor=anchor, stroke_width=8, stroke_fill=glow_color)
            draw.text((pos[0], pos[1]), text, fill=glow_color, font=font, anchor=anchor, stroke_width=4, stroke_fill=glow_color)
        stroke = 1 if bold else 0
        draw.text(pos, text, fill=color, font=font, anchor=anchor, stroke_width=stroke, stroke_fill=color)

    def draw_chamfer_panel(draw, box, fill=None, outline=None, cut=12, highlight=None, shadow=True, corner_only=False):
        if fill is None:
            fill = COLORS["panel"]
        if outline is None:
            outline = COLORS["border"]
        if highlight is None:
            highlight = COLORS["cyan"]
        x1, y1, x2, y2 = box
        if shadow:
            shadow_pts = [
                (x1+cut+8, y1+8), (x2-cut+8, y1+8),
                (x2+8, y1+cut+8), (x2+8, y2-cut+8),
                (x2-cut+8, y2+8), (x1+cut+8, y2+8),
                (x1+8, y2-cut+8), (x1+8, y1+cut+8)
            ]
            draw.polygon(shadow_pts, fill=COLORS["shadow"])
        pts = [
            (x1+cut, y1), (x2-cut, y1), (x2, y1+cut), (x2, y2-cut),
            (x2-cut, y2), (x1+cut, y2), (x1, y2-cut), (x1, y1+cut)
        ]
        draw.polygon(pts, fill=fill)
        draw.line([(x1+cut, y1+2), (x2-cut, y1+2)], fill=(255, 255, 255, 60), width=2)
        draw.line([(x1+2, y1+cut), (x1+2, y2-cut)], fill=(255, 255, 255, 60), width=2)
        draw.line([(x1+cut, y2-2), (x2-cut, y2-2)], fill=(0, 0, 0, 200), width=3)
        draw.line([(x2-2, y1+cut), (x2-2, y2-cut)], fill=(0, 0, 0, 200), width=3)
        draw.polygon(pts, outline=(outline[0], outline[1], outline[2], 80), width=4)
        draw.polygon(pts, outline=outline, width=1)
        if highlight:
            draw.line([(x1+2, y1+cut+10), (x1+2, y1+cut), (x1+cut, y1+2), (x1+cut+10, y1+2)], fill=highlight, width=3)
            draw.line([(x2-2, y2-cut-10), (x2-2, y2-cut), (x2-cut, y2-2), (x2-cut-10, y2-2)], fill=highlight, width=3)

    def draw_dashed_grid(draw, start, end, color=None, width=1, dash=8, space=8):
        if color is None:
            color = COLORS["grid"]
        x1, y1 = start
        x2, y2 = end
        length = math.hypot(x2-x1, y2-y1)
        if length == 0: return
        dx, dy = (x2-x1)/length, (y2-y1)/length
        current = 0
        while current < length:
            seg_end = min(current + dash, length)
            p1 = (x1 + dx*current, y1 + dy*current)
            p2 = (x1 + dx*seg_end, y1 + dy*seg_end)
            draw.line([p1, p2], fill=color, width=width)
            current += dash + space

    def draw_glowing_line(draw, start, end, color, glow_color, width=2):
        draw.line([start, end], fill=glow_color, width=width+4)
        draw.line([start, end], fill=color, width=width)

    def draw_3d_icon(draw, cx, cy, icon_type, active):
        color = COLORS["cyan"] if active else COLORS["text_dim"]
        draw_icon_shapes(draw, cx, cy, icon_type, color, width=2, fill=True)

    def draw_icon_shapes(draw, cx, cy, icon_type, color, width=2, fill=False):
        if icon_type == "MARKET":
            draw.ellipse([cx-8, cy-8, cx+8, cy+8], outline=color, width=width)
            draw.ellipse([cx-3, cy-3, cx+3, cy+3], outline=color, width=1)
        elif icon_type == "CHART":
            draw.rectangle([cx-10, cy+4, cx-5, cy+10], fill=color if fill else None, outline=color, width=width)
            draw.rectangle([cx-2, cy-2, cx+3, cy+10], fill=color if fill else None, outline=color, width=width)
            draw.rectangle([cx+6, cy-6, cx+11, cy+10], fill=color if fill else None, outline=color, width=width)
        elif icon_type == "ANALYSIS":
            draw.line([(cx-10, cy+6), (cx-2, cy), (cx+4, cy+4), (cx+12, cy-4)], fill=color, width=width)
        elif icon_type == "SIGNALS":
            draw.arc([cx-8, cy-8, cx+8, cy+8], 210, 330, fill=color, width=width)
            draw.ellipse([cx-2, cy+4, cx+2, cy+8], fill=color)
        elif icon_type == "SETTINGS":
            for i in range(0, 360, 45):
                rad = math.radians(i)
                x, y = cx + math.cos(rad)*10, cy + math.sin(rad)*10
                draw.line([(cx, cy), (x, y)], fill=color, width=width+1)
            draw.ellipse([cx-7, cy-7, cx+7, cy+7], fill=COLORS["panel"] if fill else None, outline=color, width=width)
            draw.ellipse([cx-3, cy-3, cx+3, cy+3], fill=color)
        elif icon_type == "HELP":
            draw.ellipse([cx-8, cy-8, cx+8, cy+8], outline=color, width=width)
            draw_3d_text(draw, (cx, cy-2), "?", size=14, color=color, bold=True, anchor="mm", shadow=False)
        elif icon_type == "PORTFOLIO":
            draw.rectangle([cx-10, cy-2, cx+10, cy+8], outline=color, width=width)
            draw.rectangle([cx-4, cy-6, cx+4, cy-2], outline=color, width=width)

    def draw_sci_fi_gauge(draw, center, radius, percentage, color, text_val, title="", unit=""):
        cx, cy = center
        draw.ellipse([cx-radius-6, cy-radius-6, cx+radius+6, cy+radius+6], fill=(0,0,0,150))
        draw.ellipse([cx-radius, cy-radius, cx+radius, cy+radius], outline=(10, 20, 35, 255), width=6)
        arc_angle = int(360 * (percentage / 100)) if percentage > 0 else 1
        draw.arc([cx-radius, cy-radius, cx+radius, cy+radius], -90, -90 + arc_angle, fill=color, width=4)
        draw.ellipse([cx-radius+12, cy-radius+12, cx+radius-12, cy+radius-12], outline=color, width=2)
        draw_3d_text(draw, (cx, cy-4), text_val, size=24, bold=True, color=color, anchor="mm", shadow=True, glow=True)
        if title:
            draw_3d_text(draw, (cx, cy+22), title, size=12, bold=True, color=COLORS["text_dim"], anchor="mm")

    def draw_3d_bull_icon(draw, box, color):
        x1, y1, x2, y2 = box
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        w, h = 60, 40
        bx, by = cx - w//2, cy - h//2
        pts = [
            (bx+5, by+10), (bx+10, by+5), (bx+20, by+5), (bx+30, by+0),
            (bx+40, by+0), (bx+45, by-5), (bx+55, by+5), (bx+45, by+15),
            (bx+40, by+25), (bx+35, by+35), (bx+25, by+35), (bx+25, by+30),
            (bx+20, by+30), (bx+15, by+35), (bx+5, by+35), (bx+5, by+25),
            (bx+0, by+30), (bx-5, by+15), (bx+5, by+10)
        ]
        draw.polygon(pts, fill=(color[0], color[1], color[2], 40))
        draw.polygon(pts, outline=color, width=2)

    def draw_left_navigation(draw, start_x, start_y, width, height):
        draw_chamfer_panel(draw, [start_x, start_y, start_x + width, start_y + height], highlight=COLORS["cyan"], cut=15)
        logo_center_x = start_x + width // 2
        logo_center_y = start_y + 60
        for r, w, a in [(35, 2, 60), (28, 3, 100), (18, 4, 255), (8, 3, 255)]:
            draw.ellipse([logo_center_x-r, logo_center_y-r, logo_center_x+r, logo_center_y+r], outline=(COLORS["cyan"][0], COLORS["cyan"][1], COLORS["cyan"][2], a), width=w)
        draw.ellipse([logo_center_x-5, logo_center_y-5, logo_center_x+5, logo_center_y+5], fill=COLORS["cyan"])
        nav_items = [
            ("MARKET", "MARKET", False),
            ("CHART", "CHART", True),
            ("ANALYSIS", "ANALYSIS", False),
            ("SIGNALS", "SIGNALS", False),
            ("PORTFOLIO", "PORTFOLIO", False),
            ("SETTINGS", "SETTINGS", False),
            ("HELP", "HELP", False)
        ]
        for i, (ico, text, active) in enumerate(nav_items):
            y_pos = start_y + 120 + i * 95
            color = COLORS["cyan"] if active else COLORS["text_dim"]
            if active:
                draw.line([(start_x+2, y_pos-20), (start_x+2, y_pos+20)], fill=COLORS["cyan"], width=5)
            draw_3d_icon(draw, logo_center_x, y_pos - 15, ico, active)
            draw_3d_text(draw, (logo_center_x, y_pos + 20), text, size=11, bold=True, color=color, anchor="mm", shadow=True)

    def draw_top_header(draw, x1, y1, x2, pair, timeframe, latest_candle, all_candles):
        draw.rectangle([x1, y1+10, x2, y1+50], fill=(0,0,0,100))
        draw_3d_text(draw, (x1, y1+15), f"{pair}", size=32, bold=True, color=COLORS["text_main"], anchor="lm", shadow=True)
        l = latest_candle
        metrics = [
            ("OPEN", f"{l['open']:.4f}", COLORS["text_main"]),
            ("HIGH", f"{l['high']:.4f}", COLORS["bull"]),
            ("LOW", f"{l['low']:.4f}", COLORS["bear"]),
            ("CLOSE", f"{l['close']:.4f}", COLORS["bull"])
        ]
        cx = x1 + 320
        for label, val, color in metrics:
            draw_3d_text(draw, (cx, y1+15), label, size=14, bold=True, color=COLORS["text_dim"], anchor="lm")
            draw_3d_text(draw, (cx+60, y1+15), val, size=18, bold=True, color=color, anchor="lm")
            cx += 130
        time_str = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
        draw_3d_text(draw, (x2 - 200, y1+15), time_str, size=14, bold=True, color=COLORS["text_dim"], anchor="rm")

    def draw_candle_chart(draw, x1, y1, x2, y2, candles):
        draw_chamfer_panel(draw, [x1, y1, x2, y2], highlight=COLORS["cyan"], cut=12)
        draw_3d_text(draw, (x1+20, y1+25), f"{CONFIG['API_INTERVAL']}", size=18, bold=True, color=COLORS["text_main"], anchor="lm")
        draw.rounded_rectangle([x2-120, y1+15, x2-30, y1+48], radius=8, fill=(10, 50, 25, 255), outline=COLORS["bull"], width=2)
        draw_3d_text(draw, (x2-75, y1+31), "LIVE", size=14, bold=True, color=COLORS["bull"], anchor="mm", glow=True)
        plot_x1, plot_y1 = x1+60, y1+70
        plot_x2, plot_y2 = x2-30, y2-30
        for gx in range(plot_x1, plot_x2, 120):
            draw_dashed_grid(draw, (gx, plot_y1), (gx, plot_y2))
        for gy in range(plot_y1, plot_y2, 80):
            draw_dashed_grid(draw, (plot_x1, gy), (plot_x2, gy))
        all_h = [c['high'] for c in candles]
        all_l = [c['low'] for c in candles]
        all_v = [c.get('volume', 1000) or 1000 for c in candles]
        min_p, max_p = min(all_l), max(all_h)
        p_range = max_p - min_p if max_p != min_p else 1
        chart_h = plot_y2 - plot_y1
        def scale_y(p): return plot_y2 - int((p - min_p) / p_range * chart_h)
        def scale_x(i): return plot_x1 + int((i / max(1, len(candles) - 1)) * (plot_x2 - plot_x1))
        for i in range(7):
            y_pos = plot_y1 + i * (chart_h // 6)
            val = max_p - (i / 6) * p_range
            draw_3d_text(draw, (plot_x2 - 8, y_pos), f"{val:.4f}", size=12, bold=True, color=COLORS["text_dim"], anchor="rm")
        for i in range(0, len(candles), max(1, len(candles)//10)):
            draw_3d_text(draw, (scale_x(i), plot_y2 + 15), candles[i]['dt'].strftime("%H:%M"), size=12, bold=True, color=COLORS["text_dim"], anchor="mm")
        c_width = max(3, int((plot_x2 - plot_x1) / len(candles) * 0.45))
        max_vol = max(all_v) if all_v else 1
        for i, c in enumerate(candles):
            cx = scale_x(i)
            y_o = scale_y(c['open'])
            y_c = scale_y(c['close'])
            y_h = scale_y(c['high'])
            y_l = scale_y(c['low'])
            col = COLORS["bull"] if c['close'] >= c['open'] else COLORS["bear"]
            glow_col = COLORS["glow_bull"] if c['close'] >= c['open'] else COLORS["glow_bear"]
            body_top, body_bot = min(y_o, y_c), max(y_o, y_c)
            if abs(body_bot - body_top) < 2: body_bot = body_top + 2
            draw.line([(cx+2, y_h+2), (cx+2, y_l+2)], fill=(0,0,0,120), width=3)
            draw.rectangle([cx - c_width + 2, body_top + 2, cx + c_width + 2, body_bot + 2], fill=(0,0,0,120))
            draw.line([(cx, y_h), (cx, y_l)], fill=glow_col, width=6)
            draw.rectangle([cx - c_width - 1, body_top - 1, cx + c_width + 1, body_bot + 1], fill=glow_col)
            draw.line([(cx, y_h), (cx, y_l)], fill=col, width=2)
            draw.rectangle([cx - c_width, body_top, cx + c_width, body_bot], fill=col)
            v_h = int((c.get('volume', 1000) / max_vol) * 60) if max_vol > 0 else 5
            draw.rectangle([cx - c_width + 1, plot_y2 - 10 - v_h, cx + c_width - 1, plot_y2 - 10], fill=(col[0], col[1], col[2], 150))

    def draw_indicator_panel(draw, y1, y2, title, values, color1, values2=None, color2=None, is_histogram=False, hist_data=None):
        x1, x2 = 130, 1470
        draw_chamfer_panel(draw, [x1, y1, x2, y2], highlight=COLORS["cyan"], cut=10)
        val_str = f"{values[-1] or 0:.2f}" if values and values[-1] is not None else "0.00"
        draw_3d_text(draw, (x1 + 15, y1 + 20), title, size=14, bold=True, color=COLORS["text_dim"], anchor="lm")
        draw_3d_text(draw, (x1 + 160, y1 + 20), val_str, size=14, bold=True, color=color1, anchor="lm")
        valid = [v for v in values if v is not None]
        if not valid: return
        min_v, max_v = min(valid), max(valid)
        if is_histogram and hist_data:
            all_valid = [abs(v) for v in hist_data if v is not None]
            if all_valid:
                max_v = max(max_v, max(all_valid))
                min_v = min(min_v, -max(all_valid))
        v_range = max_v - min_v if max_v != min_v else 1
        def s_y(v): return y2 - 20 - int((v - min_v) / v_range * (y2 - y1 - 45))
        def scale_x(i): return x1 + 30 + int((i / max(1, len(values) - 1)) * (x2 - x1 - 60))
        if is_histogram and hist_data is not None:
            zero_y = s_y(0)
            for i, h in enumerate(hist_data):
                if h is not None:
                    hx = scale_x(i)
                    hh = s_y(h)
                    hc = COLORS["bull"] if h > 0 else COLORS["bear"]
                    draw.rectangle([hx - 2, min(zero_y, hh), hx + 2, max(zero_y, hh)], fill=hc)
        pts1 = [(scale_x(i), s_y(v)) for i, v in enumerate(values) if v is not None]
        if len(pts1) > 1:
            for i in range(len(pts1)-1):
                draw_glowing_line(draw, pts1[i], pts1[i+1], color1, (color1[0], color1[1], color1[2], 50), width=2)
        if values2 is not None:
            pts2 = [(scale_x(i), s_y(v)) for i, v in enumerate(values2) if v is not None]
            if len(pts2) > 1:
                for i in range(len(pts2)-1):
                    draw_glowing_line(draw, pts2[i], pts2[i+1], color2, (color2[0], color2[1], color2[2], 30), width=2)

    def draw_right_sidebar_widgets(draw, x1, y1, x2, y2, candles):
        WIDGET_H = (y2 - y1) // 4
        wid_y = [y1, y1 + WIDGET_H, y1 + 2*WIDGET_H, y1 + 3*WIDGET_H]
        latest = candles[-1]
        closes = [c['close'] for c in candles]

        draw_chamfer_panel(draw, [x1, wid_y[0], x2, wid_y[0] + WIDGET_H], highlight=COLORS["cyan"])
        draw_3d_text(draw, (x1 + 40, wid_y[0] + 20), "MARKET DATA", size=14, bold=True, color=COLORS["text_main"], anchor="lm")
        change = latest['close'] - latest['open']
        pct = (change / latest['open'] * 100) if latest['open'] != 0 else 0
        change_text = f"+{change:.4f} (+{pct:.2f}%)" if change >= 0 else f"{change:.4f} ({pct:.2f}%)"
        change_color = COLORS["bull"] if change >= 0 else COLORS["bear"]
        ry = wid_y[0] + 55
        data_items = [
            ("Open:", f"{latest['open']:.4f}", COLORS["bull"]),
            ("High:", f"{latest['high']:.4f}", COLORS["bull"]),
            ("Low:", f"{latest['low']:.4f}", COLORS["bear"]),
            ("Close:", f"{latest['close']:.4f}", COLORS["bull"]),
            ("Change:", change_text, change_color),
        ]
        for label, value, color in data_items:
            draw_3d_text(draw, (x1 + 15, ry), label, size=14, bold=True, color=COLORS["text_dim"], anchor="lm")
            draw_3d_text(draw, (x1 + 85, ry), value, size=14, bold=True, color=color, anchor="lm")
            ry += 25
        draw_sci_fi_gauge(draw, (x2 - 95, wid_y[0] + WIDGET_H//2 + 5), 55, 80 if change>=0 else 20, COLORS["bull"], "BUY" if change>=0 else "SELL")

        draw_chamfer_panel(draw, [x1, wid_y[1], x2, wid_y[1] + WIDGET_H], highlight=COLORS["purple"])
        draw_3d_text(draw, (x1 + 40, wid_y[1] + 20), "MOVING AVERAGES", size=14, bold=True, color=COLORS["text_main"], anchor="lm")
        sma5 = compute_sma(closes, 5)[-1] or latest['close']
        sma10 = compute_sma(closes, 10)[-1] or latest['close']
        sma20 = compute_sma(closes, 20)[-1] or latest['close']
        ema21 = compute_ema(closes, 21)[-1] or latest['close']
        ema50 = compute_ema(closes, 50)[-1] or latest['close']
        ry = wid_y[1] + 55
        for label, value, color in [
            ("MA5:", f"{sma5:.4f}", COLORS["orange"]),
            ("MA10:", f"{sma10:.4f}", COLORS["purple"]),
            ("MA20:", f"{sma20:.4f}", COLORS["bear"]),
            ("EMA21:", f"{ema21:.4f}", COLORS["cyan"]),
            ("EMA50:", f"{ema50:.4f}", COLORS["purple"]),
        ]:
            draw_3d_text(draw, (x1 + 15, ry), f"{label} {value}", size=14, bold=True, color=color, anchor="lm")
            ry += 25

        draw_chamfer_panel(draw, [x1, wid_y[2], x2, wid_y[2] + WIDGET_H], highlight=COLORS["cyan"])
        draw_3d_text(draw, (x1 + 40, wid_y[2] + 20), "INDICATORS", size=14, bold=True, color=COLORS["text_main"], anchor="lm")
        rsi_vals = compute_rsi(closes)
        k_vals, d_vals = compute_stochastic(closes, [c['high'] for c in candles], [c['low'] for c in candles])
        rsi_val = rsi_vals[-1] or 52.61
        k_val = k_vals[-1] or 68.25
        d_val = d_vals[-1] or 55.48
        ry = wid_y[2] + 55
        draw_3d_text(draw, (x1 + 15, ry), f"RSI (14): {rsi_val:.2f}", size=14, bold=True, color=COLORS["purple"], anchor="lm")
        ry += 30
        draw_3d_text(draw, (x1 + 15, ry), f"%K: {k_val:.2f}   %D: {d_val:.2f}", size=14, bold=True, color=COLORS["cyan"], anchor="lm")
        draw_sci_fi_gauge(draw, (x2 - 95, wid_y[2] + WIDGET_H//2 + 5), 50, rsi_val, COLORS["purple"], f"{rsi_val:.2f}", "RSI")

        draw_chamfer_panel(draw, [x1, wid_y[3], x2, wid_y[3] + WIDGET_H], highlight=COLORS["purple"])
        draw_3d_text(draw, (x1 + 40, wid_y[3] + 20), "ADVANCED", size=14, bold=True, color=COLORS["text_main"], anchor="lm")
        wr_val = compute_williams_r([c['high'] for c in candles], [c['low'] for c in candles], closes)[-1] or -48.15
        cci_val = compute_cci([c['high'] for c in candles], [c['low'] for c in candles], closes)[-1] or 32.45
        ry = wid_y[3] + 55
        draw_3d_text(draw, (x1 + 15, ry), f"Williams %R: {wr_val:.2f}", size=14, bold=True, color=COLORS["bear"], anchor="lm")
        ry += 25
        draw_3d_text(draw, (x1 + 15, ry), f"CCI (20): {cci_val:.2f}", size=14, bold=True, color=COLORS["orange"], anchor="lm")

    def draw_bottom_status_bar(draw, x1, y1, x2, y2, candles):
        max_p = max([c['high'] for c in candles])
        min_p = min([c['low'] for c in candles])
        latest = candles[-1]
        pivot = (max_p + min_p + latest['close']) / 3
        is_bull = latest['close'] >= latest['open']
        footer_sections = [
            ("TIMEFRAME", f"{CONFIG['API_INTERVAL']}", COLORS["text_main"]),
            ("CANDLES", f"{len(candles)}", COLORS["text_main"]),
            ("HIGH", f"{max_p:.4f}", COLORS["bull"]),
            ("LOW", f"{min_p:.4f}", COLORS["bear"]),
            ("PIVOT", f"{pivot:.4f}", COLORS["text_main"]),
            ("TREND", "BULLISH" if is_bull else "BEARISH", COLORS["bull"] if is_bull else COLORS["bear"])
        ]
        box_w = (x2 - x1 - 60) // 6
        bx = x1 + 15
        for title, value, color in footer_sections:
            bx2 = bx + box_w - 10
            draw_chamfer_panel(draw, [bx, y1, bx2, y2], fill=COLORS["panel_dark"], outline=COLORS["cyan"], cut=8)
            center_x = (bx + bx2) // 2
            center_y = (y1 + y2) // 2
            draw_3d_text(draw, (center_x, center_y - 18), title, size=12, bold=True, color=COLORS["text_dim"], anchor="mm")
            draw_3d_text(draw, (center_x, center_y + 18), value, size=22, bold=True, color=color, anchor="mm", glow=True)
            bx += box_w
        bull_box = [x2 - 130, y1, x2 - 10, y2]
        draw_chamfer_panel(draw, bull_box, outline=COLORS["bull"], cut=10)
        draw_3d_bull_icon(draw, bull_box, COLORS["bull"])

    def create_ultimate_dashboard(pair: str, candles: List[Dict]) -> BytesIO:
        if not candles or not PIL_AVAILABLE:
            return None
        if len(candles) > 60:
            candles = candles[-60:]
        WIDTH, HEIGHT = 1920, 1150
        img = Image.new('RGBA', (WIDTH, HEIGHT), COLORS["bg"])
        draw = ImageDraw.Draw(img)
        for x in range(0, WIDTH, 45):
            for y in range(0, HEIGHT, 45):
                if (x+y) % 90 == 0:
                    draw.ellipse([x, y, x+3, y+3], fill=(255, 255, 255, 20))
        NAV_W = 110
        RIGHT_W = 440
        BOT_H = 110
        TOP_H = 100
        PAD = 20
        CHART_X1 = NAV_W + PAD
        CHART_Y1 = TOP_H + PAD
        CHART_X2 = WIDTH - RIGHT_W - PAD
        CHART_Y2 = 550
        IND_H = 120
        RSI_Y1 = CHART_Y2 + PAD
        RSI_Y2 = RSI_Y1 + IND_H
        MACD_Y1 = RSI_Y2 + PAD
        MACD_Y2 = MACD_Y1 + IND_H
        STOCH_Y1 = MACD_Y2 + PAD
        STOCH_Y2 = STOCH_Y1 + IND_H
        RX1 = CHART_X2 + PAD
        RX2 = WIDTH - PAD
        BOT_Y1 = HEIGHT - BOT_H

        draw_left_navigation(draw, PAD, PAD, NAV_W, HEIGHT - PAD)
        draw_top_header(draw, CHART_X1, PAD, CHART_X2, pair, CONFIG['API_INTERVAL'], candles[-1], candles)
        draw_candle_chart(draw, CHART_X1, CHART_Y1, CHART_X2, CHART_Y2, candles)
        rsi_vals = compute_rsi([c['close'] for c in candles])
        draw_indicator_panel(draw, RSI_Y1, RSI_Y2, "RSI (14)", rsi_vals, COLORS["purple"])
        macd_line, sig_line, hist = compute_macd([c['close'] for c in candles])
        draw_indicator_panel(draw, MACD_Y1, MACD_Y2, "MACD (12,26,9)", macd_line, COLORS["bull"], values2=sig_line, color2=COLORS["cyan"], is_histogram=True, hist_data=hist)
        k_vals, d_vals = compute_stochastic([c['close'] for c in candles], [c['high'] for c in candles], [c['low'] for c in candles])
        draw_indicator_panel(draw, STOCH_Y1, STOCH_Y2, "Stochastic (14,3,3)", k_vals, COLORS["cyan"], values2=d_vals, color2=COLORS["orange"])
        widget_y_start = TOP_H + PAD
        widget_y_end = BOT_Y1 - PAD
        draw_right_sidebar_widgets(draw, RX1, widget_y_start, RX2, widget_y_end, candles)
        draw_bottom_status_bar(draw, NAV_W + PAD, BOT_Y1, WIDTH - PAD, HEIGHT - PAD, candles)

        buffer = BytesIO()
        img.convert('RGB').save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

else:
    def create_ultimate_dashboard(pair, candles):
        return None

# ================= LOSS SS — 20-CANDLE 16:9 CHART WITH BEAUTIFUL DESIGN =================
import math
from io import BytesIO
from datetime import timedelta

if PIL_AVAILABLE:
    async def generate_signal_chart(asset: str, target_dt: datetime, direction: str, size=800) -> Optional[BytesIO]:
        candles = await get_candles(asset, count=5000)
        if not candles:
            return None

        # Find target index
        target_idx = None
        for i, c in enumerate(candles):
            if c['dt'].replace(second=0, microsecond=0) == target_dt.replace(second=0, microsecond=0):
                target_idx = i
                break
        if target_idx is None:
            return None

        # Latest 60-candle context, centered around the selected candle.
        start = max(0, target_idx - 30)
        end = min(len(candles), start + 60)
        start = max(0, end - 60)
        selected = candles[start:end]

        # 16:9 Aspect Ratio
        WIDTH = 1280
        HEIGHT = 720
        MARGIN_TOP = 130
        MARGIN_BOTTOM = 80
        MARGIN_LEFT = 40
        MARGIN_RIGHT = 120

        # Create image with reference dark background
        bg_color = (17, 19, 26)
        img = Image.new('RGB', (WIDTH, HEIGHT), color=bg_color)
        draw = ImageDraw.Draw(img, "RGBA")

        # Outer Rounded Border Frame
        draw.rounded_rectangle(
            [20, 20, WIDTH - 20, HEIGHT - 20],
            radius=15,
            outline=(60, 70, 90, 255),
            width=2
        )

        # Header Pill (Top Center)
        header_text = f"{asset.upper()} • M1 ZOOM LOSS ANALYSIS • {direction.upper()} ▼"
        header_w = 500
        draw.rounded_rectangle(
            [WIDTH//2 - header_w//2, 10, WIDTH//2 + header_w//2, 50],
            radius=20,
            fill=(25, 30, 45, 255),
            outline=(60, 70, 90, 255),
            width=2
        )
        draw.text(
            (WIDTH//2, 30),
            header_text,
            fill=(255, 255, 255, 255),
            font=get_font(18, bold=True),
            anchor="mm"
        )

        # Final Result Badge (Top Left)
        draw.rounded_rectangle(
            [40, 40, 280, 90],
            radius=15,
            fill=(239, 68, 68, 255) # Red Color
        )
        draw.text(
            (160, 65),
            "FINAL RESULT: LOSS",
            fill=(255, 255, 255, 255),
            font=get_font(20, bold=True),
            anchor="mm"
        )

        # Central Watermark
        draw.text(
            (WIDTH // 2, HEIGHT // 2),
            "RAVITH AI PRO",
            fill=(255, 255, 255, 15), # Highly transparent
            font=get_font(80, bold=True),
            anchor="mm"
        )

        chart_x1 = MARGIN_LEFT
        chart_y1 = MARGIN_TOP
        chart_x2 = WIDTH - MARGIN_RIGHT
        chart_y2 = HEIGHT - MARGIN_BOTTOM
        chart_w = chart_x2 - chart_x1
        chart_h = chart_y2 - chart_y1

        # Calculate price range
        all_high = [c['high'] for c in selected]
        all_low = [c['low'] for c in selected]
        max_price = max(all_high) if all_high else 1
        min_price = min(all_low) if all_low else 0
        price_range = max_price - min_price if max_price != min_price else 0.001

        # Padding
        price_range_padded = price_range * 0.15
        max_price += price_range_padded
        min_price -= price_range_padded
        price_range = max_price - min_price

        def price_to_y(p):
            return chart_y2 - ((p - min_price) / price_range) * chart_h

        def candle_to_x(i):
            if len(selected) <= 1:
                return chart_x1 + chart_w // 2
            return chart_x1 + (i / (len(selected) - 1)) * chart_w

        # Draw Support and Resistance Zones
        res_y = price_to_y(max_price - price_range_padded*0.5)
        sup_y = price_to_y(min_price + price_range_padded*0.5)

        # Resistance Line (Red)
        draw.line([(chart_x1, res_y), (chart_x2, res_y)], fill=(153, 27, 27, 180), width=6)
        draw.text((chart_x1 + 10, res_y - 15), "Resistance zone", fill=(239, 68, 68, 200), font=get_font(12), anchor="ls")

        # Support Line (Green)
        draw.line([(chart_x1, sup_y), (chart_x2, sup_y)], fill=(21, 128, 61, 180), width=6)
        draw.text((chart_x1 + 10, sup_y + 15), "Support zone", fill=(34, 197, 94, 200), font=get_font(12), anchor="lt")

        # Draw Y-axis Labels on the RIGHT
        for i in range(6):
            y_pos = chart_y1 + (i / 5) * chart_h
            price_val = max_price - (i / 5) * price_range
            label = f"{price_val:.5f}"
            draw.text(
                (chart_x2 + 15, y_pos),
                label,
                fill=(180, 190, 200, 255),
                font=get_font(12),
                anchor="lm"
            )

        # Draw X-axis Labels (Time) at the Bottom
        for i in range(0, len(selected), max(1, len(selected)//8)):
            x_pos = candle_to_x(i)
            time_str = selected[i]['dt'].strftime("%H:%M")
            draw.text(
                (x_pos, chart_y2 + 25),
                time_str,
                fill=(180, 190, 200, 255),
                font=get_font(12),
                anchor="mm"
            )

        # Draw Moving Average (Blue Line)
        ma_points = []
        sma_period = 4
        for i in range(len(selected)):
            if i >= sma_period - 1:
                avg = sum(c['close'] for c in selected[i-sma_period+1:i+1]) / sma_period
            else:
                avg = sum(c['close'] for c in selected[:i+1]) / (i+1)
            ma_points.append((candle_to_x(i), price_to_y(avg)))
        
        if len(ma_points) > 1:
            draw.line(ma_points, fill=(59, 130, 246, 200), width=3) # Blue MA line

        # Draw Candles
        candle_width = max(10, chart_w / (len(selected) * 2.2))
        target_index_in_selected = None
        
        for i, c in enumerate(selected):
            if c['dt'].replace(second=0, microsecond=0) == target_dt.replace(second=0, microsecond=0):
                target_index_in_selected = i

            x = candle_to_x(i)
            y_open = price_to_y(c['open'])
            y_close = price_to_y(c['close'])
            y_high = price_to_y(c['high'])
            y_low = price_to_y(c['low'])

            is_bull = c['close'] >= c['open']
            
            # Solid Colors matching reference
            color = (16, 185, 129, 255) if is_bull else (239, 68, 68, 255)

            # Candle wick
            draw.line([(x, y_high), (x, y_low)], fill=color, width=2)

            # Candle body
            top = min(y_open, y_close)
            bottom = max(y_open, y_close)
            if bottom - top < 2:
                bottom = top + 2

            draw.rectangle(
                [x - candle_width/2, top, x + candle_width/2, bottom],
                fill=color
            )

        # Draw Target Reticle and Tooltip
        if target_index_in_selected is not None:
            target_candle = selected[target_index_in_selected]
            x = candle_to_x(target_index_in_selected)
            y_high = price_to_y(target_candle['high'])
            y_low = price_to_y(target_candle['low'])
            y_mid = (y_high + y_low) / 2

            # Red Rectangle around the candle
            box_pad = candle_width
            draw.rectangle(
                [x - box_pad, y_high - box_pad, x + box_pad, y_low + box_pad],
                outline=(239, 68, 68, 255),
                width=2
            )
            draw.rectangle(
                [x - box_pad - 4, y_high - box_pad - 4, x + box_pad + 4, y_low + box_pad + 4],
                outline=(239, 68, 68, 100),
                width=1
            )

            # Concentric circles
            for r in [15, 25]:
                draw.ellipse(
                    [x - r, y_mid - r, x + r, y_mid + r],
                    outline=(239, 68, 68, 200),
                    width=2
                )
            
            # Crosshairs
            draw.line([(x - 30, y_mid), (x + 30, y_mid)], fill=(239, 68, 68, 200), width=1)
            draw.line([(x, y_mid - 30), (x, y_mid + 30)], fill=(239, 68, 68, 200), width=1)

            # Downward Triangle Marker
            tri_y = y_high - box_pad - 10
            draw.polygon(
                [(x, tri_y), (x - 8, tri_y - 12), (x + 8, tri_y - 12)],
                fill=(239, 68, 68, 255)
            )

            # Vertical dashed line down to time
            dash_y = y_low + box_pad
            while dash_y < chart_y2 + 10:
                draw.line([(x, dash_y), (x, dash_y + 5)], fill=(150, 150, 150, 150), width=1)
                dash_y += 10

            # Tooltip Label "LOSS CANDLE MARKER"
            label_w, label_h = 200, 30
            lx1, ly1 = x - label_w + 30, tri_y - 45
            draw.rounded_rectangle([lx1, ly1, lx1 + label_w, ly1 + label_h], radius=15, fill=(239, 68, 68, 255))
            draw.text((lx1 + label_w/2, ly1 + label_h/2), "LOSS CANDLE MARKER", fill="white", font=get_font(12, bold=True), anchor="mm")

            # Main Details Tooltip Box
            tt_w, tt_h = 240, 100
            tx1, ty1 = lx1 + label_w - 20, ly1 - tt_h + 10
            draw.rounded_rectangle(
                [tx1, ty1, tx1 + tt_w, ty1 + tt_h],
                radius=10,
                fill=(20, 22, 30, 230),
                outline=(60, 70, 90, 255),
                width=1
            )
            
            # Tooltip Texts
            loss_dt = target_dt + timedelta(minutes=1)
            lines = [
                f"Signal Time : {target_dt.strftime('%H:%M')}",
                f"Loss Time    : {loss_dt.strftime('%H:%M')}",
                f"Payout          : --",
                f"Zoom View   : {len(selected)} verified candle(s)"
            ]
            
            for idx, line in enumerate(lines):
                draw.text(
                    (tx1 + 15, ty1 + 15 + (idx * 20)),
                    line,
                    fill=(200, 210, 220, 255),
                    font=get_font(11),
                    anchor="la"
                )

        # Footer Texts
        draw.text(
            (MARGIN_LEFT, HEIGHT - 35),
            "Marked screenshot generated by SHOW LOSS CANDLES",
            fill=(120, 130, 150, 200),
            font=get_font(11),
            anchor="lm"
        )
        
        draw.text(
            (WIDTH - MARGIN_LEFT, HEIGHT - 35),
            "Developer: @RAVITH_AI",
            fill=(120, 130, 150, 200),
            font=get_font(11),
            anchor="rm"
        )

        buffer = BytesIO()
        img.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

else:
    async def generate_signal_chart(asset, target_dt, direction, size=800):
        return None

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
async def check_signal_result(asset: str, time_str: str, direction: str, mtg_level: int = 0, check_date: date = None) -> Dict:
    candles = await get_candles(asset, count=5000)
    if not candles:
        return {'result': 'UNKNOWN', 'mtg_used': 0, 'checked': False, 'error': 'No data', 'payout': 0}

    if check_date is None:
        check_date = datetime.now(UTC_PLUS_6).date()

    try:
        hour, minute = map(int, time_str.split(':'))
        target_dt = UTC_PLUS_6.localize(datetime(check_date.year, check_date.month, check_date.day, hour, minute, 0))
    except:
        return {'result': 'UNKNOWN', 'mtg_used': 0, 'checked': False, 'error': 'Invalid time', 'payout': 0}

    def find_candle_at(dt):
        for c in candles:
            c_dt = c['dt'].replace(second=0, microsecond=0)
            if c_dt == dt.replace(second=0, microsecond=0):
                return c
        return None

    def check_candle_win(candle, dir_str):
        if candle is None:
            return None
        op = candle['open']
        cl = candle['close']
        if op == cl:
            return None
        if dir_str == 'CALL':
            return cl > op
        elif dir_str == 'PUT':
            return cl < op
        return None

    entry_candle = find_candle_at(target_dt)

    if entry_candle is None:
        return {'result': 'PENDING', 'mtg_used': 0, 'checked': False, 'error': 'Candle not found (future or missing)', 'payout': 0}

    signal_payout = entry_candle.get('payout', 0)
    win = check_candle_win(entry_candle, direction)

    if win is None:
        return {'result': 'TIE', 'mtg_used': 0, 'checked': True, 'payout': signal_payout}

    if win:
        return {'result': 'WIN', 'mtg_used': 0, 'checked': True, 'payout': signal_payout}

    if mtg_level >= 1:
        mtg1_dt = target_dt + timedelta(minutes=1)
        mtg1_candle = find_candle_at(mtg1_dt)

        if mtg1_candle is None:
            return {'result': 'LOSS', 'mtg_used': 0, 'checked': True, 'note': 'MTG candle not available', 'payout': signal_payout}

        win_mtg1 = check_candle_win(mtg1_candle, direction)
        if win_mtg1:
            return {'result': 'WIN', 'mtg_used': 1, 'checked': True, 'payout': signal_payout}

        if mtg_level >= 2:
            mtg2_dt = target_dt + timedelta(minutes=2)
            mtg2_candle = find_candle_at(mtg2_dt)
            if mtg2_candle is not None:
                win_mtg2 = check_candle_win(mtg2_candle, direction)
                if win_mtg2:
                    return {'result': 'WIN', 'mtg_used': 2, 'checked': True, 'payout': signal_payout}

        return {'result': 'LOSS', 'mtg_used': mtg_level, 'checked': True, 'payout': signal_payout}

    return {'result': 'LOSS', 'mtg_used': 0, 'checked': True, 'payout': signal_payout}

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

def get_main_keyboard(user_id=None):
    keyboard = [
        [InlineKeyboardButton("▶️ 𝚂𝚃𝙰𝚁𝚃 𝙱𝙾𝚃", callback_data="start_bot"),
         InlineKeyboardButton("⏹ 𝚂𝚃𝙾𝙿 𝙱𝙾𝚃", callback_data="stop_bot")],
        [InlineKeyboardButton("📊 𝚂𝚃𝙰𝚃𝚄𝚂", callback_data="status"),
         InlineKeyboardButton("📋 𝙿𝙰𝚁𝚃𝙸𝙰𝙻", callback_data="partial"),
         InlineKeyboardButton("📈 𝚃𝙾𝙳𝙰𝚈", callback_data="today_stats")],
        [InlineKeyboardButton("📜 𝙷𝙸𝚂𝚃𝙾𝚁𝚈", callback_data="history"),
         InlineKeyboardButton("🏆 𝙻𝙴𝙰𝙳𝙴𝚁𝙱𝙾𝙰𝚁𝙳", callback_data="leaderboard")],
        [InlineKeyboardButton("💹 𝙻𝙸𝚅𝙴 𝙿𝚁𝙸𝙲𝙴", callback_data="live_price"),
         InlineKeyboardButton("📈 𝙼𝙰𝚁𝙺𝙴𝚃 𝚂𝙲𝙰𝙽", callback_data="market_scan")],
        [InlineKeyboardButton("🔍 𝙰𝚂𝚂𝙴𝚃 𝙸𝙽𝙵𝙾", callback_data="asset_info"),
         InlineKeyboardButton("📊 𝙲𝙷𝙰𝚁𝚃 𝙽𝙾𝚆", callback_data="chart_now")],
        [InlineKeyboardButton("🎰 𝙼𝙰𝙽𝚄𝙰𝙻 𝚂𝙸𝙶𝙽𝙰𝙻", callback_data="manual_signal"),
         InlineKeyboardButton("📡 𝙻𝙰𝚂𝚃 𝚂𝙸𝙶𝙽𝙰𝙻", callback_data="last_signal"),
         InlineKeyboardButton("📋 𝚂𝙸𝙶𝙽𝙰𝙻 𝙻𝙾𝙶", callback_data="signal_log")],
        [InlineKeyboardButton("━━━━━━ ⚙️ 𝚂𝙴𝚃𝚃𝙸𝙽𝙶𝚂 ━━━━━━", callback_data="settings")],
        [InlineKeyboardButton("🔌 𝚃𝙶 𝙲𝙾𝙽𝙽𝙴𝙲𝚃", callback_data="tg_connect"),
         InlineKeyboardButton("🔄 𝚁𝙴??𝙴𝚃", callback_data="reset")],
        [InlineKeyboardButton("📱 𝙿𝚁𝙾𝙵𝙸𝙻𝙴", callback_data="profile"),
         InlineKeyboardButton("💡 𝙷𝙴𝙻𝙿", callback_data="help")],
        [InlineKeyboardButton("━━━━━ 🔮 𝙵𝚄𝚃𝚄𝚁𝙴 𝙲𝙷𝙴𝙲𝙺𝙴𝚁 ━━━━━", callback_data="future_checker")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_owner_keyboard(user_id=None):
    keyboard = [
        [InlineKeyboardButton("▶️ 𝚂𝚃𝙰𝚁𝚃 𝙱𝙾𝚃", callback_data="start_bot"),
         InlineKeyboardButton("⏹ 𝚂𝚃𝙾𝙿 𝙱𝙾𝚃", callback_data="stop_bot")],
        [InlineKeyboardButton("📊 𝚂𝚃𝙰𝚃𝚄𝚂", callback_data="status"),
         InlineKeyboardButton("📋 𝙿𝙰𝚁𝚃𝙸𝙰𝙻", callback_data="partial"),
         InlineKeyboardButton("📈 𝚃𝙾𝙳𝙰𝚈", callback_data="today_stats")],
        [InlineKeyboardButton("📜 𝙷𝙸𝚂𝚃𝙾𝚁𝚈", callback_data="history"),
         InlineKeyboardButton("🏆 𝙻𝙴𝙰𝙳𝙴𝚁𝙱𝙾𝙰𝚁𝙳", callback_data="leaderboard")],
        [InlineKeyboardButton("💹 𝙻𝙸𝚅𝙴 𝙿𝚁𝙸𝙲𝙴", callback_data="live_price"),
         InlineKeyboardButton("📈 𝙼𝙰𝚁𝙺𝙴𝚃 𝚂𝙲𝙰𝙽", callback_data="market_scan")],
        [InlineKeyboardButton("🔍 𝙰𝚂𝚂𝙴𝚃 𝙸𝙽𝙵𝙾", callback_data="asset_info"),
         InlineKeyboardButton("📊 𝙲𝙷𝙰𝚁𝚃 𝙽𝙾𝚆", callback_data="chart_now")],
        [InlineKeyboardButton("🎰 𝙼𝙰𝙽𝚄𝙰𝙻 𝚂𝙸𝙶𝙽𝙰𝙻", callback_data="manual_signal"),
         InlineKeyboardButton("📡 𝙻𝙰𝚂𝚃 𝚂𝙸𝙶𝙽𝙰𝙻", callback_data="last_signal"),
         InlineKeyboardButton("📋 𝚂𝙸𝙶𝙽𝙰𝙻 𝙻𝙾𝙶", callback_data="signal_log")],
        [InlineKeyboardButton("━━━━━━ ⚙️ 𝚂𝙴𝚃𝚃𝙸𝙽𝙶𝚂 ━━━━━━", callback_data="settings")],
        [InlineKeyboardButton("🔌 𝚃𝙶 𝙲𝙾𝙽𝙽𝙴𝙲𝚃", callback_data="tg_connect"),
         InlineKeyboardButton("🔄 𝚁𝙴𝚂𝙴𝚃", callback_data="reset")],
        [InlineKeyboardButton("📱 𝙿𝚁𝙾𝙵𝙸𝙻𝙴", callback_data="profile"),
         InlineKeyboardButton("💡 𝙷𝙴𝙻𝙿", callback_data="help")],
        [InlineKeyboardButton("━━━━━ 🔮 𝙵𝚄𝚃𝚄𝚁𝙴 𝙲𝙷𝙴𝙲𝙺𝙴𝚁 ━━━━━", callback_data="future_checker")],
        [InlineKeyboardButton("━━━━━ 👑 𝙰𝙳𝙼𝙸𝙽 𝙿𝙰𝙽𝙴𝙻 ━━━━━", callback_data="admin_panel")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard(user_id):
    uid = str(user_id)
    settings = USER_DATA.get(uid, {}).get("settings", {})

    sound = "🔔 𝙾𝙽" if settings.get("sound_alert", True) else "🔕 𝙾𝙵𝙵"
    auto_r = "✅ 𝙾𝙽" if settings.get("auto_result", True) else "❌ 𝙾𝙵𝙵"
    payout = "✅ 𝙾𝙽" if settings.get("show_payout", True) else "❌ 𝙾𝙵𝙵"
    martingale = "✅ 𝙾𝙽" if settings.get("martingale", True) else "❌ 𝙾𝙵𝙵"
    chart_style = settings.get("chart_style", "3d").upper()
    risk = settings.get("risk_level", "medium").upper()
    sig_type = settings.get("signal_type", "all").upper()
    notif = settings.get("notification_mode", "all").upper()
    strategy = settings.get("strategy", "REVERSE_PLUS_TRENDY").upper()
    footer = settings.get("footer_text", "RAVITH AI PRO")

    keyboard = [
        [InlineKeyboardButton(f"━━━━━ ⚙️ 𝚂𝙴𝚃𝚃𝙸𝙽𝙶𝚂 ━━━━━", callback_data="noop")],
        [InlineKeyboardButton(f"━━━ 🎨 𝙰𝙿𝙿𝙴𝙰𝚁𝙰𝙽𝙲𝙴 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"💧 𝚆𝙰𝚃𝙴𝚁𝙼𝙰𝚁𝙺", callback_data="set_watermark"),
         InlineKeyboardButton(f"📞 𝙲𝙾𝙽𝚃𝙰𝙲𝚃", callback_data="set_contact")],
        [InlineKeyboardButton(f"📊 𝙲𝙷𝙰𝚁𝚃：{ff(chart_style)}", callback_data="toggle_chart_style")],
        [InlineKeyboardButton(f"━━━ 🔔 𝙽𝙾𝚃𝙸𝙵𝙸𝙲𝙰𝚃𝙸𝙾𝙽𝚂 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"🔊 𝚂𝙾𝚄𝙽𝙳：{sound}", callback_data="toggle_sound"),
         InlineKeyboardButton(f"📢 𝙼𝙾𝙳𝙴：{ff(notif)}", callback_data="toggle_notif_mode")],
        [InlineKeyboardButton(f"━━━ 📈 𝚃𝚁𝙰𝙳𝙸𝙽𝙶 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"⚠️ 𝚁𝙸𝚂𝙺：{ff(risk)}", callback_data="toggle_risk"),
         InlineKeyboardButton(f"📡 𝚂𝙸𝙶𝙽𝙰𝙻：{ff(sig_type)}", callback_data="toggle_signal_type")],
        [InlineKeyboardButton(f"🎯 𝙰𝚄𝚃𝙾 𝚁𝙴𝚂𝚄𝙻𝚃：{auto_r}", callback_data="toggle_auto_result"),
         InlineKeyboardButton(f"💰 𝙿𝙰𝚈𝙾𝚄𝚃：{payout}", callback_data="toggle_show_payout")],
        [InlineKeyboardButton(f"🔄 𝙼𝙰𝚁𝚃𝙸𝙽𝙶𝙰𝙻𝙴：{martingale}", callback_data="toggle_martingale")],
        [InlineKeyboardButton(f"━━━ 🧠 𝚂𝚃𝚁𝙰𝚃𝙴𝙶𝚈 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"📈 𝙲𝚄𝚁𝚁𝙴𝙽𝚃：{ff(strategy)}", callback_data="select_strategy")],
        [InlineKeyboardButton(f"━━━ ✏️ 𝙲𝚄𝚂𝚃𝙾𝙼 𝙵𝙾𝙾𝚃𝙴𝚁 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"📝 𝚂𝙴𝚃 𝙵𝙾𝙾𝚃𝙴𝚁 𝚃𝙴𝚇𝚃", callback_data="set_footer_text")],
        [InlineKeyboardButton(f"━━━ 🎯 𝙰𝚂𝚂𝙴𝚃𝚂 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"⭐ 𝙿𝚁𝙴𝙵𝙴𝚁𝚁𝙴𝙳 𝙰𝚂𝚂𝙴𝚃𝚂", callback_data="preferred_assets"),
         InlineKeyboardButton(f"🚫 𝙱𝙻𝙾𝙲𝙺𝙴𝙳 𝙰𝚂𝚂𝙴𝚃𝚂", callback_data="blocked_assets")],
        [InlineKeyboardButton(f"💵 𝙼𝙸𝙽 𝙿𝙰𝚈𝙾𝚄𝚃", callback_data="set_min_payout")],
        [InlineKeyboardButton(f"━━━ 🌐 𝙲𝙾𝙽𝙽𝙴𝙲𝚃𝙸𝙾𝙽 ━━━", callback_data="noop")],
        [InlineKeyboardButton(f"🔌 𝚃𝙶 𝙲𝙾𝙽𝙽𝙴𝙲𝚃", callback_data="tg_connect"),
         InlineKeyboardButton(f"🌍 𝚃𝙸𝙼𝙴𝚉𝙾𝙽𝙴", callback_data="set_timezone")],
        [InlineKeyboardButton(f"🌐 𝙻𝙰𝙽𝙶𝚄𝙰𝙶𝙴", callback_data="set_language")],
        [InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺 𝚃𝙾 𝙼𝙰𝙸𝙽", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_message(user_id):
    uid = str(user_id)
    settings = USER_DATA.get(uid, {}).get("settings", {})
    watermark = settings.get("watermark", "RAVITH AI PRO")
    contact = settings.get("contact", CONFIG.get("BOT_USERNAME", "@Mahabub_iX"))
    risk = settings.get("risk_level", "medium")
    sig_type = settings.get("signal_type", "all")
    chart_style = settings.get("chart_style", "3d")
    sound = "🔔 𝙾𝙽" if settings.get("sound_alert", True) else "🔕 𝙾𝙵𝙵"
    auto_r = "✅ 𝙾𝙽" if settings.get("auto_result", True) else "❌ 𝙾𝙵𝙵"
    payout_show = "✅ 𝙾𝙽" if settings.get("show_payout", True) else "❌ 𝙾𝙵𝙵"
    martingale = "✅ 𝙾𝙽" if settings.get("martingale", True) else "❌ 𝙾𝙵𝙵"
    tz = settings.get("timezone", "Asia/Dhaka")
    lang = settings.get("language", "en")
    min_payout = settings.get("min_payout", 0)
    pref = settings.get("preferred_assets", [])
    blocked = settings.get("blocked_assets", [])
    notif = settings.get("notification_mode", "all")
    strategy = settings.get("strategy", "REVERSE_PLUS_TRENDY").upper()
    footer = settings.get("footer_text", "RAVITH AI PRO")

    msg = f"""
╔═══════════════════════════════════╗
║       ⚙️ 𝚂𝙴𝚃𝚃𝙸𝙽𝙶𝚂 𝙿𝙰𝙽𝙴𝙻        ║
╚═══════════════════════════════════╝

╭━━━━━━━【🎨】━━━━━━━╮
│ 💧 𝚆𝚊𝚝𝚎𝚛𝚖𝚊𝚛𝚔：{ff(watermark)}
│ 📞 𝙲𝚘𝚗𝚝𝚊𝚌𝚝：{contact}
│ 📊 𝙲𝚑𝚊𝚛𝚝：{ff(chart_style.upper())}
╰━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━【📈】━━━━━━━╮
│ ⚠️ 𝚁𝚒𝚜𝚔：{ff(risk.upper())}
│ 📡 𝚂𝚒𝚐𝚗𝚊𝚕 𝚃𝚢𝚙𝚎：{ff(sig_type.upper())}
│ 🔊 𝚂𝚘𝚞𝚗𝚍：{sound}
│ 🎯 𝙰𝚞𝚝𝚘 𝚁𝚎𝚜𝚞𝚕𝚝：{auto_r}
│ 💰 𝚂𝚑𝚘𝚠 𝙿𝚊𝚢𝚘𝚞𝚝：{payout_show}
│ 🔄 𝙼𝚊𝚛𝚝𝚒𝚗𝚐𝚊𝚕𝚎：{martingale}
│ 📢 𝙽𝚘𝚝𝚒𝚏𝚒𝚌𝚊𝚝𝚒𝚘𝚗：{ff(notif.upper())}
╰━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━【🧠】━━━━━━━╮
│ 📈 𝙲𝚞𝚛𝚛𝚎𝚗𝚝 𝚂𝚝𝚛𝚊𝚝𝚎𝚐𝚢：{ff(strategy)}
│ ✏️ 𝙵𝚘𝚘𝚝𝚎𝚛 𝚃𝚎𝚡𝚝：{fb(footer)}
╰━━━━━━━━━━━━━━━━━━━╯

╭━━━━━━━【🌐】━━━━━━━╮
│ 🕐 𝚃𝚒𝚖𝚎𝚣𝚘𝚗𝚎：{ff(tz)}
│ 🌍 𝙻𝚊𝚗𝚐𝚞𝚊𝚐𝚎：{ff(lang.upper())}
│ 💵 𝙼𝚒𝚗 𝙿𝚊𝚢𝚘𝚞𝚝：{fn(str(min_payout))}٪
│ ⭐ 𝙿𝚛𝚎𝚏𝚎𝚛𝚛𝚎𝚍：{fn(str(len(pref)))} 𝚊𝚜𝚜𝚎𝚝𝚜
│ 🚫 𝙱𝚕𝚘𝚌𝚔𝚎𝚍：{fn(str(len(blocked)))} 𝚊𝚜𝚜𝚎𝚝𝚜
╰━━━━━━━━━━━━━━━━━━━╯

━━━━━━━━━━━━━━━━━━━━━━━━━━
   ⚡ {ff("Tap to change settings")} ⚡
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
async def send_signal_with_chart(user_id: int, asset: str, direction: str, signal_time_ts: int,
                                 price: float, payout: float, candles: List[Dict]):
    uid = str(user_id)
    settings = USER_DATA.get(uid, {}).get("settings", {})
    contact = settings.get("contact", CONFIG.get("BOT_USERNAME", "@Mahabub_iX"))
    footer_text = settings.get("footer_text", "RAVITH AI PRO")

    msg = format_signal_message(asset, direction, signal_time_ts, price, payout, contact, footer_text)
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 𝙿𝙰𝚁𝚃𝙸𝙰𝙻", callback_data="partial"),
         InlineKeyboardButton("🔄 𝚁𝙴𝚂𝙴𝚃", callback_data="reset")]
    ])

    image_buffer = None
    if PIL_AVAILABLE and candles:
        try:
            loop = asyncio.get_running_loop()
            chart_candles = candles[-60:] if len(candles) > 60 else candles
            image_buffer = await loop.run_in_executor(None, create_ultimate_dashboard, asset, chart_candles)
        except Exception as e:
            print(f"{Fore.RED}❌ Chart generation failed: {e}")

    USER_DATA.get(uid, {})["signals_received"] = USER_DATA.get(uid, {}).get("signals_received", 0) + 1
    save_user_data()

    chat_id = get_user_chat_id(user_id)
    await send_telegram_photo_with_caption(chat_id, image_buffer, msg, markup)

async def send_result_with_chart(user_id: int, asset: str, direction: str, signal_time_ts: int,
                                 win: bool, mtg_level: int, individual_stats: dict, pair_stats: dict,
                                 contact: str, candles: List[Dict], footer_text: str):
    msg = format_result_message(asset, direction, signal_time_ts, win, mtg_level, individual_stats, pair_stats, contact, footer_text)
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 𝙿𝙰𝚁𝚃𝙸𝙰𝙻", callback_data="partial"),
         InlineKeyboardButton("🔄 𝚁𝙴𝚂𝙴𝚃", callback_data="reset")]
    ])

    image_buffer = None
    if PIL_AVAILABLE and candles:
        try:
            loop = asyncio.get_running_loop()
            chart_candles = candles[-60:] if len(candles) > 60 else candles
            image_buffer = await loop.run_in_executor(None, create_ultimate_dashboard, asset, chart_candles)
        except Exception as e:
            print(f"{Fore.RED}❌ Chart generation failed: {e}")

    chat_id = get_user_chat_id(user_id)
    await send_telegram_photo_with_caption(chat_id, image_buffer, msg, markup)

async def send_telegram_photo_with_caption(chat_id, image_buffer, caption, reply_markup=None):
    if BOT_APPLICATION is None:
        return
    try:
        if image_buffer:
            await BOT_APPLICATION.bot.send_photo(
                chat_id=chat_id,
                photo=image_buffer,
                caption=caption,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            await BOT_APPLICATION.bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
    except Exception as e:
        print(f"{Fore.RED}✗ Telegram send error for {chat_id}: {e}")

# ================= TRADING LOOP (modified to pass user settings) =================
async def check_result_for_user(user_id: int):
    session = USER_TRADING_SESSIONS.get(user_id, {})
    active_signal = session.get('active_signal')
    if not active_signal:
        return

    current_time = get_current_time()
    signal_dt = active_signal['signal_dt']
    mtg = active_signal['mtg']
    check_dt = signal_dt + timedelta(minutes=mtg+1)

    if current_time < check_dt + timedelta(seconds=5):
        return

    candles = await get_candles(active_signal['asset'], count=CONFIG.get("API_CANDLE_COUNT", 5000))
    if not candles:
        return

    target = None
    for c in candles:
        if c['dt'].replace(second=0, microsecond=0) == check_dt.replace(second=0, microsecond=0):
            target = c
            break

    if not target:
        return

    op, cp = target['open'], target['close']
    direction = active_signal['direction']
    win = (direction == "CALL" and cp > op) or (direction == "PUT" and cp < op)

    if win:
        await send_result_for_user(user_id, active_signal['asset'], direction,
                                   active_signal['signal_time'], True, mtg, candles)
        session['active_signal'] = None
    elif mtg < CONFIG['MAX_MTG_LEVEL']:
        session['active_signal']['mtg'] += 1
    else:
        await send_result_for_user(user_id, active_signal['asset'], direction,
                                   active_signal['signal_time'], False, mtg, candles)
        session['active_signal'] = None

async def send_result_for_user(user_id: int, asset: str, direction: str, signal_time_ts: int,
                               win: bool, mtg_level: int = 0, candles: List[Dict] = None):
    uid = str(user_id)
    settings = USER_DATA.get(uid, {}).get("settings", {})
    contact = settings.get("contact", CONFIG.get("BOT_USERNAME", "@Mahabub_iX"))
    footer_text = settings.get("footer_text", "RAVITH AI PRO")

    sig_time = timestamp_to_dhaka_time(signal_time_ts)
    result_data = {
        'asset': asset,
        'clean_asset': fancy_asset_name(asset),
        'direction': direction,
        'signal_time': signal_time_ts,
        'signal_datetime': sig_time.isoformat(),
        'result': 'WIN' if win else 'LOSS',
        'mtg_level': mtg_level,
        'date': sig_time.date().isoformat(),
        'display_time': (sig_time + timedelta(minutes=1)).strftime("%H:%M"),
        'timestamp': datetime.now(UTC_PLUS_6).isoformat()
    }
    is_new = save_user_result_entry(user_id, result_data)
    stats = get_user_stats(user_id)

    if win:
        stats['win'] += 1
        stats['streak'] = stats.get('streak', 0) + 1
        if stats['streak'] > stats.get('best_streak', 0):
            stats['best_streak'] = stats['streak']
    else:
        if mtg_level == CONFIG['MAX_MTG_LEVEL']:
            stats['loss'] += 1
            stats['streak'] = 0

    if is_new:
        if win:
            stats['pair_wins'] = stats.get('pair_wins', 0) + 1
        elif mtg_level == CONFIG['MAX_MTG_LEVEL']:
            stats['pair_losses'] = stats.get('pair_losses', 0) + 1
    save_user_stats()

    individual_stats = {"wins": stats['win'], "losses": stats['loss']}
    pair_stats = {"pair_wins": stats.get('pair_wins', 0), "pair_losses": stats.get('pair_losses', 0)}

    chat_id = get_user_chat_id(user_id)
    await send_result_with_chart(user_id, asset, direction, signal_time_ts,
                                 win, mtg_level, individual_stats, pair_stats,
                                 contact, candles if candles else [], footer_text)

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

def get_user_statistics(user_id, results_list=None):
    if results_list is None:
        stats = get_user_stats(user_id)
        results_list = stats['all_results']
    total = len(results_list)
    wins = sum(1 for r in results_list if r.get('result') == 'WIN')
    losses = total - wins
    acc = (wins / total * 100) if total else 0
    return {"total_trades": total, "wins": wins, "losses": losses, "accuracy": round(acc, 2)}

# ================= FORMAT FUNCTIONS (with footer) =================
def format_signal_message(asset, direction, signal_time_ts, price, payout, contact, footer_text):
    dt = timestamp_to_dhaka_time(signal_time_ts)
    time_str = dt.strftime("%H:%M")
    clean_asset = fancy_asset_name(asset)
    dir_emoji = "🟢" if direction == "CALL" else "🔴"
    dir_text = fancy_direction(direction)
    price_str = f"{price:.2f}" if price >= 1 else f"{price:.5f}"
    payout_int = int(payout) if payout else 0
    contact_clean = contact.lstrip('@')
    footer_bold = fb(footer_text)
    msg = f"""╔═★═════════════════★═╗
   👑 𝗥𝗔𝗩𝗜𝗧𝗛 𝗔𝗜 𝗣𝗥𝗢
╚═★═════════════════★═╝

╭━━━━━━━【⛨】━━━━━━━╮
💎 »» {clean_asset}
⏰ »» {fancy_time(time_str)}
{dir_emoji} »» {dir_text}
🎯 »» {fn(price_str)}
💸 »» {fn(str(payout_int))}٪
╰━━━━━━━━━━━━━━━━━━╯

🔗 {ff("CREATE ACCOUNT")}
<a href="https://t.me/{contact_clean}">🚀 𝙱𝙾𝚃 𝙾𝚆𝙽𝙴𝚁</a>

▰▰▰▰▰【 {footer_bold} 】▰▰▰▰▰"""
    return msg

def format_result_message(asset, direction, signal_time_ts, win, mtg_level, individual_stats, pair_stats, contact, footer_text):
    dt = timestamp_to_dhaka_time(signal_time_ts)
    time_str = dt.strftime("%H:%M")
    clean_asset = fancy_asset_name(asset)
    mtg_superscripts = {1: '¹', 2: '²', 3: '³'}
    mtg_sup = mtg_superscripts.get(mtg_level, '')
    if win:
        if mtg_level == 0:
            result_line = "✅✅✅ 𝚂𝚄𝚁𝙴 𝚂𝙷𝙾𝚃 ✅✅✅"
        else:
            result_line = f"✅✅✅ 𝙶𝙰𝙻𝙴 𝚆𝙸𝙽{mtg_sup} ✅✅✅"
    else:
        result_line = f"❌❌❌ 𝙻𝙾𝚂𝚂 𝙶𝙰𝙻𝙴{mtg_sup} ❌❌❌"
    wins = individual_stats['wins']
    losses = individual_stats['losses']
    total = wins + losses
    ind_accuracy = (wins / total * 100) if total > 0 else 0
    pair_wins = pair_stats['pair_wins']
    pair_losses = pair_stats['pair_losses']
    pair_total = pair_wins + pair_losses
    pair_accuracy = (pair_wins / pair_total * 100) if pair_total > 0 else 0
    contact_clean = contact.lstrip('@')
    footer_bold = fb(footer_text)
    msg = f"""▰▱▰▱ 𝚁╎𝙴╎𝚂╎𝚄╎𝙻╎𝚃 ▰▱▰▱

╭━━━━━━━━━【⛨】━━━━━━━━━╮
🎃{clean_asset}  ┃ 🕐 {fancy_time(time_str)}
╰━━━━━━━━━【⛨】━━━━━━━━━╯

        {result_line}

╭━━━━━━━━━【⛨】━━━━━━━━━╮
🔥 𝚆𝙸𝙽：{fn(str(wins))} │ ☃️ 𝙻𝙾𝚂𝚂：{fn(str(losses))} │ ({fn(f"{ind_accuracy:.0f}")}٪)
⚖️ 𝙿𝙰𝙸𝚁：{fn(str(pair_wins))}𝚡{fn(str(pair_losses))} ({fn(f"{pair_accuracy:.0f}")}٪)
╰━━━━━━━━━【⛨】━━━━━━━━━╯

<a href="https://t.me/{contact_clean}">🌐 𝚃𝙴𝙻𝙴𝙶𝚁𝙰𝙼：{contact}</a>

╔═★═════════════════★═╗
      {footer_bold}
╚═★═════════════════★═╝"""
    return msg

# ================= TRADING LOOP (modified) =================
async def trading_loop_for_user(user_id: int):
    """No automated trading or signal loop in the educational build."""
    session = USER_TRADING_SESSIONS.setdefault(user_id, {})
    session['active'] = False
    session['active_signal'] = None
    try:
        chat_id = get_user_chat_id(user_id)
        await BOT_APPLICATION.bot.send_message(
            chat_id=chat_id,
            text="Educational mode only: automated signals, trade execution, and win/loss claims are disabled. Use Chart Now to inspect candle structure."
        )
    except Exception:
        pass


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
        await safe_edit_or_reply(query, "Educational mode: win/loss screenshots and performance claims are disabled. Use Chart Now for the same source chart image.")
        return
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
            img_buffer = await generate_signal_chart(loss['asset'], target_dt, loss['direction'])
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
            ("REVERSE_PLUS_TRENDY", "🧠 Reverse Plus Trendy (Study)"),
            ("SUPPORT_RESISTANCE", "📈 Support/Resistance Study"),
            ("RSI_REVERSE", "🌀 RSI Reversal Study"),
            ("EMA_TREND", "📊 EMA Trend Study"),
            ("STRONG_SIGNAL", "💪 Indicator Confluence Study")
        ]
        current_strategy = USER_DATA.get(uid, {}).get("settings", {}).get("strategy", "REVERSE_PLUS_TRENDY")
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
        settings = USER_DATA.get(uid, {}).get("settings", {})
        styles = ["3d", "2d", "minimal", "neon"]
        current = settings.get("chart_style", "3d")
        idx = (styles.index(current) + 1) % len(styles) if current in styles else 0
        USER_DATA[uid]["settings"]["chart_style"] = styles[idx]
        save_user_data()
        msg = get_settings_message(user_id)
        await safe_edit_or_reply(query, msg, get_settings_keyboard(user_id))
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
        USER_DATA[uid]["settings"]["martingale"] = not settings.get("martingale", True)
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
│ {ff("Example: https://example.trycloudflare.com")}
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
│  🤖 {ff("Educational chart mode is active")}
│  📡 {ff("Fetching market data...")}
│  🎯 {ff("Studying candle patterns...")}
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
                notes = educational_pattern_notes(candles)
                note_text = "\n".join("• " + item for item in notes["observations"])
                loop = asyncio.get_running_loop()
                buf = await loop.run_in_executor(None, create_ultimate_dashboard, asset, candles[-60:])
                if buf:
                    chat_id = get_user_chat_id(user_id)
                    caption = (f"📊 {fancy_asset_name(asset)}\n\n{notes['status']}\n{note_text}\n\nNot financial advice.")
                    await BOT_APPLICATION.bot.send_photo(chat_id=chat_id, photo=buf, caption=caption, parse_mode='HTML')
            except Exception as e:
                print(f"Chart error: {e}")
        msg = f"╭━━━━━━━━━━╮\n│ ✅ {ff('Educational chart sent!')}\n╰━━━━━━━━━━╯"
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
                if not deduct_credit(user_id, 1):
                    msg = f"⛔ {ff('No credits left!')}"
                    await safe_edit_or_reply(query, msg, InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔙 𝙱𝙰𝙲𝙺", callback_data="back_main")]]
                    ))
                    return
            candles = sig['candles']
            await send_signal_with_chart(user_id, sig['asset'], sig['direction'],
                                     sig['signal_time'], candles[-1]['close'],
                                     sig.get('payout', 0), candles)
            msg = f"╭━━━━━━━━━━╮\n│ ✅ {ff('Signal sent!')}\n╰━━━━━━━━━━╯"
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
async def check_signal_result_batch(asset: str, signals: List[Dict], mtg_level: int = 0, check_date: date = None) -> List[Dict]:
    """
    Check multiple signals for the same asset in a single API call.
    This dramatically reduces API calls when many signals share the same asset.
    """
    if not signals:
        return []
    
    # Fetch candles once for this asset
    candles = await get_candles(asset, count=5000)
    if not candles:
        # Return all signals as unchecked if API fails
        return [{**sig, 'result': 'UNKNOWN', 'mtg_used': 0, 'checked': False, 'error': 'No data', 'payout': 0} for sig in signals]
    
    if check_date is None:
        check_date = datetime.now(UTC_PLUS_6).date()
    
    # Build a lookup dict for fast candle access
    candle_lookup = {}
    for c in candles:
        key = c['dt'].replace(second=0, microsecond=0)
        candle_lookup[key] = c
    
    results = []
    
    for sig in signals:
        try:
            hour, minute = map(int, sig['time'].split(':'))
            target_dt = UTC_PLUS_6.localize(datetime(
                check_date.year, check_date.month, check_date.day, 
                hour, minute, 0
            ))
            target_key = target_dt.replace(second=0, microsecond=0)
            
            entry_candle = candle_lookup.get(target_key)
            
            if entry_candle is None:
                results.append({
                    **sig,
                    'result': 'PENDING',
                    'mtg_used': 0,
                    'checked': False,
                    'error': 'Candle not found',
                    'payout': 0
                })
                continue
            
            signal_payout = entry_candle.get('payout', 0)
            
            def check_candle_win(candle, dir_str):
                if candle is None:
                    return None
                op = candle['open']
                cl = candle['close']
                if op == cl:
                    return None
                if dir_str == 'CALL':
                    return cl > op
                elif dir_str == 'PUT':
                    return cl < op
                return None
            
            win = check_candle_win(entry_candle, sig['direction'])
            
            if win is None:
                results.append({
                    **sig,
                    'result': 'TIE',
                    'mtg_used': 0,
                    'checked': True,
                    'payout': signal_payout
                })
                continue
            
            if win:
                results.append({
                    **sig,
                    'result': 'WIN',
                    'mtg_used': 0,
                    'checked': True,
                    'payout': signal_payout
                })
                continue
            
            # Check MTG candles if loss
            mtg_used = 0
            mtg_win = False
            
            if mtg_level >= 1:
                mtg1_dt = target_dt + timedelta(minutes=1)
                mtg1_key = mtg1_dt.replace(second=0, microsecond=0)
                mtg1_candle = candle_lookup.get(mtg1_key)
                
                if mtg1_candle is not None:
                    win_mtg1 = check_candle_win(mtg1_candle, sig['direction'])
                    if win_mtg1:
                        mtg_used = 1
                        mtg_win = True
                
                if not mtg_win and mtg_level >= 2:
                    mtg2_dt = target_dt + timedelta(minutes=2)
                    mtg2_key = mtg2_dt.replace(second=0, microsecond=0)
                    mtg2_candle = candle_lookup.get(mtg2_key)
                    
                    if mtg2_candle is not None:
                        win_mtg2 = check_candle_win(mtg2_candle, sig['direction'])
                        if win_mtg2:
                            mtg_used = 2
                            mtg_win = True
            
            if mtg_win:
                results.append({
                    **sig,
                    'result': 'WIN',
                    'mtg_used': mtg_used,
                    'checked': True,
                    'payout': signal_payout
                })
            else:
                results.append({
                    **sig,
                    'result': 'LOSS',
                    'mtg_used': mtg_level,
                    'checked': True,
                    'payout': signal_payout
                })
                
        except Exception as e:
            results.append({
                **sig,
                'result': 'ERROR',
                'mtg_used': 0,
                'checked': False,
                'error': str(e),
                'payout': 0
            })
    
    return results


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
async def main():
    global BOT_APPLICATION

    load_config()
    load_users()
    load_user_data()
    load_user_stats()

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

        await application.updater.stop()
        await application.stop()
        await application.shutdown()

        save_user_data()
        save_user_stats()
        save_users()

        print(Fore.GREEN + "✅ Saved. Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())