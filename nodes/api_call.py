"""API Call node — calls external LLM or any REST API with retry logic."""

import json
import time
import urllib.request
import urllib.error
import logging

from ..lib.response_parser import extract_mappings, auto_parse_json

logger = logging.getLogger(__name__)


class APICall:
    """Calls external LLM or any REST API. OpenAI-compatible as default preset."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompt", "negative_prompt", "metadata", "raw_response")
    FUNCTION = "call_api"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_preset": (["openai_compatible", "generic"],),
                "api_url": ("STRING", {"default": ""}),
                "method": (["POST", "GET"],),
                "request_template": ("STRING", {"multiline": True, "default": ""}),
                "response_mapping": ("STRING", {"multiline": True, "default": "prompt=choices.0.message.content"}),
                "timeout": ("INT", {"default": 30, "min": 5, "max": 300}),
                "max_retries": ("INT", {"default": 3, "min": 0, "max": 10}),
                "retry_delay": ("INT", {"default": 2, "min": 1, "max": 30}),
            },
            "optional": {
                "llm_config": ("LLM_CONFIG",),
                "api_key": ("STRING", {"default": ""}),
                "headers": ("STRING", {"multiline": True, "default": ""}),
                "topic": ("STRING", {"default": ""}),
            },
        }

    def call_api(self, api_preset, api_url, method, request_template,
                 response_mapping, timeout, max_retries, retry_delay,
                 llm_config=None, api_key="", headers="", topic=""):

        # LLM_CONFIG overrides manual fields when connected
        if llm_config:
            api_url = api_url or llm_config.get("api_url", "")
            api_key = api_key or llm_config.get("api_key", "")
            api_preset = "openai_compatible"

        if not api_url:
            return ("", "", "{}", '{"error": "No API URL provided"}')

        body_str = request_template
        if topic:
            body_str = body_str.replace("{topic}", topic)

        req_headers = {"Content-Type": "application/json"}
        if api_preset == "openai_compatible" and api_key:
            req_headers["Authorization"] = f"Bearer {api_key}"
        if headers:
            try:
                req_headers.update(json.loads(headers))
            except json.JSONDecodeError:
                pass

        body_bytes = None
        if method == "POST" and body_str.strip():
            body_bytes = body_str.encode("utf-8")

        last_error = None
        raw_response = ""

        for attempt in range(max_retries + 1):
            try:
                req = urllib.request.Request(
                    api_url, data=body_bytes, headers=req_headers, method=method
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw_response = resp.read().decode("utf-8")

                response_data = auto_parse_json(raw_response)
                if not isinstance(response_data, dict):
                    response_data = {"content": response_data}

                extracted = extract_mappings(response_data, response_mapping)
                prompt = str(extracted.get("prompt", ""))
                negative_prompt = str(extracted.get("negative_prompt", ""))
                metadata_json = json.dumps(extracted, ensure_ascii=False)
                return (prompt, negative_prompt, metadata_json, raw_response)

            except Exception as e:
                last_error = str(e)
                logger.warning(f"API call attempt {attempt + 1}/{max_retries + 1} failed: {e}")
                if attempt < max_retries:
                    time.sleep(retry_delay * (2 ** attempt))

        error_response = json.dumps({"error": last_error})
        return ("", "", error_response, raw_response or error_response)
