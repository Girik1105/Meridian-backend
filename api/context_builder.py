import json
import re
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_prompt_cache = {}


def _load_prompt(name):
    if name not in _prompt_cache:
        _prompt_cache[name] = (PROMPTS_DIR / f"{name}.txt").read_text()
    return _prompt_cache[name]


class ContextBuilder:
    MAX_MESSAGES = 10

    async def build_for_onboarding(self, user_profile, messages_qs, summary=None):
        profile_data = user_profile.profile_data or {}
        profile_json = json.dumps(profile_data, indent=2) if profile_data else "{}"

        system_prompt = _load_prompt("onboarding").format(profile_data=profile_json)
        conversation_messages = await self._format_messages(messages_qs, summary)

        return system_prompt, conversation_messages

    async def _format_messages(self, messages_qs, summary=None):
        # Get last MAX_MESSAGES ordered by created_at
        count = await messages_qs.acount()
        offset = max(0, count - self.MAX_MESSAGES)
        messages = []
        async for msg in messages_qs.order_by("created_at")[offset:]:
            messages.append(msg)

        formatted = []

        if summary:
            formatted.append({
                "role": "user",
                "content": f"[Previous conversation summary: {summary}]",
            })

        for msg in formatted_messages(messages):
            formatted.append(msg)

        return formatted


def formatted_messages(messages):
    for msg in messages:
        role = msg.role if msg.role in ("user", "assistant") else "user"
        content = msg.content
        if msg.role == "system":
            content = f"[System: {content}]"
        yield {"role": role, "content": content}


def extract_structured_data(response_text):
    """Extract <profile_update> JSON from Claude's response.
    Returns (clean_text, profile_update_dict_or_None).
    """
    pattern = r"<profile_update>(.*?)</profile_update>"
    match = re.search(pattern, response_text, re.DOTALL)

    if not match:
        return response_text, None

    try:
        profile_update = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return response_text, None

    clean_text = re.sub(pattern, "", response_text, flags=re.DOTALL).strip()
    return clean_text, profile_update


def merge_profile_data(existing, update):
    """Deep-merge update into existing profile data. Overwrites scalars/lists, merges dicts."""
    if not update:
        return existing

    merged = dict(existing)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_profile_data(merged[key], value)
        else:
            merged[key] = value
    return merged
