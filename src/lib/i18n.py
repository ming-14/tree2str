import json
import locale
import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)

_current_lang = "en_US"
_translations: Dict[str, str] = {}

SUPPORTED_LANGS = ["zh_CN", "en_US", "ja_JP", "ko_KR", "ru_RU"]
_DEFAULT_LANG = "en_US"

_LOCALE_MAP = {
    "zh": "zh_CN",
    "en": "en_US",
    "ja": "ja_JP",
    "ko": "ko_KR",
    "ru": "ru_RU",
}


def _locales_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "locales")


def detect_language() -> str:
    try:
        sys_loc = locale.getdefaultlocale()[0] or ""
    except Exception:
        sys_loc = ""
    if not sys_loc:
        return _DEFAULT_LANG
    prefix = sys_loc.split("_")[0].lower()
    mapped = _LOCALE_MAP.get(prefix)
    if mapped:
        return mapped
    return _DEFAULT_LANG


def _load_translations(lang: str) -> None:
    global _translations, _current_lang
    locales_dir = _locales_dir()
    filepath = os.path.join(locales_dir, f"{lang}.json")
    if not os.path.isfile(filepath):
        if lang != _DEFAULT_LANG:
            logger.info("翻译文件不存在: %s，回退到 %s", filepath, _DEFAULT_LANG)
            lang = _DEFAULT_LANG
            filepath = os.path.join(locales_dir, f"{lang}.json")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            _translations = json.load(f)
        _current_lang = lang
        logger.info("已加载翻译: %s (%d 条)", lang, len(_translations))
    except Exception as exc:
        logger.warning("加载翻译文件失败 (%s): %s", filepath, exc)
        _translations = {}
        _current_lang = _DEFAULT_LANG


def init(lang: str = None) -> None:
    detected = lang or detect_language()
    _load_translations(detected)


def t(key: str, **kwargs) -> str:
    text = _translations.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
