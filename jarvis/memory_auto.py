"""Finite, local extraction from the current owner's completed chat turn.

Only whole-message declarations with catalogued values qualify. No arbitrary
model output or free-text values can enter automatic personal memory.
"""
import json
import re
import time
import unicodedata
import uuid
from . import memory_policy

VERSION = 'pl-declarations-v1'


def normalized(text):
    return ''.join(ch for ch in unicodedata.normalize('NFD', text.casefold())
                   if not unicodedata.combining(ch)).replace('ł', 'l')


# Each rule yields a backend-authored sentence, a stable key and a finite value.
RULES = [
    ('preferences', 'response_length', r'(?:preferuje|wole) (krotkie|szczegolowe) odpowiedzi',
     {'krotkie': 'Preferuję krótkie odpowiedzi.', 'szczegolowe': 'Preferuję szczegółowe odpowiedzi.'}),
    ('preferences', 'language', r'(?:preferuje|wole) odpowiedzi (po polsku|po angielsku)',
     {'po polsku': 'Preferuję odpowiedzi po polsku.', 'po angielsku': 'Preferuję odpowiedzi po angielsku.'}),
    ('equipment', 'computer_os', r'(?:uzywam|moj system to) (windows 10|windows 11|linux|macos)',
     {'windows 10': 'Używam Windows 10.', 'windows 11': 'Używam Windows 11.',
      'linux': 'Używam Linux.', 'macos': 'Używam macOS.'}),
    ('equipment', 'phone_os', r'moj telefon ma system (android|ios)',
     {'android': 'Mój telefon ma system Android.', 'ios': 'Mój telefon ma system iOS.'}),
    ('projects', 'active_project', r'(?:pracuje nad projektem|rozwijam projekt) (jarvis os|autologika os)',
     {'jarvis os': 'Pracuję nad projektem JARVIS OS.', 'autologika os': 'Pracuję nad projektem AutoLogika OS.'}),
    ('decisions', 'model_location', r'zdecydowalem,? ze modele ai maja dzialac (lokalnie)',
     {'lokalnie': 'Zdecydowałem, że modele AI mają działać lokalnie.'}),
    ('decisions', 'backup_frequency', r'zdecydowalem,? ze kopie zapasowe robimy (codziennie|co tydzien)',
     {'codziennie': 'Zdecydowałem, że kopie zapasowe robimy codziennie.',
      'co tydzien': 'Zdecydowałem, że kopie zapasowe robimy co tydzień.'}),
    ('working_style', 'workflow', r'(?:preferuje|wole) pracowac (etapami|nad jednym zadaniem naraz)',
     {'etapami': 'Wolę pracować etapami.', 'nad jednym zadaniem naraz': 'Wolę pracować nad jednym zadaniem naraz.'}),
]


def extract(text):
    # Reject control characters, quotes, extra sentences, unknown values and
    # surrounding instructions. Strip only ordinary spaces and one final dot.
    if len(text) > 300 or not re.fullmatch(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż0-9 ,.]+', text):
        return None
    value = normalized(text.strip(' '))
    replace = value.startswith('od teraz ')
    if replace:
        value = value[len('od teraz '):]
    if value.endswith('.'):
        value = value[:-1]
    for category, key, pattern, texts in RULES:
        match = re.fullmatch(pattern, value)
        if match:
            return {'category': category, 'key': category + '.' + key,
                    'value': match[1], 'text': texts[match[1]], 'replace': replace}
    return None


