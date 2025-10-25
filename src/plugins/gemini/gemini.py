from plugins.base_plugin.base_plugin import BasePlugin
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import base64
import logging
import requests
import os

logger = logging.getLogger(__name__)

GEMINI_IMAGE_MODELS = ["generative-image-1", "image-gemini-1", "image-bison"]
DEFAULT_GEMINI_MODEL = "generative-image-1"

class Gemini(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['api_key'] = {
            "required": True,
            "service": "Google",
            "expected_key": "GOOGLE_API_KEY"
        }
        return template_params

    def generate_image(self, settings, device_config):
        api_key = device_config.load_env_key("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("Google API key not configured (GOOGLE_API_KEY).")

        text_prompt = settings.get("textPrompt", "")
        image_model = settings.get("imageModel", DEFAULT_GEMINI_MODEL)
        if image_model not in GEMINI_IMAGE_MODELS:
            raise RuntimeError("Invalid image model specified for Gemini.")
        orientation = device_config.get_config("orientation") or "horizontal"
        size = self._size_for_model_and_orientation(image_model, orientation)
        randomize_prompt = settings.get('randomizePrompt') == 'true'
        quality = settings.get('quality', '')  # from settings.html

        # append quality/size hints to prompt when API params not available
        quality_map = {
            "hd": "high detail, sharp, high resolution",
            "standard": "standard detail",
            "high": "very detailed, high fidelity",
            "medium": "moderately detailed",
            "low": "simplified, low detail"
        }
        if quality in quality_map:
            text_prompt = f"{text_prompt}. {quality_map[quality]}."
        text_prompt = f"{text_prompt} (target size: {size})"

        try:
            if randomize_prompt:
                text_prompt = self.fetch_image_prompt(api_key, from_prompt=text_prompt)

            img = self.fetch_image(
                api_key=api_key,
                prompt=text_prompt,
                model=image_model,
                size=size
            )
        except Exception as e:
            logger.error(f"Gemini image request failed: {e}")
            raise RuntimeError("Gemini image request failed, check logs.")
        return img

    @staticmethod
    def _size_for_model_and_orientation(model, orientation):
        # Usable default sizes; include square option
        if model == "generative-image-1":
            if orientation == "horizontal":
                return "1792x1024"
            if orientation == "vertical":
                return "1024x1792"
            return "1536x1536"  # square
        if model == "image-gemini-1":
            if orientation == "horizontal":
                return "1536x1024"
            if orientation == "vertical":
                return "1024x1536"
            return "1280x1280"
        # Fallback
        return "1024x1024"

    @staticmethod
    def fetch_image(api_key, prompt, model="generative-image-1", size="1024x1024"):
        logger.info(f"Gemini generating image (model={model}, size={size}) for prompt: {prompt}")
        model_map = {
            "generative-image-1": "gemini-2.5-flash-image",
            "image-gemini-1": "gemini-1.0-image",
            "image-bison": "image-bison"
        }
        actual_model = model_map.get(model, model)

        # ensure client picks up key in env (more compatible)
        os.environ["GOOGLE_API_KEY"] = api_key
        client = genai.Client()

        response = client.models.generate_content(
            model=actual_model,
            contents=[prompt],
        )

        img = None
        try:
            candidates = getattr(response, "candidates", None) or []
            if not candidates:
                raise RuntimeError("No candidates in Gemini response.")
            parts = getattr(candidates[0].content, "parts", []) or []
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if inline is not None and getattr(inline, "data", None):
                    data = inline.data
                    # inline.data might be bytes or base64 string -> handle both
                    if isinstance(data, str):
                        try:
                            data = base64.b64decode(data)
                        except Exception:
                            data = data.encode('utf-8')
                    img = Image.open(BytesIO(data))
                    break
                # Fallback: if text contains a URL to an image
                text = getattr(part, "text", None)
                if text and ("http://" in text or "https://" in text):
                    # take first token as URL
                    url = text.strip().split()[0]
                    try:
                        r = requests.get(url, timeout=30)
                        r.raise_for_status()
                        img = Image.open(BytesIO(r.content))
                        break
                    except Exception:
                        continue
            if img is None:
                # Last fallback: maybe response contains base64 fields in dict form
                j = response.to_dict() if hasattr(response, "to_dict") else None
                if j:
                    # Recursively search for base64 strings
                    def find_b64(o):
                        if isinstance(o, dict):
                            for v in o.values():
                                r = find_b64(v)
                                if r:
                                    return r
                        elif isinstance(o, list):
                            for item in o:
                                r = find_b64(item)
                                if r:
                                    return r
                        elif isinstance(o, str) and len(o) > 100:
                            try:
                                base64.b64decode(o, validate=True)
                                return o
                            except Exception:
                                return None
                        return None
                    b64 = find_b64(j)
                    if b64:
                        img = Image.open(BytesIO(base64.b64decode(b64)))

            if img is None:
                raise RuntimeError("No image found in Gemini response.")
            return img
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")
            raise

    @staticmethod
    def _extract_base64_from_response(json_obj):
        """
        Recursively scans the JSON response and attempts to find a base64 string field.
        Supports multiple possible keys that may appear across API versions.
        """
        candidates = []
        # known possible keys
        keys_to_check = ["image", "b64_json", "b64", "content", "data"]
        def recurse(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in keys_to_check and isinstance(v, str) and Gemini._looks_like_base64(v):
                        candidates.append(v)
                    else:
                        recurse(v)
            elif isinstance(o, list):
                for item in o:
                    recurse(item)
        recurse(json_obj)
        return candidates[0] if candidates else None

    @staticmethod
    def _looks_like_base64(s):
        # simple heuristic: base64 characters and length
        if not isinstance(s, str):
            return False
        s_stripped = s.strip()
        if len(s_stripped) < 100:
            return False
        try:
            # attempt to decode without raising
            base64.b64decode(s_stripped, validate=True)
            return True
        except Exception:
            return False

    def fetch_image_prompt(self, api_key, from_prompt=None):
        """
        Optional helper to produce an enhanced/randomized prompt via the Generative Language HTTP API.
        Returns the generated prompt as a string.
        """
        logger.info("Gemini: generating image prompt via Generative Language API")
        endpoint = f"https://generativelanguage.googleapis.com/v1beta2/models/text-bison-001:generate?key={api_key}"
        if from_prompt and from_prompt.strip():
            system = (
                "Rewrite the given short image description to a vivid, unique and compact image prompt "
                "suitable for image generation. Keep it <= 20 words, include an artist/movie/time period, "
                "and keep the original subject."
            )
            prompt_text = f"{system}\nOriginal: {from_prompt}"
        else:
            prompt_text = (
                "Create a completely random, unusual and concise image prompt (<=20 words), "
                "including an artist/movie or time period reference."
            )

        payload = {
            "prompt": {
                "text": prompt_text
            },
            "temperature": 1.0,
            "max_output_tokens": 256
        }
        resp = requests.post(endpoint, json=payload, timeout=30)
        resp.raise_for_status()
        j = resp.json()
        # Google API is expected to return candidates[0].content or output[0].content
        prompt = None
        if isinstance(j, dict):
            if "candidates" in j and j["candidates"]:
                prompt = j["candidates"][0].get("content")
            elif "output" in j and j["output"]:
                prompt = j["output"][0].get("content")
        if not prompt:
            # Fallback: recursively search for a longer text field
            def find_text(o):
                if isinstance(o, dict):
                    for v in o.values():
                        r = find_text(v)
                        if r:
                            return r
                elif isinstance(o, list):
                    for item in o:
                        r = find_text(item)
                        if r:
                            return r
                elif isinstance(o, str) and len(o.split()) <= 30 and len(o) > 10:
                    return o
                return None
            prompt = find_text(j)

        if not prompt:
            raise RuntimeError("No prompt received from the Generative Language API.")
        prompt = prompt.strip()
        logger.info(f"Gemini generated prompt: {prompt}")
        return prompt
