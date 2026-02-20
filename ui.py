import streamlit as st
import pandas as pd
import time
from seleniumbase import SB

st.set_page_config(page_title="SWS Strategy Engine", layout="wide")

# --- ENGINE: FETCH DATA WITHOUT HEADERS ---
def get_live_data(url):
    """Uses SeleniumBase UC Mode to bypass Speedhive security automatically."""
    try:
        # 'uc=True' is the magic switch that makes the browser look human
        with SB(uc=True, headless=True) as sb:
            sb.open(url)
            # We wait for the table to actually load its data
            sb.wait_for_element("table", timeout=10)
            
            # Scrape the table data directly from the rendered page
            table_data = sb.get_text_list("td")
            headers = sb.get_text_list("th")
            
            # SeleniumBase can also pull the underlying API response 
            # if the table scraping is too messy
            return sb.get_beautiful_soup()
    except Exception as e:
        return f"Error: {e}"

# --- MAIN UI ---
st.title("🏆 SWS Race Strategy Engine")
st.write("This engine uses **Undetected Driver** mode to bypass Speedhive security.")

url_input = st.sidebar.text_input("Paste Speedhive Session URL")

if url_input:
    with st.spinner("Bypassing Speedhive security..."):
        soup = get_live_data(url_input)
        
        if hasattr(soup, 'find_all'): # If we got a valid BeautifulSoup object
            rows = []
            table = soup.find('table')
            if table:
                for tr in table.find_all('tr')[1:]:
                    cols = [td.get_text(strip=True) for td in tr.find_all('td')]
                    if len(cols) >= 5:
                        rows.append({
                            'Pos': cols[0],
                            'Kart': cols[1],
                            'Driver': cols[2],
                            'Laps': cols[3],
                            'Last Lap': cols[4]
                        })
                
                if rows:
                    st.success(f"Connected! Tracking {len(rows)} Drivers.")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True)
                else:
                    st.warning("Connected, but the timing table is empty. Is the race running?")
            else:
                st.error("Could not find the timing table. Ensure the URL is correct.")
        else:
            st.error(f"Failed to bypass security: {soup}")

else:
    st.info("Paste the Speedhive URL to begin tracking. No cookies required.")

if st.sidebar.toggle("Auto-Refresh (10s)", value=True):
    time.sleep(10)
    st.rerun()