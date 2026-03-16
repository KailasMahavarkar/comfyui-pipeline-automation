"""Prompt List node — user-provided prompts as a typed PROMPT_LIST."""

from ..lib.prompt_mutations import parse_prompt_list


class PromptList:
    """Accepts prompts as newline-separated text or a JSON array.
    Outputs a typed PROMPT_LIST for Prompt Generator."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("PROMPT_LIST",)
    RETURN_NAMES = ("prompt_list",)
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompts": ("STRING", {"multiline": True}),
            },
        }

    def build(self, prompts):
        variants = parse_prompt_list(prompts)
        return ({"prompts": [v["prompt"] for v in variants]},)
