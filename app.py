#!/usr/bin/env python3
# app.py - Login EasyHits4U con Browserless BQL + Supabase (solo chiavi working)

import requests
import json
import time
import os
from datetime import datetime

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ Supabase non installato")

# ==================== CONFIGURAZIONE ====================
EASYHITS_EMAIL = "sandrominori50+giorgiofaggiolini@gmail.com"
EASYHITS_PASSWORD = "DDnmVV45!!"
REFERER_URL = "https://www.easyhits4u.com/?ref=nicolacaporale"
BROWSERLESS_URL = "https://production-sfo.browserless.io/chrome/bql"

# Supabase (variabili d'ambiente su Render)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
# ========================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def get_working_keys_from_supabase():
    """Recupera solo le chiavi con status 'working'"""
    if not SUPABASE_AVAILABLE or not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        log("❌ Supabase non configurato")
        return []
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        response = supabase.table('browserless_keys')\
            .select('id', 'api_key')\
            .eq('status', 'working')\
            .execute()
        keys = [row['api_key'] for row in response.data]
        log(f"📦 Recuperate {len(keys)} chiavi 'working' da Supabase")
        return keys
    except Exception as e:
        log(f"❌ Errore Supabase: {e}")
        return []

def update_key_status(api_key, new_status):
    """Aggiorna lo status di una chiave su Supabase"""
    if not SUPABASE_AVAILABLE or not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        supabase.table('browserless_keys')\
            .update({'status': new_status})\
            .eq('api_key', api_key)\
            .execute()
        log(f"   📝 Chiave {api_key[:10]}... → '{new_status}'")
    except Exception as e:
        log(f"   ⚠️ Errore aggiornamento: {e}")

def get_cf_token(api_key):
    query = """
    mutation {
      goto(url: "https://www.easyhits4u.com/logon/", waitUntil: networkIdle, timeout: 60000) {
        status
      }
      solve(type: cloudflare, timeout: 60000) {
        solved
        token
        time
      }
    }
    """
    url = f"{BROWSERLESS_URL}?token={api_key}"
    try:
        start = time.time()
        response = requests.post(url, json={"query": query}, headers={"Content-Type": "application/json"}, timeout=120)
        if response.status_code != 200:
            return None
        data = response.json()
        if "errors" in data:
            return None
        solve_info = data.get("data", {}).get("solve", {})
        if solve_info.get("solved"):
            token = solve_info.get("token")
            log(f"   ✅ Token ({time.time()-start:.1f}s)")
            return token
        return None
    except Exception as e:
        log(f"   ❌ Errore token: {e}")
        return None

def login_with_token(token):
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/148.0',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': REFERER_URL,
    }
    data = {
        'manual': '1',
        'fb_id': '',
        'fb_token': '',
        'google_code': '',
        'username': EASYHITS_EMAIL,
        'password': EASYHITS_PASSWORD,
        'cf-turnstile-response': token,
    }
    session.get(REFERER_URL)
    response = session.post("https://www.easyhits4u.com/logon/", data=data, headers=headers, allow_redirects=True, timeout=30)
    final_cookies = session.cookies.get_dict()
    if 'user_id' in final_cookies:
        log(f"   ✅ Login OK! user_id: {final_cookies['user_id']}")
        return final_cookies
    return None

def main():
    log("=" * 50)
    log("🚀 LOGIN EASYHITS4U + SUPABASE (solo chiavi working)")
    log("=" * 50)
    
    keys = get_working_keys_from_supabase()
    if not keys:
        log("❌ Nessuna chiave 'working' disponibile")
        return
    
    for api_key in keys:
        log(f"🔑 Tentativo con chiave: {api_key[:10]}...")
        
        token = get_cf_token(api_key)
        if not token:
            log(f"   ❌ Token non ottenuto")
            update_key_status(api_key, 'broken')
            continue
        
        cookies = login_with_token(token)
        if cookies:
            log(f"🎉 Login OK! user_id={cookies.get('user_id')}, sesids={cookies.get('sesids')}")
            os.makedirs("/tmp/easyhits4u", exist_ok=True)
            with open("/tmp/easyhits4u/cookies.json", "w") as f:
                json.dump(cookies, f)
            log("💾 Cookie salvati")
            update_key_status(api_key, 'used')
            return
        else:
            log(f"   ❌ Login fallito")
            update_key_status(api_key, 'broken')
    
    log("❌ Nessuna chiave ha funzionato per il login.")

if __name__ == "__main__":
    main()