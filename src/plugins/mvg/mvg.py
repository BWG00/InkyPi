from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image
import requests
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# MVG API endpoints
MVG_API_URL = "https://www.mvg.de/api/fib/v2"
STATIONS_URL = f"{MVG_API_URL}/stations"
DEPARTURES_URL = f"{MVG_API_URL}/departures"


class MVG(BasePlugin):
    def generate_settings_template(self):
        """Generate settings template for MVG plugin."""
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        """Generate image with MVG departure information."""
        # Get settings
        station_id = settings.get('station_id')
        station_name = settings.get('station_name', 'MVG Live')
        limit = int(settings.get('departure_limit', 8))
        
        if not station_id:
            raise RuntimeError("Station ID is required. Please configure the MVG plugin.")
        
        timezone = device_config.get_config("timezone", default="Europe/Berlin")
        tz = pytz.timezone(timezone)
        
        try:
            # Fetch departures from MVG API
            departures = self.get_departures(station_id, limit)
            
            # Prepare data for template
            template_params = {
                'station_name': station_name,
                'departures': departures,
                'current_time': datetime.now(tz).strftime('%H:%M'),
                'device_config': device_config,
                'settings': settings
            }
            
            # Add style settings
            style_settings = self.get_style_settings(settings)
            template_params.update(style_settings)
            
            # Render image using base plugin
            dimensions = (device_config.get_resolution()[0], device_config.get_resolution()[1])
            img = self.render_image(dimensions, 'mvg.html', 'mvg.css', template_params)
            return img
            
        except Exception as e:
            logger.error(f"Error generating MVG image: {str(e)}")
            raise RuntimeError(f"Failed to fetch MVG data: {str(e)}")

    def get_departures(self, station_id, limit=8):
        """Fetch departures from MVG API."""
        try:
            url = f"{DEPARTURES_URL}?staId={station_id}&limit={limit}"
            headers = {
                'User-Agent': 'InkyPi/1.0'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            departures = []
            
            if 'departures' in data:
                for dep in data['departures']:
                    departure_time = self.parse_departure_time(dep.get('departureTime'))
                    line = dep.get('line', {})
                    
                    departures.append({
                        'time': departure_time,
                        'line_number': line.get('number', 'N/A'),
                        'line_name': line.get('name', 'Unknown'),
                        'destination': dep.get('destination', 'Unknown'),
                        'product': line.get('product', 'BUS'),
                        'platform': dep.get('platform', ''),
                        'delay': dep.get('delay', 0),
                        'cancelled': dep.get('cancelled', False),
                        'diversion': dep.get('diversion', False)
                    })
            
            return departures[:limit]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching MVG departures: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error parsing MVG data: {str(e)}")
            raise

    def get_stations(self, query):
        """Search for stations by name."""
        try:
            url = f"{STATIONS_URL}?query={query}"
            headers = {
                'User-Agent': 'InkyPi/1.0'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            stations = []
            
            if isinstance(data, list):
                for station in data[:10]:  # Return top 10 results
                    stations.append({
                        'id': station.get('id'),
                        'name': station.get('name'),
                        'latitude': station.get('latitude'),
                        'longitude': station.get('longitude')
                    })
            
            return stations
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching MVG stations: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error parsing stations data: {str(e)}")
            return []

    def parse_departure_time(self, time_value):
        """Parse departure time from MVG API."""
        if isinstance(time_value, int):
            # Unix timestamp in milliseconds
            from datetime import datetime
            return datetime.fromtimestamp(time_value / 1000).strftime('%H:%M')
        return str(time_value)

    def get_style_settings(self, settings):
        """Extract style settings from plugin settings."""
        style_settings = {}
        
        # Frame settings
        if 'frame_style' in settings:
            style_settings['frame_style'] = settings['frame_style']
        
        # Text color and size
        if 'text_color' in settings:
            style_settings['text_color'] = settings['text_color']
        
        if 'background_color' in settings:
            style_settings['background_color'] = settings['background_color']
        
        return style_settings
