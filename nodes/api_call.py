"""Webhook node — calls any REST API with retry and response extraction."""

import json
import time
import urllib.request
import urllib.error
import logging

from ..lib.response_parser import extract_mappings, auto_parse_json
from ..lib.secrets import get_api_key

logger = logging.getLogger(__name__)


class Webhook:
    """Calls a REST API with configurable retry and dot-path response extraction.
    Use for notifications, triggering external workflows, or fetching data."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("response", "status_code", "extracted")
    FUNCTION = "call"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {"default": ""}),
                "method": (["POST", "GET", "PUT", "PATCH"],),
            },
            "optional": {
                "body": ("STRING", {"multiline": True, "default": ""}),
                "headers": ("STRING", {"multiline": True, "default": ""}),
                "response_mapping": ("STRING", {"default": ""}),
                "api_key_name": ("STRING", {"default": ""}),
                "timeout": ("INT", {"default": 30, "min": 5, "max": 300}),
                "max_retries": ("INT", {"default": 3, "min": 0, "max": 10}),
                "retry_delay": ("INT", {"default": 2, "min": 1, "max": 30}),
                "topic": ("STRING", {"default": ""}),
                "passthrough": ("*",),
            },
        }

    def call(self, url, method,
             body="", headers="", response_mapping="",
             api_key_name="", timeout=30, max_retries=3,
             retry_delay=2, topic="", passthrough=None):

        if not url:
            return ('{"error": "No URL provided"}', 0, "{}")

        # Template substitution
        body_str = body
        if topic:
            body_str = body_str.replace("{topic}", topic)

        # Build headers
        req_headers = {"Content-Type": "application/json"}
        api_key = get_api_key(api_key_name)
        if api_key:
            req_headers["Authorization"] = f"Bearer {api_key}"
        if headers:
            try:
                req_headers.update(json.loads(headers))
            except json.JSONDecodeError:
                pass

        body_bytes = None
        if method in ("POST", "PUT", "PATCH") and body_str.strip():
            body_bytes = body_str.encode("utf-8")

        last_error = None
        raw_response = ""
        status_code = 0

        for attempt in range(max_retries + 1):
            try:
                req = urllib.request.Request(
                    url, data=body_bytes, headers=req_headers, method=method
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    status_code = resp.status
                    raw_response = resp.read().decode("utf-8")

                # Extract mapped fields if response_mapping provided
                extracted = "{}"
                if response_mapping.strip():
                    response_data = auto_parse_json(raw_response)
                    if not isinstance(response_data, dict):
                        response_data = {"content": response_data}
                    mapped = extract_mappings(response_data, response_mapping)
                    extracted = json.dumps(mapped, ensure_ascii=False)

                return (raw_response, status_code, extracted)

            except urllib.error.HTTPError as e:
                status_code = e.code
                last_error = str(e)
                raw_response = e.read().decode("utf-8") if hasattr(e, "read") else ""
                logger.warning("Webhook attempt %d/%d failed: %s",
                               attempt + 1, max_retries + 1, e)
                if attempt < max_retries:
                    time.sleep(retry_delay * (2 ** attempt))

            except Exception as e:
                last_error = str(e)
                logger.warning("Webhook attempt %d/%d failed: %s",
                               attempt + 1, max_retries + 1, e)
                if attempt < max_retries:
                    time.sleep(retry_delay * (2 ** attempt))

        error_response = json.dumps({"error": last_error})
        return (raw_response or error_response, status_code, "{}")
