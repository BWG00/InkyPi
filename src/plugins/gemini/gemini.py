from plugins.base_plugin.base_plugin import BasePlugin
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import base64
import requests
import logging



logger = logging.getLogger(__name__)

class Gemini(BasePlugin):
    def generate_image(self, settings, device_config):
        api_key = device_config.load_env_key("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI API Key not configured.")
        client = genai.Client(api_key=api_key)
        prompt = ("Create a simple drawing of a duck.")
        response = client.models.generate_content(
            model="emini-2.0-flash-preview-image-generation",
            contents=[prompt]
        )
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                logger.debug("Text: %s", part.text)
            elif part.inline_data is not None:
                image_data = base64.b64decode(part.inline_data.data)
                image = Image.open(BytesIO(image_data))
                return image
        return None
