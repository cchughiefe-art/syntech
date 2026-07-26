#!/usr/bin/env python3
"""
SYNTECH Validator Signup Automation v3
- IP rotation via proxy list
- User-Agent rotation
- Rate-limit backoff & retry
- Credentials saved to Google Drive (mounted at /content/drive/MyDrive/)
====================================================================
AUTHORIZED PENETRATION TESTING TOOL — DO NOT USE WITHOUT PERMISSION
====================================================================
"""

import requests
import re
import json
import time
import os
import random
import threading
from datetime import datetime
from pathlib import Path

# ======================== CONFIGURATION ============================

TARGET_URL = "https://syntech.network/secure/K5A4W3F8"
REGISTER_URL = "https://syntech.network/accounts/register/"
BASE_URL = "https://syntech.network"

# Google Drive mount path (adjust if your mount differs)
GOOGLE_DRIVE_DIR = "/content/drive/MyDrive/HackerAI"
CREDENTIALS_FILE = os.path.join(GOOGLE_DRIVE_DIR, "syntech_validators.json")
TXT_LOG_DIR = os.path.join(GOOGLE_DRIVE_DIR, "signup_logs")

# How many accounts to create total (set to 0 for unlimited)
TARGET_COUNT = 25

# Delay between accounts (seconds) — minimum even with proxies
MIN_DELAY = 3
MAX_DELAY = 8

# ==================== USER AGENT ROTATION ==========================

USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Firefox macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Opera
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/111.0.0.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

# =================== ACCEPT-LANGUAGE ROTATION =======================

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-CA,en;q=0.9",
    "en-AU,en;q=0.9",
    "en-US,en;q=0.8",
    "en;q=0.9",
]

# ==================== PROXY CONFIGURATION ===========================
#
# HOW TO SET UP PROXIES (IP ROTATION):
#
# Option A — File-based proxy list:
#   1. Create /tmp/proxies.txt with one proxy per line:
#        http://user:pass@1.2.3.4:8080
#        socks5://user:pass@5.6.7.8:1080
#        http://3.4.5.6:3128
#   2. Set PROXY_FILE = "/tmp/proxies.txt" below
#   3. Each signup picks a random proxy from the list
#
# Option B — Residential proxy service (BrightData, Oxylabs, etc.):
#   1. Set PROXY_SERVICE_URL to your provider's super proxy
#      e.g. "http://customer-xxx-cc-US-session-auto-sessId:pass@zproxy.lum-superproxy.io:22225"
#   2. Set USE_PROXY_SERVICE = True
#   3. Each request can get a different residential IP automatically
#
# Option C — Tor (requires tor installed):
#   sudo apt install tor
#   Set USE_TOR = True
#   Uses 127.0.0.1:9050 (SOCKS5)
#
# Option D — No proxy (direct connection):
#   Set USE_PROXY_SERVICE = False and PROXY_FILE = ""

USE_PROXY_SERVICE = False
PROXY_SERVICE_URL = ""  # e.g. "http://customer-xxx-session-auto:pass@pr.superproxy.io:22225"

PROXY_FILE = ""  # e.g. "/tmp/proxies.txt"

USE_TOR = True
TOR_PROXY = "socks5h://127.0.0.1:9050"

# ================================================================


def load_proxies():
    """Load proxies from file. Returns list of proxy strings."""
    if PROXY_FILE and os.path.exists(PROXY_FILE):
        with open(PROXY_FILE) as f:
            proxies = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        print(f"[+] Loaded {len(proxies)} proxies from {PROXY_FILE}")
        return proxies
    return []


def get_random_headers():
    """Return randomized browser headers for a signup request."""
    ua = random.choice(USER_AGENTS)
    lang = random.choice(ACCEPT_LANGUAGES)

    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": lang,
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
    }

    # ~50% chance of adding a few extra headers for realism
    if random.random() > 0.5:
        headers["Sec-CH-UA"] = f'"Chromium";v="126", "Google Chrome";v="126"'
        headers["Sec-CH-UA-Mobile"] = "?0"
        headers["Sec-CH-UA-Platform"] = random.choice(['"Windows"', '"macOS"', '"Linux"'])

    return headers


def get_random_proxy(proxies, used_proxies, lock):
    """
    Pick a random proxy from the list, avoiding recently used ones.
    Returns None if no proxies are configured (direct connection).
    """
    if USE_PROXY_SERVICE and PROXY_SERVICE_URL:
        return {"http": PROXY_SERVICE_URL, "https": PROXY_SERVICE_URL}

    if USE_TOR:
        return {"http": TOR_PROXY, "https": TOR_PROXY}

    if not proxies:
        return None

    with lock:
        # Try to pick a proxy not recently used
        available = [p for p in proxies if p not in used_proxies]
        if not available:
            used_proxies.clear()
            available = proxies

        proxy = random.choice(available)
        used_proxies.add(proxy)

    return {"http": proxy, "https": proxy}


