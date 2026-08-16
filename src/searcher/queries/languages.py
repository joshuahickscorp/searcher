"""Multilingual query tools. Translation is not evidence authority (§13.5)."""

from __future__ import annotations

from dataclasses import dataclass

# Language → admitted sources that can actually run that language.
# review_required sources are not used for generation routing.
ADMITTED_SOURCES: dict[str, tuple[str, ...]] = {
    "en": (
        "searxng",
        "wikipedia",
        "marginalia",
        "internet_archive",
        "openverse",
        "ebay_browse_api",
        "therealreal",
        "rebag",
        "byronesque",
        "heroine",
    ),
    "ja": ("komehyo", "kind", "wikipedia_ja"),
    "ko": ("wikipedia_ko",),
    "zh": ("wikipedia_zh",),
    "fr": ("wikipedia_fr",),
    "it": ("wikipedia_it",),
    "ru": ("wikipedia_ru",),
}

SUPPORTED_LANGUAGES = tuple(ADMITTED_SOURCES)

CONDITION = {
    "en": {
        "used": "used",
        "archive": "archive",
        "vintage": "vintage",
        "deadstock": "deadstock",
        "sold": "sold",
    },
    "ja": {
        "used": "中古",
        "archive": "アーカイブ",
        "vintage": "ヴィンテージ",
        "deadstock": "デッドストック",
        "sold": "売り切れ",
    },
    "ko": {
        "used": "중고",
        "archive": "아카이브",
        "vintage": "빈티지",
        "deadstock": "데드스탁",
        "sold": "판매완료",
    },
    "zh": {
        "used": "二手",
        "archive": "Archive",
        "vintage": "古着",
        "deadstock": "未使用",
        "sold": "已售",
    },
    "fr": {
        "used": "occasion",
        "archive": "archive",
        "vintage": "vintage",
        "deadstock": "deadstock",
        "sold": "vendu",
    },
    "it": {
        "used": "usato",
        "archive": "archivio",
        "vintage": "vintage",
        "deadstock": "deadstock",
        "sold": "venduto",
    },
    "ru": {
        "used": "б/у",
        "archive": "архив",
        "vintage": "винтаж",
        "deadstock": "дедсток",
        "sold": "продано",
    },
}

CATEGORY = {
    "en": {"footwear": "sneaker", "unknown": ""},
    "ja": {"footwear": "スニーカー", "unknown": ""},
    "ko": {"footwear": "스니커즈", "unknown": ""},
    "zh": {"footwear": "运动鞋", "unknown": ""},
    "fr": {"footwear": "basket", "unknown": ""},
    "it": {"footwear": "sneaker", "unknown": ""},
    "ru": {"footwear": "кроссовки", "unknown": ""},
}

COLOUR = {
    "en": {"black": "black", "white": "white", "navy": "navy", "grey": "grey"},
    "ja": {"black": "ブラック", "white": "ホワイト", "navy": "ネイビー", "grey": "グレー"},
    "ko": {"black": "블랙", "white": "화이트", "navy": "네이비", "grey": "그레이"},
    "zh": {"black": "黑色", "white": "白色", "navy": "藏青", "grey": "灰色"},
    "fr": {"black": "noir", "white": "blanc", "navy": "marine", "grey": "gris"},
    "it": {"black": "nero", "white": "bianco", "navy": "navy", "grey": "grigio"},
    "ru": {"black": "чёрный", "white": "белый", "navy": "тёмно-синий", "grey": "серый"},
}

MATERIAL = {
    "en": {"leather": "leather", "suede": "suede", "canvas": "canvas"},
    "ja": {"leather": "レザー", "suede": "スエード", "canvas": "キャンバス"},
    "ko": {"leather": "가죽", "suede": "스웨이드", "canvas": "캔버스"},
    "zh": {"leather": "皮革", "suede": "麂皮", "canvas": "帆布"},
    "fr": {"leather": "cuir", "suede": "daim", "canvas": "toile"},
    "it": {"leather": "pelle", "suede": "camoscio", "canvas": "tela"},
    "ru": {"leather": "кожа", "suede": "замша", "canvas": "текстиль"},
}

