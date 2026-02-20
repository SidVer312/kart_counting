import streamlit as st
import httpx
import pandas as pd
import time
import re
from collections import deque

# --- CONFIG & STYLING ---
st.set_page_config(page_title="SWS Kart Strategy", layout="wide", page_icon="🏎️")

st.markdown("""
    <style>
    .rocket-card { border: 2px solid #28a745; padding: 15px; border-radius: 10px; background-color: #f0fff4; margin-bottom: 10px; }
    .lemon-card { border: 2px solid #dc3545; padding: 15px; border-radius: 10px; background-color: #fff5f5; margin-bottom: 10px; }
    .neutral-card { border: 2px solid #6c757d; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- INITIALIZE STATE ---
if 'pit_queue' not in st.session_state:
    st.session_state.pit_queue = deque(maxlen=12)
if 'baselines' not in st.session_state:
    st.session_state.baselines = {} # { "Driver": [last_10_laps] }
if 'active_stints' not in st.session_state:
    st.session_state.active_stints = {} # { "Plate": {"driver": str, "laps": []} }

# --- CORE FUNCTIONS ---
def parse_speedhive_url(url):
    """Extracts Token and SessionID specifically for the direct API feed."""
    try:
        token_match = re.search(r'livetiming/([A-Z0-9]+)', url)
        # Session ID is often at the end of the first dash-segment or the URL
        session_match = re.search(r'-([0-9]+)', url)
        token = token_match.group(1) if token_match else None
        session_id = session_match.group(1) if session_match else None
        return token, session_id
    except: return None, None

def fetch_stealth_data(token, session_id):
    """Bypasses 'char 0' errors using HTTP/2 and modern headers."""
    url = f"https://speedhive.mylaps.com/LiveTiming/GetData/{token}?sessionId={session_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://speedhive.mylaps.com/"
    }
    try:
        # HTTP/2 is essential for 2026 Speedhive security
        with httpx.Client(http2=True, headers=headers, timeout=10) as client:
            response = client.get(url)
            return response.json() if response.status_code == 200 else None
    except: return None

def to_seconds(t_str):
    try:
        t_str = str(t_str).replace("'", "").strip()
        if not t_str or t_str == "0": return 0.0
        if ':' in t_str:
            m, s = t_str.split(':')
            return int(m) * 60 + float(s)
        return float(t_str)
    except: return 0.0

# --- MAIN UI ---
st.title("🏆 SWS Kart Intelligence Engine")
url_input = st.sidebar.text_input("Paste Speedhive URL", 
    value="https://speedhive.mylaps.com/livetiming/CDLPNDLQ-2147483741/active")

token, sess_id = parse_speedhive_url(url_input)

if token and sess_id:
    data = fetch_stealth_data(token, sess_id)
    
    if data and 'Rows' in data:
        # --- PROCESSING LOGIC ---
        for row in data['Rows']:
            name = row.get('DriverName') or row.get('Name') or "N/A"
            plate = str(row.get('Number', '0'))
            last_lap = to_seconds(row.get('LastLapTime'))
            is_pit = row.get('IsInPit', False) or row.get('Status') == "PIT"

            # 1. Update Driver Baseline Pace
            if not is_pit and last_lap > 25:
                if name not in st.session_state.baselines:
                    st.session_state.baselines[name] = deque(maxlen=10)
                st.session_state.baselines[name].append(last_lap)

                # Track current kart stint
                if plate not in st.session_state.active_stints:
                    st.session_state.active_stints[plate] = {'driver': name, 'laps': []}
                st.session_state.active_stints[plate]['laps'].append(last_lap)

            # 2. Pit Entry Logic: Identify Rocket vs Lemon
            elif is_pit and plate in st.session_state.active_stints:
                stint = st.session_state.active_stints.pop(plate)
                if name in st.session_state.baselines and len(stint['laps']) > 2:
                    avg_base = sum(st.session_state.baselines[name]) / len(st.session_state.baselines[name])
                    avg_stint = sum(stint['laps']) / len(stint['laps'])
                    score = avg_stint - avg_base # Negative is faster (Rocket)
                    
                    # Prevent duplicates in queue
                    if not any(q['plate'] == plate for q in st.session_state.pit_queue):
                        st.session_state.pit_queue.append({
                            'score': score, 
                            'driver': name, 
                            'plate': plate,
                            'time': time.strftime("%H:%M")
                        })

        # --- DASHBOARD ---
        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("🏁 Kart Queue (In Pits)")
            if not st.session_state.pit_queue:
                st.info("Pit lane empty. Waiting for karts to box...")
            else:
                for i, k in enumerate(list(st.session_state.pit_queue)):
                    score = k['score']
                    if score < -0.2:
                        css, label = "rocket-card", "🚀 ROCKET"
                    elif score > 0.15:
                        css, label = "lemon-card", "🍋 LEMON"
                    else:
                        css, label = "neutral-card", "⚖️ NEUTRAL"

                    st.markdown(f"""<div class="{css}"><strong>#{k['plate']} - {label}</strong><br>
                                 Rel. Pace: {score:+.3f}s<br><small>Last Pilot: {k['driver']} ({k['time']})</small></div>""", 
                                 unsafe_allow_html=True)

        with col2:
            st.subheader("📊 Strategy & Live Feed")
            if st.session_state.pit_queue:
                head_score = st.session_state.pit_queue[0]['score']
                if head_score < -0.1:
                    st.success(f"### ✅ BOX NOW!\nKart #{st.session_state.pit_queue[0]['plate']} is a confirmed ROCKET.")
                else:
                    st.warning("### ❌ STAY OUT\nThe next kart in the queue is slow.")
            
            st.divider()
            df = pd.DataFrame(data['Rows'])
            if not df.empty:
                st.dataframe(df[['Position', 'Number', 'DriverName', 'LastLapTime', 'Laps']], 
                             use_container_width=True, hide_index=True)

    else:
        st.error("📡 Connection Blocked. Trying Stealth Reconnect...")
else:
    st.info("Awaiting valid Speedhive URL...")

if st.sidebar.toggle("Auto-Refresh (5s)", value=True):
    time.sleep(5)
    st.rerun()