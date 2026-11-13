"""Deterministic Polish voice/text intents. Model output never reaches this parser; only the owner's own words do."""
from dataclasses import dataclass
import re
import unicodedata

WAKE_WORDS = ('jarvis', 'jarvisie', 'dżarwis', 'dzarwis', 'jarwis')
GATE_NOUNS = r'(?:bram[aeęy]|bramk[aeęi]|garaz\w*|wjazd\w*|szlaban\w*)'
OPEN = r'(?:otworz\w*|otwieraj|otwarcie|odblokuj|podnies\w*|open)'
CLOSE = r'(?:zamknij|zamykaj|zamkniecie|zamykac|opusc\w*|close)'
STOP = r'(?:zatrzymaj|stop|stoj|przerwij|wstrzymaj)'
STATUS = r'(?:stan|status|czy .*(?:otwart|zamkniet)|jak(?:i|a)? (?:jest )?stan|sprawdz)'
YES = re.compile(r'^(?:tak|potwierdzam|potwierdz|zrob to|dawaj|jasne|oczywiscie|ok|okej|zgoda|wykonaj|pewnie)[.!]?$')
NO = re.compile(r'^(?:nie|anuluj|odwolaj|rezygnuje|stop|zostaw|nie trzeba)[.!]?$')


@dataclass(frozen=True)
class Intent:
    kind: str            # gate | confirm | cancel
    action: str = ''     # open | close | stop | status
    wake: bool = False
    text: str = ''


def normalize(text: str) -> str:
    folded = unicodedata.normalize('NFKD', text.lower().replace('ł', 'l').replace('Ł', 'l'))
    folded = ''.join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9 ]+', ' ', folded).strip()


def strip_wake(text: str) -> tuple[str, bool]:
    for word in WAKE_WORDS:
        pattern = r'^(?:hej |hey |ok |okej |sluchaj )?' + re.escape(normalize(word)) + r'\b[ ,]*'
        changed = re.sub(pattern, '', text, count=1)
        if changed != text:
            return re.sub(r'\s+', ' ', changed).strip(), True
    return text, False


def parse(message: str) -> Intent | None:
    """Return a gate/confirm/cancel intent or None when the message should go to the model."""
    if not isinstance(message, str) or len(message) > 400:
        return None
    text = normalize(message)
    text, wake = strip_wake(text)
    if not text:
        return None
    if YES.fullmatch(text):
        return Intent('confirm', wake=wake, text=text)
    if NO.fullmatch(text):
        return Intent('cancel', wake=wake, text=text)
    if not re.search(r'\b' + GATE_NOUNS + r'\b', text) and not re.search(r'\bgaraz', text):
        return None
    words = len(text.split())
    if words > 12:
        return None
    if re.search(r'\b' + STOP + r'\b', text):
        return Intent('gate', 'stop', wake, text)
    if re.search(r'\b' + OPEN + r'\b', text):
        return Intent('gate', 'open', wake, text)
    if re.search(r'\b' + CLOSE + r'\b', text):
        return Intent('gate', 'close', wake, text)
    if re.search(STATUS, text):
        return Intent('gate', 'status', wake, text)
    return None
