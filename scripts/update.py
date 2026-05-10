#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import requests
from datetime import datetime

# EmailJS konfiguráció (GitHub Secrets-ből jönnek)
EMAILJS_PUBLIC_KEY = os.environ.get('EMAILJS_PUBLIC_KEY', '')
EMAILJS_SERVICE_ID = os.environ.get('EMAILJS_SERVICE_ID', '')
EMAILJS_ADMIN_TEMPLATE_ID = os.environ.get('EMAILJS_ADMIN_TEMPLATE_ID', '')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'tamaskult2@icloud.com')

def send_admin_notification(changes_text):
    """Küld egy admin emailt EmailJS-en keresztül, ha van változás"""
    if not all([EMAILJS_PUBLIC_KEY, EMAILJS_SERVICE_ID, EMAILJS_ADMIN_TEMPLATE_ID]):
        print("⚠️ EmailJS konfiguráció hiányzik, email nem került kiküldésre")
        return False
    
    try:
        data = {
            "service_id": EMAILJS_SERVICE_ID,
            "template_id": EMAILJS_ADMIN_TEMPLATE_ID,
            "user_id": EMAILJS_PUBLIC_KEY,
            "template_params": {
                "admin_email": ADMIN_EMAIL,
                "changes": changes_text
            }
        }
        
        response = requests.post(
            "https://api.emailjs.com/api/v1.0/email/send",
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ Admin email elküldve: {ADMIN_EMAIL}")
            return True
        else:
            print(f"❌ Email küldési hiba: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Email küldési exception: {e}")
        return False

def load_data():
    """Betölti a meglévő data.json fájlt"""
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️ data.json nem található, üres lista indul")
        return []

def save_data(data):
    """Elmenti a data.json fájlt"""
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ data.json mentve ({len(data)} tégla)")

def update_index_html(data):
    """Frissíti az index.html fájlt az új adatokkal"""
    try:
        with open('index.template.html', 'r', encoding='utf-8') as f:
            template = f.read()
        
        # Adatok beillesztése
        html_content = template.replace(
            '__DATA_PLACEHOLDER__',
            json.dumps(data, ensure_ascii=False, indent=2)
        )
        
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print("✅ index.html frissítve")
        return True
    except Exception as e:
        print(f"❌ index.html frissítési hiba: {e}")
        return False

def compare_data(old_data, new_data):
    """Összehasonlítja a régi és új adatokat, visszaadja a változásokat"""
    changes = []
    
    # Dict-té alakítjuk ID alapján a gyorsabb kereséshez
    old_dict = {item['id']: item for item in old_data}
    new_dict = {item['id']: item for item in new_data}
    
    # Új téglák
    for brick_id, brick in new_dict.items():
        if brick_id not in old_dict:
            changes.append(f"🆕 Új tégla: {brick['title']}")
    
    # Státusz változások
    for brick_id, new_brick in new_dict.items():
        if brick_id in old_dict:
            old_brick = old_dict[brick_id]
            if old_brick['status'] != new_brick['status']:
                changes.append(
                    f"🔄 Státusz változás: {new_brick['title']} "
                    f"({old_brick['status']} → {new_brick['status']})"
                )
    
    # Törölt téglák
    for brick_id, brick in old_dict.items():
        if brick_id not in new_dict:
            changes.append(f"🗑️ Törölt tégla: {brick['title']}")
    
    return changes

def main():
    """Főprogram: frissítés és változás-ellenőrzés"""
    print("=" * 50)
    print("🧱 Tegláról-téglára automatikus frissítés")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Régi adatok betöltése
    old_data = load_data()
    print(f"📂 Régi adatok betöltve: {len(old_data)} tégla")
    
    # ÚJ ADATOK LEKÉRÉSE (jelenleg csak szimuláció)
    # TODO: Itt kell implementálni a valódi scraping logikát
    # Egyelőre csak a régi adatokat használjuk
    new_data = old_data.copy()
    
    # PÉLDA: Szimulált változás teszteléshez (kommenteld ki éles használatban)
    # if len(new_data) > 0:
    #     new_data[0]['status'] = 'Teljesítve'  # Első tégla státuszát megváltoztatjuk
    
    print(f"🔍 Új adatok lekérve: {len(new_data)} tégla")
    
    # Változások ellenőrzése
    changes = compare_data(old_data, new_data)
    
    if changes:
        print(f"\n🔔 {len(changes)} változás észlelve:")
        for change in changes:
            print(f"  • {change}")
        
        # Adatok mentése
        save_data(new_data)
        update_index_html(new_data)
        
        # Admin email küldése
        changes_text = f"{len(changes)} változás történt:\n\n" + "\n".join(changes)
        email_sent = send_admin_notification(changes_text)
        
        if email_sent:
            print("\n✅ Frissítés sikeres, admin értesítés elküldve!")
        else:
            print("\n⚠️ Frissítés sikeres, de admin email nem lett elküldve")
    else:
        print("\n✅ Nincs változás, frissítés nem szükséges")
    
    print("=" * 50)

if __name__ == "__main__":
    main()
