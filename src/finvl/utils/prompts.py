"""
Prompt template loading and rendering for FinVL-MAS.
Inspired by R&D-Agent T() template system.
Loads YAML prompt files and renders with Jinja2.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

try:
    from jinja2 import Environment, StrictUndefined
    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"
_CACHE: Dict[str, Dict[str, Any]] = {}


def load_prompt_file(name: str) -> Dict[str, Any]:
    """Load a YAML prompt file by name (without extension)."""
    if name in _CACHE:
        return _CACHE[name]
    path = _PROMPT_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    _CACHE[name] = data
    return data


def render_prompt(
    file_name: str,
    prompt_key: str,
    part: str = "user_template",
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Load a prompt template and render it with context.

    Args:
        file_name: Name of the YAML file (e.g. "chart_analyst").
        prompt_key: Top-level key in the YAML (e.g. "chart_analysis").
        part: Which sub-key to render ("system" or "user_template").
        context: Template variables.

    Returns:
        Rendered prompt string.
    """
    data = load_prompt_file(file_name)
    section = data.get(prompt_key, {})
    template_str = section.get(part, "")

    if not template_str:
        return ""

    if HAS_JINJA and context:
        env = Environment(undefined=StrictUndefined)
        try:
            template = env.from_string(template_str)
            return template.render(**context)
        except Exception as e:
            logger.warning(f"Jinja render failed for {file_name}/{prompt_key}/{part}: {e}")
            return template_str

    return template_str


def get_system_prompt(file_name: str, prompt_key: str) -> str:
    """Shortcut to get the system prompt."""
    return render_prompt(file_name, prompt_key, part="system")
