"""Bulk Prompter node — standalone prompt variation generator."""

import json
from ..lib.bulk_prompter import generate_variants, ALL_STRATEGIES


class BulkPrompter:
    """Generates N prompt variants from a base prompt using local mutation strategies."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("variants", "count")
    FUNCTION = "generate"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_prompt": ("STRING", {"multiline": True}),
                "num_variants": ("INT", {"default": 10, "min": 1, "max": 1000}),
            },
            "optional": {
                "strategies": ("STRING", {
                    "default": ",".join(ALL_STRATEGIES),
                    "multiline": False,
                }),
                "custom_word_bank_path": ("STRING", {"default": ""}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2**31}),
            },
        }

    def generate(self, base_prompt, num_variants,
                 strategies=None, custom_word_bank_path="", seed=-1):

        # Parse strategies
        if strategies and isinstance(strategies, str):
            strat_list = [s.strip() for s in strategies.split(",") if s.strip()]
        else:
            strat_list = list(ALL_STRATEGIES)

        # Filter to valid strategies
        strat_list = [s for s in strat_list if s in ALL_STRATEGIES]
        if not strat_list:
            strat_list = list(ALL_STRATEGIES)

        actual_seed = seed if seed >= 0 else None
        custom_path = custom_word_bank_path if custom_word_bank_path else None

        variants = generate_variants(
            base_prompt=base_prompt,
            num_variants=num_variants,
            strategies=strat_list,
            custom_word_bank_path=custom_path,
            seed=actual_seed,
        )

        # Output as JSON array of prompt strings
        prompts = [v["prompt"] for v in variants]
        return (json.dumps(prompts, ensure_ascii=False), len(prompts))
