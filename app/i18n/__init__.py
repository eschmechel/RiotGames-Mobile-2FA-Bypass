import json
import locale
from pathlib import Path

DEFAULT_LANGUAGE = "en"

LANGUAGES = {
    "en": "English",
    "es": "Español",
    "fr": "Français",
}

_translations: dict = {}
_current_language: str = DEFAULT_LANGUAGE


def get_language() -> str:
    return _current_language


def set_language(lang: str) -> None:
    global _current_language
    if lang in LANGUAGES:
        _current_language = lang
        _load_translations(lang)


def _get_language_file_path(lang: str) -> Path:
    base_dir = Path(__file__).parent
    return base_dir / f"{lang}.json"


def _load_translations(lang: str) -> None:
    global _translations
    file_path = _get_language_file_path(lang)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            _translations = json.load(f)
    except (OSError, json.JSONDecodeError):
        if lang != DEFAULT_LANGUAGE:
            _load_translations(DEFAULT_LANGUAGE)


def _detect_system_language() -> str:
    try:
        system_lang = locale.getlocale()[0]
        if system_lang:
            lang_code = system_lang.split("_")[0].split("-")[0]
            if lang_code in LANGUAGES:
                return lang_code
    except Exception:
        pass
    return DEFAULT_LANGUAGE


def init() -> None:
    from app.core.storage import load_config, save_config

    config = load_config()
    if config and config.get("language"):
        lang = config["language"]
    else:
        lang = _detect_system_language()
        if config is None:
            config = {}
        config["language"] = lang
        save_config(config)

    set_language(lang)


def t(key: str, **kwargs) -> str:
    keys = key.split(".")
    value = _translations
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k, key)
        else:
            return key

    if isinstance(value, str) and kwargs:
        return value.format(**kwargs)
    return value if isinstance(value, str) else key


def get_available_languages() -> dict:
    return LANGUAGES.copy()
