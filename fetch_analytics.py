#!/usr/bin/env python3
"""
Google Analytics látogatószám lekérés
Naponta fut GitHub Actions-ben, frissíti az analytics-stats.json fájlt
"""

import json
import os
from datetime import datetime, timedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)

# Google Analytics Property ID
PROPERTY_ID = "537246904"

def get_analytics_data():
    """Lekéri a látogatószámokat a Google Analytics API-ból"""
    
    # Service Account credentials from environment variable (GitHub Secrets)
    credentials_json = os.environ.get('GA_CREDENTIALS_JSON')
    if not credentials_json:
        print("❌ Hiba: GA_CREDENTIALS_JSON environment variable nincs beállítva")
        return None
    
    # Credentials fájl létrehozása
    with open('/tmp/credentials.json', 'w') as f:
        f.write(credentials_json)
    
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/tmp/credentials.json'
    
    try:
        client = BetaAnalyticsDataClient()
        
        # Lekérjük az összes látogatót (inception óta)
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            date_ranges=[DateRange(start_date="2020-01-01", end_date="today")],
            metrics=[
                Metric(name="activeUsers"),  # Aktív felhasználók
                Metric(name="sessions"),     # Összes session
            ],
        )
        
        response = client.run_report(request)
        
        if response.rows:
            row = response.rows[0]
            active_users = int(row.metric_values[0].value)
            total_sessions = int(row.metric_values[1].value)
            
            print(f"✅ Aktív felhasználók: {active_users:,}")
            print(f"✅ Összes session: {total_sessions:,}")
            
            return {
                "activeUsers": active_users,
                "totalSessions": total_sessions,
                "lastUpdated": datetime.now().isoformat()
            }
        else:
            print("⚠️ Nincs adat")
            return None
            
    except Exception as e:
        print(f"❌ Hiba az Analytics lekérésnél: {e}")
        return None

def main():
    print("🔍 Google Analytics adatok lekérése...")
    
    data = get_analytics_data()
    
    if data:
        # Mentés JSON fájlba (current working directory)
        output_file = 'analytics-stats.json'
        output_path = os.path.join(os.getcwd(), output_file)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Adatok mentve: {output_path}")
        print(f"📊 Statisztikák:")
        print(f"   - Aktív felhasználók: {data['activeUsers']:,}")
        print(f"   - Összes session: {data['totalSessions']:,}")
        print(f"   - Utoljára frissítve: {data['lastUpdated']}")
    else:
        print("❌ Nem sikerült lekérni az adatokat")

if __name__ == "__main__":
    main()