def extract_credentials(html):
    """Extract login/password/recovery-phrase from the credentials page HTML."""
    login_m = re.search(r'<code id="c-login">([^<]+)</code>', html)
    pass_m = re.search(r'<code id="c-pass">([^<]+)</code>', html)
    phrase_m = re.search(r'<code id="c-phrase"[^>]*>([^<]+)</code>', html)

    return {
        "login": login_m.group(1) if login_m else None,
        "password": pass_m.group(1) if pass_m else None,
        "recovery_phrase": phrase_m.group(1) if phrase_m else None,
    }


def signup(proxies, used_proxies, lock):
    """
    Perform one complete signup flow.
    Returns (credentials_dict, error_string) on failure.
    """
    session = requests.Session()
    session.headers.update(get_random_headers())

    # Apply proxy
    proxy = get_random_proxy(proxies, used_proxies, lock)
    if proxy:
        session.proxies.update(proxy)

    # ---------- Step 1: GET the registration page ----------
    try:
        r = session.get(TARGET_URL, timeout=30)
    except requests.exceptions.ProxyError as e:
        return None, f"PROXY_ERROR: {e}"
    except requests.exceptions.Timeout:
        return None, "TIMEOUT"
    except requests.exceptions.RequestException as e:
        return None, f"REQUEST_ERROR: {e}"

    if r.status_code != 200:
        return None, f"GET {r.status_code}"

    html = r.text

    # Extract hidden form fields
    csrf_m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    token_m = re.search(r'name="form_token" value="([^"]+)"', html)

    if not csrf_m or not token_m:
        return None, "MISSING_FORM_TOKENS"

    csrf_token = csrf_m.group(1)
    form_token = token_m.group(1)

    # ---------- Step 2: POST the registration form ----------
    form_data = {
        "csrfmiddlewaretoken": csrf_token,
        "ref": "",
        "form_token": form_token,
        "fp": "",
        "company_website": "",  # honeypot field — must be empty
    }

    post_headers = {
        "X-Requested-With": "fetch",
        "Referer": TARGET_URL,
        "Origin": BASE_URL,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    try:
        r2 = session.post(
            REGISTER_URL,
            data=form_data,
            headers=post_headers,
            timeout=30,
        )
    except requests.exceptions.RequestException as e:
        return None, f"POST_ERROR: {e}"

    # Handle rate limiting
    if r2.status_code == 429:
        return None, "RATE_LIMITED"

    if r2.status_code != 200:
        return None, f"POST {r2.status_code}: {r2.text[:200]}"

    try:
        data = r2.json()
    except json.JSONDecodeError:
        return None, f"NON_JSON_RESPONSE: {r2.text[:300]}"

    if not data.get("ok"):
        return None, f"REG_FAIL: {data.get('message', 'unknown')}"

    # ---------- Step 3: Fetch the credentials page ----------
    creds_url = BASE_URL + data["redirect"]
    try:
        r3 = session.get(creds_url, timeout=30)
    except requests.exceptions.RequestException as e:
        return None, f"CREDS_FETCH_ERROR: {e}"

    if r3.status_code != 200:
        return None, f"CREDS_PAGE {r3.status_code}"

    creds = extract_credentials(r3.text)

    if not creds["login"] or not creds["password"] or not creds["recovery_phrase"]:
        return None, f"CREDS_EXTRACT_FAIL: {creds}"

    return creds, None


def load_existing():
    """Load previously saved credentials from the JSON file."""
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_credentials(all_creds):
    """Save all credentials to Google Drive (JSON + timestamped TXT)."""
    os.makedirs(GOOGLE_DRIVE_DIR, exist_ok=True)
    os.makedirs(TXT_LOG_DIR, exist_ok=True)

    # JSON (always overwrite — canonical source)
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(all_creds, f, indent=2)

    # TXT log (timestamped, append-only for record keeping)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_path = os.path.join(TXT_LOG_DIR, f"syntech_validators_{ts}.txt")
    with open(txt_path, "w") as f:
        f.write(f"SYNTECH VALIDATORS - {len(all_creds)} accounts\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        for i, c in enumerate(all_creds, 1):
            f.write(f"Account #{i}\n")
            f.write(f"  Login:           {c['login']}\n")
            f.write(f"  Password:        {c['password']}\n")
            f.write(f"  Recovery Phrase: {c['recovery_phrase']}\n")
            f.write(f"  Created:         {c.get('created_at', 'N/A')}\n")
            f.write("\n")

    # Also save a latest.txt for quick access
    latest_txt = os.path.join(GOOGLE_DRIVE_DIR, "syntech_latest.txt")
    latest_creds = all_creds[-1] if all_creds else None
    if latest_creds:
        with open(latest_txt, "w") as f:
            f.write(f"SYNTECH LATEST ACCOUNT ({len(all_creds)} total)\n")
            f.write("=" * 40 + "\n")
            f.write(f"Login:           {latest_creds['login']}\n")
            f.write(f"Password:        {latest_creds['password']}\n")
            f.write(f"Recovery Phrase: {latest_creds['recovery_phrase']}\n")
            f.write(f"Created:         {latest_creds.get('created_at', 'N/A')}\n")

    return txt_path


def print_banner():
    banner = r"""
╔══════════════════════════════════════════════════════════╗
║  SYNTECH VALIDATOR SIGNUP AUTOMATION — v3               ║
║  IP rotation · UA rotation · Rate-limit backoff          ║
║  Target: syntech.network                                 ║
╚══════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_config(proxies):
    print(f"[i] Target:         {TARGET_URL}")
    print(f"[i] Drive path:     {GOOGLE_DRIVE_DIR}")
    print(f"[i] Target count:   {TARGET_COUNT}")
    print(f"[i] User agents:    {len(USER_AGENTS)}")
    print(f"[i] Proxies loaded: {len(proxies)}")
    print(f"[i] Using Tor:      {USE_TOR}")
    print(f"[i] Proxy service:  {PROXY_SERVICE_URL if USE_PROXY_SERVICE else 'No'}")
    print(f"[i] Delay range:    {MIN_DELAY}-{MAX_DELAY}s")
    print()


def main():
    print_banner()

    # Load proxies
    proxies = load_proxies()
    used_proxies = set()
    proxy_lock = threading.Lock()

    if not proxies and not USE_PROXY_SERVICE and not USE_TOR:
        print("[!] No proxies configured — using direct connection (no IP rotation).")
        print("[!] Set PROXY_FILE, USE_PROXY_SERVICE, or USE_TOR for IP rotation.\n")

    print_config(proxies)

    # Load existing credentials
    all_creds = load_existing()
    print(f"[i] Existing accounts on Drive: {len(all_creds)}\n")

    if TARGET_COUNT and len(all_creds) >= TARGET_COUNT:
        print(f"[✓] Target of {TARGET_COUNT} accounts already met. Exiting.")
        return

    consecutive_fails = 0
    attempt = 0
    stats = {"success": 0, "rate_limited": 0, "errors": 0}

    while True:
        # Check if we've hit the target
        if TARGET_COUNT and len(all_creds) >= TARGET_COUNT:
            break

        attempt += 1
        account_num = len(all_creds) + 1
        current_target = f"{account_num}/{TARGET_COUNT}" if TARGET_COUNT else account_num

        # Show which proxy is being used
        proxy_info = ""
        if USE_TOR:
            proxy_info = " [Tor]"
        elif USE_PROXY_SERVICE and PROXY_SERVICE_URL:
            proxy_info = " [ProxyService]"
        elif proxies:
            proxy_info = " [ProxyRotate]"

        print(f"[{attempt}] Creating #{current_target}{proxy_info}...", end=" ", flush=True)

        creds, error = signup(proxies, used_proxies, proxy_lock)

        if creds:
            creds["created_at"] = datetime.now().isoformat()
            all_creds.append(creds)
            consecutive_fails = 0
            stats["success"] += 1

            save_credentials(all_creds)
            ua_snippet = creds.get("login", "?")
            print(f"OK → Login: {creds['login']}  ({len(all_creds)} total)")

            # Delay before next signup
            if not (TARGET_COUNT and len(all_creds) >= TARGET_COUNT):
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                time.sleep(delay)

        elif error == "RATE_LIMITED":
            consecutive_fails += 1
            stats["rate_limited"] += 1
            backoff = min(10 * (2 ** (consecutive_fails - 1)), 180)
            print(f"RATE LIMITED — waiting {backoff}s")

            # Rotate IP on rate limit (mark current proxy as bad)
            if proxies:
                with proxy_lock:
                    used_proxies.clear()

            time.sleep(backoff)

        else:
            consecutive_fails += 1
            stats["errors"] += 1
            print(f"FAIL — {error}")
            time.sleep(3)

        # Hard reset if stuck
        if consecutive_fails >= 10:
            print(f"\n[!] 10 consecutive failures. Taking a 120s break...")
            time.sleep(120)
            consecutive_fails = 5

        # Save after every attempt
        save_credentials(all_creds)

    # Final report
    print()
    print("=" * 55)
    print("  COMPLETE — SYNTECH VALIDATOR ACCOUNTS")
    print("=" * 55)
    print(f"  Accounts created:  {len(all_creds)}")
    print(f"  Successful:        {stats['success']}")
    print(f"  Rate-limited:      {stats['rate_limited']}")
    print(f"  Errors:            {stats['errors']}")
    print(f"  Attempts:          {attempt}")
    print(f"  JSON:              {CREDENTIALS_FILE}")
    print(f"  Logs dir:          {TXT_LOG_DIR}/")
    print("=" * 55)


if __name__ == "__main__":
    main()

