"""Anti-automation challenge detection. A challenge is recorded, never solved."""

from __future__ import annotations

# Public token used in FetchResult.classification_note / error_class.
# SourceOutcome stays at the Bible's 11 values; challenge is BLOCKED_BY_ACCESS
# plus this stated reason. Adding a 12th outcome would break the schema lock.
BLOCKED_BY_CHALLENGE = "BLOCKED_BY_CHALLENGE"

# (needle in lowered body, stable marker written into the note)
_CHALLENGE_MARKERS: tuple[tuple[str, str], ...] = (
    ("just a moment", "cloudflare_just_a_moment"),
    ("attention required", "cloudflare_attention_required"),
    ("cf-browser-verification", "cloudflare_browser_verification"),
    ("cf-challenge", "cloudflare_challenge"),
    ("checking your browser", "cloudflare_browser_check"),
    ("enable javascript and cookies", "js_cookie_interstitial"),
    ("sorry, you have been blocked", "cloudflare_blocked"),
    ("access denied", "access_denied"),
    ("unusual traffic", "unusual_traffic"),
    ("captcha", "captcha"),
    ("hcaptcha", "hcaptcha"),
    ("recaptcha", "recaptcha"),
    ("verify you are human", "verify_human"),
    ("are you a robot", "are_you_a_robot"),
)


def challenge_marker(text: str) -> str | None:
    """Return a stable marker if the body looks like an anti-automation gate."""
    lowered = text.lower()
    for needle, marker in _CHALLENGE_MARKERS:
        if needle in lowered:
            return marker
    return None


def looks_like_challenge(text: str) -> bool:
    return challenge_marker(text) is not None


def challenge_note(text: str) -> str:
    marker = challenge_marker(text) or "anti_automation_interstitial"
    return f"{BLOCKED_BY_CHALLENGE}: {marker}"


def is_challenge_block(note: str | None, error_class: str | None = None) -> bool:
    if error_class == BLOCKED_BY_CHALLENGE:
        return True
    return note is not None and note.startswith(BLOCKED_BY_CHALLENGE)