def install(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS memory_epoch(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL);
    INSERT OR IGNORE INTO memory_epoch VALUES(1,0);
    CREATE TRIGGER IF NOT EXISTS memory_epoch_insert AFTER INSERT ON memory BEGIN UPDATE memory_epoch SET revision=revision+1 WHERE id=1; END;
    CREATE TRIGGER IF NOT EXISTS memory_epoch_update AFTER UPDATE ON memory BEGIN UPDATE memory_epoch SET revision=revision+1 WHERE id=1; END;
    CREATE TRIGGER IF NOT EXISTS memory_epoch_delete AFTER DELETE ON memory BEGIN UPDATE memory_epoch SET revision=revision+1 WHERE id=1; END;
    CREATE TABLE IF NOT EXISTS memory_turns(turn_id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,policy_revision INTEGER NOT NULL,memory_revision INTEGER NOT NULL,capture_allowed INTEGER NOT NULL,outcome TEXT);
    CREATE TABLE IF NOT EXISTS memory_auto_keys(fact_key TEXT PRIMARY KEY,memory_id TEXT NOT NULL UNIQUE REFERENCES memory(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS memory_origins(memory_id TEXT NOT NULL REFERENCES memory(id) ON DELETE CASCADE,revision INTEGER NOT NULL,session_id TEXT NOT NULL,turn_id TEXT NOT NULL,quote TEXT NOT NULL,extractor TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(memory_id,revision));
    ''')


def begin(c, session_id, turn_id, allowed):
    c.execute('INSERT INTO memory_turns VALUES(?,?,?,?,?,NULL)',
              (turn_id, session_id, memory_policy.policy(c)[0],
               c.execute('SELECT revision FROM memory_epoch WHERE id=1').fetchone()[0], int(allowed)))


def capture(c, session_id, turn_id):
    """Called inside the chat finalization write transaction; never commits."""
    receipt = c.execute('SELECT * FROM memory_turns WHERE turn_id=? AND session_id=?', (turn_id, session_id)).fetchone()
    if receipt is None:  # A turn started before the migration is ineligible.
        return {'status': 'missing_snapshot', 'saved': 0}
    if receipt['outcome']:
        return json.loads(receipt['outcome'])

    def outcome(status, ident=None):
        result = {'status': status, 'saved': int(status in ('created', 'updated'))}
        if ident:
            result['memory_id'] = ident
        c.execute('UPDATE memory_turns SET outcome=? WHERE turn_id=?', (json.dumps(result), turn_id))
        return result

    row = c.execute("SELECT content FROM chat_messages WHERE session_id=? AND turn_id=? AND role='user' AND state='pending'",
                    (session_id, turn_id)).fetchone()
    if not row or not receipt['capture_allowed']:
        return outcome('request_excluded')
    text = row['content']
    if memory_policy.refuses_memory(text):
        return outcome('request_excluded')
    revision, policy = memory_policy.policy(c)
    if revision != receipt['policy_revision']:
        return outcome('policy_changed')
    if not policy.enabled or policy.mode != 'auto':
        return outcome('disabled')
    candidate = extract(text)
    if not candidate:
        return outcome('unsupported')
    if candidate['category'] not in policy.categories:
        return outcome('category_disabled')
    if c.execute('SELECT revision FROM memory_epoch WHERE id=1').fetchone()[0] != receipt['memory_revision']:
        return outcome('memory_changed')

    prior = c.execute('''SELECT m.*,s.source,s.revision,s.category FROM memory_auto_keys k
                        JOIN memory m ON m.id=k.memory_id JOIN memory_sources s ON s.memory_id=m.id
                        WHERE k.fact_key=?''', (candidate['key'],)).fetchone()
    # Also recognize supported declarations in old/manual notes. Never guess
    # relationships to arbitrary manual prose or infer permission to overwrite.
    notes = c.execute('SELECT id,text FROM memory LIMIT 1001').fetchall()
    if len(notes) > 1000:
        return outcome('memory_capacity')
    for note in notes:
        other = extract(note['text'])
        if other and other['key'] == candidate['key']:
            if other['text'] == candidate['text']:
                return outcome('duplicate', note['id'])
            if not prior or note['id'] != prior['id']:
                return outcome('protected_conflict')
    now = time.time()
    if prior:
        if prior['source'] != 'owner_auto':
            return outcome('protected_conflict')
        if not candidate['replace']:
            return outcome('conflict')
        ident, next_revision = prior['id'], prior['revision'] + 1
        c.execute('INSERT INTO memory_history(memory_id,revision,text,source,category,created) VALUES(?,?,?,?,?,?)',
                  (ident, prior['revision'], prior['text'], prior['source'], prior['category'], now))
        c.execute('UPDATE memory SET text=? WHERE id=?', (candidate['text'], ident))
        c.execute('UPDATE memory_sources SET revision=?,updated=? WHERE memory_id=?', (next_revision, now, ident))
        c.execute('DELETE FROM memory_vectors WHERE memory_id=?', (ident,))
        status = 'updated'
    else:
        ident, next_revision = str(uuid.uuid4()), 0
        c.execute('INSERT INTO memory VALUES(?,?,?)', (ident, candidate['text'], now))
        c.execute('INSERT INTO memory_sources VALUES(?,?,?,?,?)', (ident, 'owner_auto', candidate['category'], 0, now))
        c.execute('INSERT INTO memory_auto_keys VALUES(?,?)', (candidate['key'], ident))
        status = 'created'
    c.execute('INSERT INTO memory_origins VALUES(?,?,?,?,?,?,?)',
              (ident, next_revision, session_id, turn_id, text.strip(' '), VERSION, now))
    return outcome(status, ident)
