"""Tokenizer for ctxlang."""


class CompileError(Exception):
    def __init__(self, msg, pos=None):
        super().__init__(msg)
        self.msg = msg
        self.pos = pos


class Tok:
    __slots__ = ('kind', 'val', 'line', 'col', 'nl', 'ws', 'file')

    def __init__(self, kind, val, line, col, nl, ws):
        self.kind = kind   # 'id', 'kw', 'int', 'float', 'op', 'builtin', 'eof'
        self.val = val
        self.line = line
        self.col = col
        self.nl = nl       # a newline precedes this token
        self.ws = ws       # whitespace (or a newline) precedes this token
        self.file = None

    @property
    def pos(self):
        return (self.line, self.col, self.file)

    def __repr__(self):
        return f'Tok({self.kind}, {self.val!r}, {self.line}:{self.col})'


KEYWORDS = {
    'fn', 'struct', 'union', 'type', 'const', 'namespace', 'let', 'mut',
    'if', 'else', 'while', 'break', 'continue', 'match', 'return', 'and', 'or', 'not',
    'true', 'false', 'null',
}

OPS = [
    '->', '=>', '::', '..', '==', '!=', '<=', '>=',
    '{', '}', '(', ')', '[', ']', ',', ';', ':', '.', '=', '<', '>',
    '+', '-', '*', '/', '%', '&', '?',
]


ESCAPES = {'n': 10, 't': 9, 'r': 13, '0': 0, '\\': 92, '"': 34, "'": 39}


def lex(src, file=None):
    toks = _lex(src, file)
    for t in toks:
        t.file = file
    return toks


def _lex(src, file):
    toks = []
    i, n = 0, len(src)
    line, col = 1, 1
    nl, ws = True, True

    def err(msg):
        raise CompileError(msg, (line, col, file))

    def char_at(j, quote):
        """Decode one (possibly escaped) character of a literal at j -> (byte, next j)."""
        if j >= n or src[j] == '\n':
            err('unterminated literal')
        ch = src[j]
        if ch != '\\':
            if ord(ch) > 127:
                err(f'non-ASCII character {ch!r} in literal; use a \\x escape')
            return ord(ch), j + 1
        if j + 1 >= n:
            err('unterminated literal')
        e = src[j + 1]
        if e in ESCAPES:
            return ESCAPES[e], j + 2
        if e == 'x':
            hx = src[j + 2:j + 4]
            if len(hx) != 2 or any(h not in '0123456789abcdefABCDEF' for h in hx):
                err('\\x needs two hex digits')
            return int(hx, 16), j + 4
        err(f'unknown escape \\{e}')

    while i < n:
        c = src[i]
        if c == '\n':
            i += 1
            line += 1
            col = 1
            nl = ws = True
            continue
        if c in ' \t\r':
            i += 1
            col += 1
            ws = True
            continue
        if src.startswith('//', i):
            while i < n and src[i] != '\n':
                i += 1
            ws = True
            continue
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            if j < 0:
                err('unterminated block comment')
            chunk = src[i:j + 2]
            line += chunk.count('\n')
            if '\n' in chunk:
                nl = True
                col = len(chunk) - chunk.rfind('\n')
            else:
                col += len(chunk)
            i = j + 2
            ws = True
            continue

        start, scol = i, col
        if c.isalpha() or c == '_':
            while i < n and (src[i].isalnum() or src[i] == '_'):
                i += 1
            word = src[start:i]
            kind = 'kw' if word in KEYWORDS else 'id'
            toks.append(Tok(kind, word, line, scol, nl, ws))
        elif c.isdigit():
            kind = 'int'
            if src.startswith(('0x', '0X'), i):
                i += 2
                while i < n and (src[i] in '0123456789abcdefABCDEF_'):
                    i += 1
                val = int(src[start + 2:i].replace('_', ''), 16)
            elif src.startswith(('0b', '0B'), i):
                i += 2
                while i < n and src[i] in '01_':
                    i += 1
                val = int(src[start + 2:i].replace('_', ''), 2)
            else:
                while i < n and (src[i].isdigit() or src[i] == '_'):
                    i += 1
                if i + 1 < n and src[i] == '.' and src[i + 1].isdigit():
                    kind = 'float'
                    i += 1
                    while i < n and (src[i].isdigit() or src[i] == '_'):
                        i += 1
                if i < n and src[i] in 'eE':
                    j = i + 1
                    if j < n and src[j] in '+-':
                        j += 1
                    if j < n and src[j].isdigit():
                        kind = 'float'
                        i = j
                        while i < n and src[i].isdigit():
                            i += 1
                text = src[start:i].replace('_', '')
                val = float(text) if kind == 'float' else int(text)
            if i < n and (src[i].isalpha() or src[i] == '_'):
                err(f'invalid number literal')
            toks.append(Tok(kind, val, line, scol, nl, ws))
        elif c == '"':
            j, data = i + 1, bytearray()
            while True:
                if j < n and src[j] == '"':
                    break
                b, j = char_at(j, '"')
                data.append(b)
            i = j + 1
            toks.append(Tok('str', bytes(data), line, scol, nl, ws))
        elif c == "'":
            b, j = char_at(i + 1, "'")
            if j >= n or src[j] != "'":
                err('a character literal holds exactly one character')
            i = j + 1
            toks.append(Tok('char', b, line, scol, nl, ws))
        elif c == '@':
            i += 1
            while i < n and (src[i].isalnum() or src[i] == '_'):
                i += 1
            if i == start + 1:
                err("expected a builtin name after '@'")
            toks.append(Tok('builtin', src[start + 1:i], line, scol, nl, ws))
        else:
            for op in OPS:
                if src.startswith(op, i):
                    i += len(op)
                    toks.append(Tok('op', op, line, scol, nl, ws))
                    break
            else:
                err(f'unexpected character {c!r}')
        col += i - start
        nl = ws = False

    toks.append(Tok('eof', None, line, col, True, True))
    return toks
