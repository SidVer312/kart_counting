import streamlit as st
import httpx
import pandas as pd
import time
import re

st.set_page_config(page_title="SWS Strategy Engine", layout="wide")

def get_live_data(token, session_id):
    # This is the direct data endpoint the website uses internally
    url = f"https://speedhive.mylaps.com/LiveTiming/GetData/{token}?sessionId={session_id}"
    
    # These headers are the "secret sauce" to bypass the char 0 block
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://speedhive.mylaps.com/livetiming/{token}-{session_id}/active",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        # We use http2=True to match how modern browsers communicate
        with httpx.Client(http2=True, headers=headers, timeout=10) as client:
            response = client.get(url)
            
            if response.status_code == 200:
                # If the body is empty, we still get the char 0 error, so we check first
                if not response.text.strip():
                    return "Server sent an empty response (Bot block active)."
                return response.json()
            else:
                return f"Server denied access (Error {response.status_code})."
    except Exception as e:
        return f"Connection Failed: {e}"

# --- MAIN UI ---
st.title("🏆 Dubai SWS Kart Strategy Engine")

# Input for the full URL
url_input = st.sidebar.text_input(
    "Paste Speedhive Session URL", 
    value="https://speedhive.mylaps.com/livetiming/B3E58F71A3C54200-2147486187/active"
)

# Extract Token and Session
try:
    token_match = re.search(r'livetiming/([A-Z0-9]+)-([0-9]+)', url_input)
    token = token_match.group(1)
    sess_id = token_match.group(2)
    
    if st.sidebar.button("Force Manual Refresh"):
        st.rerun()

    data = get_live_data(token, sess_id)

    if isinstance(data, dict) and 'Rows' in data:
        st.success(f"✅ Live Data Active for {token}")
        df = pd.DataFrame(data['Rows'])
        
        # Displaying the most critical race data
        cols = ['Position', 'Number', 'DriverName', 'LastLapTime', 'BestLapTime', 'Laps']
        available = [c for c in cols if c in df.columns]
        st.dataframe(df[available].sort_values('Position'), use_container_width=True, hide_index=True)
    else:
        st.error(f"📡 Connection Issue: {data}")
        st.info("Try refreshing the Speedhive page in your browser, then copy the URL again.")

except Exception:
    st.info("Please paste a valid Speedhive Live Timing URL in the sidebar.")

# Auto-Refresh (Every 5 seconds for live racing)
if st.sidebar.toggle("Auto-Refresh Feed", value=True):
    time.sleep(5)
    st.rerun()