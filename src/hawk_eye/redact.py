from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_DOMAIN_RE = re.compile(r"\b[a-zA-Z0-9-]{1,63}(?:\.[a-zA-Z0-9-]{1,63})+\b")


@dataclass(frozen=True)
class RedactionConfig:
    redact_ipv4: bool = True
    redact_domains: bool = True


def redact_text(text: str, cfg: RedactionConfig = RedactionConfig()) -> str:
    out = text
    if cfg.redact_ipv4:
        out = _IPV4_RE.sub("[REDACTED_IP]", out)
    if cfg.redact_domains:
        out = _DOMAIN_RE.sub("[REDACTED_DOMAIN]", out)
    return out


def redact_obj(obj: Any, cfg: RedactionConfig = RedactionConfig()) -> Any:
    if obj is None:
        return None
    if isinstance(obj, str):
        return redact_text(obj, cfg)
    if isinstance(obj, list):
        return [redact_obj(x, cfg) for x in obj]
    if isinstance(obj, dict):
        return {k: redact_obj(v, cfg) for k, v in obj.items()}
    return obj

