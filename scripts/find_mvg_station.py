#!/usr/bin/env python3
"""
MVG Station ID Finder
Sucht nach MVG Haltestellen und zeigt ihre IDs an.
"""

import requests
import sys


def search_station(query):
    """Sucht nach MVG Haltestellen."""
    url = f"https://www.mvg.de/api/fib/v2/stations?query={query}"
    headers = {
        'User-Agent': 'InkyPi/1.0'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        stations = response.json()
        
        if not stations:
            print(f"❌ Keine Haltestelle gefunden für: '{query}'")
            return
        
        print(f"\n✅ Gefundene Haltestellen für '{query}':\n")
        print("-" * 80)
        
        for i, station in enumerate(stations[:10], 1):
            station_id = station.get('id', 'N/A')
            name = station.get('name', 'Unbekannt')
            lat = station.get('latitude', 'N/A')
            lon = station.get('longitude', 'N/A')
            
            print(f"{i}. {name}")
            print(f"   ID: {station_id}")
            print(f"   Koordinaten: {lat}, {lon}")
            print()
        
        print("-" * 80)
        print(f"\n💡 Tipp: Kopiere die ID (z.B. {stations[0].get('id')}) für die InkyPi Konfiguration\n")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Fehler beim Abrufen der Daten: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")
        sys.exit(1)


def main():
    """Hauptfunktion."""
    print("=" * 80)
    print("MVG Haltestellen-ID Finder")
    print("=" * 80)
    
    if len(sys.argv) > 1:
        # Station aus Kommandozeile
        query = " ".join(sys.argv[1:])
    else:
        # Interaktive Eingabe
        query = input("\nGib den Namen der Haltestelle ein: ").strip()
    
    if not query:
        print("❌ Bitte gib einen Haltestellennamen ein!")
        sys.exit(1)
    
    search_station(query)


if __name__ == "__main__":
    main()
