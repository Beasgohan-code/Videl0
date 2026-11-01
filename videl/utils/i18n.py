"""Conservative, privacy-localized translations for private bot replies.

Unknown phrases intentionally remain in English until a reviewed translation is
added; user-authored text, commands, URLs and inline code are never translated.
"""
from __future__ import annotations

import re

LANGUAGES = {"en": "English", "ml": "Malayalam", "hi": "Hindi", "ta": "Tamil"}

_TRANSLATIONS = {
    "ml": {
        "Your private preferences": "നിങ്ങളുടെ സ്വകാര്യ മുൻഗണനകൾ",
        "Optional bot updates": "ഐച്ഛിക ബോട്ട് അപ്‌ഡേറ്റുകൾ",
        "Reminder quiet hours": "ഓർമ്മപ്പെടുത്തലുകൾക്കുള്ള ശാന്തസമയം",
        "Opted in": "അനുവദിച്ചു",
        "Off by default": "ആരംഭത്തിൽ ഓഫ്",
        "Reminder saved": "ഓർമ്മപ്പെടുത്തൽ സംരക്ഷിച്ചു",
        "Reminder limit": "ഓർമ്മപ്പെടുത്തൽ പരിധി",
        "No reminders": "ഓർമ്മപ്പെടുത്തലുകളില്ല",
        "Your reminders": "നിങ്ങളുടെ ഓർമ്മപ്പെടുത്തലുകൾ",
        "Reminders cleared": "ഓർമ്മപ്പെടുത്തലുകൾ നീക്കി",
        "Reminder": "ഓർമ്മപ്പെടുത്തൽ",
        "Help center": "സഹായകേന്ദ്രം",
        "Accessible command help": "എളുപ്പത്തിൽ വായിക്കാവുന്ന കമാൻഡ് സഹായം",
        "Showing": "കാണിക്കുന്നു",
        "commands": "കമാൻഡുകൾ",
        "Example:": "ഉദാഹരണം:",
        "Language updated": "ഭാഷ മാറ്റി",
        "English": "ഇംഗ്ലീഷ്",
        "Malayalam": "മലയാളം",
        "Hindi": "ഹിന്ദി",
        "Tamil": "തമിഴ്",
    },
    "hi": {
        "Your private preferences": "आपकी निजी प्राथमिकताएँ",
        "Optional bot updates": "वैकल्पिक बॉट अपडेट",
        "Reminder quiet hours": "रिमाइंडर के शांत घंटे",
        "Opted in": "सहमति दी गई",
        "Off by default": "डिफ़ॉल्ट रूप से बंद",
        "Reminder saved": "रिमाइंडर सहेजा गया",
        "Reminder limit": "रिमाइंडर सीमा",
        "No reminders": "कोई रिमाइंडर नहीं",
        "Your reminders": "आपके रिमाइंडर",
        "Reminders cleared": "रिमाइंडर हटाए गए",
        "Reminder": "रिमाइंडर",
        "Help center": "सहायता केंद्र",
        "Accessible command help": "सरल कमांड सहायता",
        "Showing": "दिखाए जा रहे हैं",
        "commands": "कमांड",
        "Example:": "उदाहरण:",
        "Language updated": "भाषा अपडेट की गई",
        "English": "अंग्रेज़ी",
        "Malayalam": "मलयालम",
        "Hindi": "हिंदी",
        "Tamil": "तमिल",
    },
    "ta": {
        "Your private preferences": "உங்கள் தனிப்பட்ட விருப்பங்கள்",
        "Optional bot updates": "விருப்பமான போட் புதுப்பிப்புகள்",
        "Reminder quiet hours": "நினைவூட்டல்களுக்கான அமைதி நேரம்",
        "Opted in": "ஒப்புதல் அளிக்கப்பட்டது",
        "Off by default": "இயல்பாக முடக்கம்",
        "Reminder saved": "நினைவூட்டல் சேமிக்கப்பட்டது",
        "Reminder limit": "நினைவூட்டல் வரம்பு",
        "No reminders": "நினைவூட்டல்கள் இல்லை",
        "Your reminders": "உங்கள் நினைவூட்டல்கள்",
        "Reminders cleared": "நினைவூட்டல்கள் நீக்கப்பட்டன",
        "Reminder": "நினைவூட்டல்",
        "Help center": "உதவி மையம்",
        "Accessible command help": "எளிய கட்டளை உதவி",
        "Showing": "காட்டப்படுகிறது",
        "commands": "கட்டளைகள்",
        "Example:": "எடுத்துக்காட்டு:",
        "Language updated": "மொழி புதுப்பிக்கப்பட்டது",
        "English": "ஆங்கிலம்",
        "Malayalam": "மலையாளம்",
        "Hindi": "இந்தி",
        "Tamil": "தமிழ்",
    },
}

_TAG = re.compile(r"^(<\s*/?\s*([a-zA-Z0-9_-]+)\b[^>]*>)$")


def localize_html(value: str, language: str) -> str:
    """Translate exact authored text nodes while preserving HTML and code spans."""
    table = _TRANSLATIONS.get(language)
    if not table or not isinstance(value, str):
        return value
    parts = re.split(r"(<[^>]+>)", value)
    in_code = 0
    output = []
    for part in parts:
        match = _TAG.match(part)
        if match:
            tag = match.group(2).casefold()
            if tag in {"code", "pre"}:
                in_code += -1 if part.startswith("</") else 1
                in_code = max(0, in_code)
            output.append(part)
            continue
        if in_code or not part.strip():
            output.append(part)
            continue
        leading = part[:len(part) - len(part.lstrip())]
        trailing = part[len(part.rstrip()):]
        text = part.strip()
        output.append(leading + table.get(text, text) + trailing)
    return "".join(output)