_KATAKANA = {
    "a": "ア",
    "i": "イ",
    "u": "ウ",
    "e": "エ",
    "o": "オ",
    "ka": "カ",
    "ki": "キ",
    "ku": "ク",
    "ke": "ケ",
    "ko": "コ",
    "sa": "サ",
    "shi": "シ",
    "si": "シ",
    "su": "ス",
    "se": "セ",
    "so": "ソ",
    "ta": "タ",
    "chi": "チ",
    "ti": "チ",
    "tsu": "ツ",
    "tu": "ツ",
    "te": "テ",
    "to": "ト",
    "na": "ナ",
    "ni": "ニ",
    "nu": "ヌ",
    "ne": "ネ",
    "no": "ノ",
    "ha": "ハ",
    "hi": "ヒ",
    "fu": "フ",
    "hu": "フ",
    "he": "ヘ",
    "ho": "ホ",
    "ma": "マ",
    "mi": "ミ",
    "mu": "ム",
    "me": "メ",
    "mo": "モ",
    "ya": "ヤ",
    "yu": "ユ",
    "yo": "ヨ",
    "ra": "ラ",
    "ri": "リ",
    "ru": "ル",
    "re": "レ",
    "ro": "ロ",
    "wa": "ワ",
    "wo": "ヲ",
    "n": "ン",
    "ga": "ガ",
    "gi": "ギ",
    "gu": "グ",
    "ge": "ゲ",
    "go": "ゴ",
    "za": "ザ",
    "ji": "ジ",
    "zi": "ジ",
    "zu": "ズ",
    "ze": "ゼ",
    "zo": "ゾ",
    "da": "ダ",
    "di": "ヂ",
    "du": "ヅ",
    "de": "デ",
    "do": "ド",
    "ba": "バ",
    "bi": "ビ",
    "bu": "ブ",
    "be": "ベ",
    "bo": "ボ",
    "pa": "パ",
    "pi": "ピ",
    "pu": "プ",
    "pe": "ペ",
    "po": "ポ",
}

_CYRILLIC = str.maketrans(
    {
        "a": "а",
        "b": "б",
        "c": "к",
        "d": "д",
        "e": "е",
        "f": "ф",
        "g": "г",
        "h": "х",
        "i": "и",
        "j": "дж",
        "k": "к",
        "l": "л",
        "m": "м",
        "n": "н",
        "o": "о",
        "p": "п",
        "q": "к",
        "r": "р",
        "s": "с",
        "t": "т",
        "u": "у",
        "v": "в",
        "w": "в",
        "x": "кс",
        "y": "и",
        "z": "з",
    }
)

_HANGUL_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_HANGUL_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"


def _to_katakana(word: str) -> str:
    raw = "".join(ch.lower() if ch.isalpha() else " " for ch in word)
    out: list[str] = []
    i = 0
    while i < len(raw):
        if raw[i] == " ":
            i += 1
            continue
        matched = False
        for length in (3, 2, 1):
            chunk = raw[i : i + length]
            if chunk in _KATAKANA:
                out.append(_KATAKANA[chunk])
                i += length
                matched = True
                break
        if not matched:
            # Long vowels / leftover consonants get a vowel.
            ch = raw[i]
            out.append(_KATAKANA.get(ch + "u", _KATAKANA.get(ch, "・")))
            i += 1
    return "".join(out)


def _to_hangul_approx(word: str) -> str:
    """Very rough syllable packing. Brand Latin is also always preserved."""
    letters = [ch.lower() for ch in word if ch.isalpha()]
    if not letters:
        return word
    syllables: list[str] = []
    i = 0
    while i < len(letters):
        cho = min(max(ord(letters[i]) - 97, 0), 18)
        jung = 0
        if i + 1 < len(letters):
            jung = min(max(ord(letters[i + 1]) - 97, 0), 20)
            i += 2
        else:
            i += 1
        syllables.append(chr(0xAC00 + cho * 21 * 28 + jung * 28))
    return "".join(syllables)


def transliterate_brand(brand: str, language: str) -> str | None:
    if not brand:
        return None
    if language == "ja":
        return " ".join(_to_katakana(part) for part in brand.split())
    if language == "ko":
        return " ".join(_to_hangul_approx(part) for part in brand.split())
    if language == "ru":
        return " ".join(part.lower().translate(_CYRILLIC) for part in brand.split()).title()
    # zh: no general latin→hanzi. Keep Latin; category/condition carry the language.
    return None


@dataclass(frozen=True, slots=True)
class TranslationRecord:
    source_term: str
    translated_term: str
    language: str
    tool: str
    confidence: float
    improved_verified_retrieval: bool = False


def translate_term(
    term: str, language: str, table: dict[str, dict[str, str]]
) -> TranslationRecord | None:
    mapped = (table.get(language) or {}).get(term.lower())
    if not mapped:
        return None
    return TranslationRecord(
        source_term=term,
        translated_term=mapped,
        language=language,
        tool="searcher.queries.languages.static_table",
        confidence=0.8,
    )


def sources_for(language: str) -> tuple[str, ...]:
    return ADMITTED_SOURCES.get(language, ())
