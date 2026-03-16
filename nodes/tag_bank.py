"""Tag Bank node — custom word banks and topic tags as a typed TAG_BANK."""


class TagBank:
    """Bundles custom word bank path and per-topic curated tags into
    a typed TAG_BANK object for Prompt Generator."""

    CATEGORY = "Pipeline Automation"
    RETURN_TYPES = ("TAG_BANK",)
    RETURN_NAMES = ("tag_bank",)
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "custom_word_bank_path": ("STRING", {"default": ""}),
                "topic_tag_bank": ("STRING", {"multiline": True, "default": ""}),
            },
        }

    def build(self, custom_word_bank_path="", topic_tag_bank=""):
        return ({
            "word_bank_path": custom_word_bank_path or None,
            "topic_tags": topic_tag_bank or None,
        },)
