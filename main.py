import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from collections import deque

class DubaiKartCounter:
    def __init__(self, url):
        # Configuration
        self.url = url
        self.driver_histories = {}  # { 'Driver Name': [list of clean laps] }
        self.pit_lane_karts = deque() # Karts waiting in pits: [{'quality': float, 'in_time': float}]
        self.active_stints = {}     # { 'Plate_ID': {'driver': name, 'laps': []} }
        
        # Setup Selenium (Headless)
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        self.browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    def get_clean_average(self, laps):
        """Removes outliers (traffic/mistakes) and returns average pace."""
        if len(laps) < 3: return None
        sorted_laps = sorted(laps)
        # Trim top and bottom 20% to find 'True Pace'
        trim = max(1, int(len(sorted_laps) * 0.2))
        clean_set = sorted_laps[trim:-trim]
        return sum(clean_set) / len(clean_set)

    def scrape_speedhive(self):
        """Pulls the live timing table from Speedhive."""
        self.browser.get(self.url)
        time.sleep(3) # Wait for JS to load
        
        # Extract table rows
        try:
            # Note: Selectors may need adjustment based on specific Speedhive layout
            rows = self.browser.find_elements("xpath", "//tr[@class='live-timing-row']")
            data = []
            for row in rows:
                cols = row.find_elements("tag name", "td")
                # Expected: [Pos, Plate/No, Name, Last Lap, Best Lap, Gap, Status]
                data.append({
                    'plate': cols[1].text,
                    'name': cols[2].text,
                    'last_lap': self.parse_time(cols[3].text),
                    'status': cols[6].text # 'PIT' or 'Track'
                })
            return data
        except Exception as e:
            print(f"Scrape Error: {e}")
            return []

    def parse_time(self, time_str):
        """Converts MM:SS.ms or SS.ms to float seconds."""
        try:
            if ':' in time_str:
                m, s = time_str.split(':')
                return int(m) * 60 + float(s)
            return float(time_str)
        except: return 0.0

    def update_logic(self):
        raw_data = self.scrape_speedhive()
        
        for entry in raw_data:
            plate = entry['plate']
            name = entry['name']
            lap = entry['last_lap']
            status = entry['status']

            # 1. Initialize Driver History
            if name not in self.driver_histories:
                self.driver_histories[name] = []

            # 2. Handle Pit In (Kart enters the queue)
            if status == "PIT" and plate in self.active_stints:
                stint_laps = self.active_stints[plate]['laps']
                stint_avg = self.get_clean_average(stint_laps)
                driver_baseline = self.get_clean_average(self.driver_histories[name])
                
                if stint_avg and driver_baseline:
                    # Negative means kart is FASTER than driver's usual baseline
                    quality_score = stint_avg - driver_baseline
                    self.pit_lane_karts.append({'score': quality_score, 'time': time.time()})
                
                del self.active_stints[plate]

            # 3. Handle On-Track Laps
            elif status != "PIT" and lap > 20.0: # Ignore tiny glitch laps
                if plate not in self.active_stints:
                    self.active_stints[plate] = {'driver': name, 'laps': []}
                
                self.active_stints[plate]['laps'].append(lap)
                self.driver_histories[name].append(lap)

    def display_dashboard(self):
        print("\033[H\033[J") # Clear terminal
        print("--- DUBAI KARTDROME STRATEGY ENGINE ---")
        print(f"Karts in Pit: {len(self.pit_lane_karts)}")
        
        if self.pit_lane_karts:
            print("\nPIT QUEUE (First to Exit):")
            for i, kart in enumerate(self.pit_lane_karts):
                tag = "🚀 ROCKET" if kart['score'] < -0.2 else "🍋 LEMON" if kart['score'] > 0.2 else "⚖️ NEUTRAL"
                print(f"Pos {i+1}: Score {kart['score']:.3f} | {tag}")
            
            # Decision Logic
            best_score = self.pit_lane_karts[0]['score']
            if best_score < -0.15:
                print("\nSTRATEGY: >>> BOX NOW! TOP KART AVAILABLE <<<")
            else:
                print("\nSTRATEGY: STAY OUT. Wait for better kart rotation.")

# To run:
engine = DubaiKartCounter("https://speedhive.mylaps.com/LiveTiming/YOUR_EVENT_ID")
while True:
   engine.update_logic()
   engine.display_dashboard()
   time.sleep(5)