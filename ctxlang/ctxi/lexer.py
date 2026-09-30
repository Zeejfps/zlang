"""Tokenizer for ctxlang."""


class CompileError(Exception):
    def __init__(self, msg, pos=None):
        super().__init__(msg)
        self.msg = msg
        self.pos = pos


class Tok:
    __slots__ = ('kind', 'val', 'line', 'col', 'nl', 'file', 'width')

    def __init__(self, kind, val, line, col, nl):
        self.kind = kind   # 'id', 'kw', 'int', 'float', 'str', 'char', 'op', 'builtin', 'eof'
        self.val = val
        self.line = line
        self.col = col
        self.nl = nl       # a newline precedes this token
        self.file = None
        self.width = 0     # in characters; a token never spans lines

    @property
    def pos(self):
        return (self.line, self.col, self.file)

    def __repr__(self):
        return f'Tok({self.kind}, {self.val!r}, {self.line}:{self.col})'


KEYWORDS = {
    'fn', 'struct', 'union', 'type', 'const', 'namespace', 'let', 'mut',
    'if', 'else', 'while', 'break', 'continue', 'match', 'return', 'defer', 'and', 'or', 'not',
    'true', 'false', 'null',
}

OPS = [
    '->', '=>', '::', '..', '==', '!=', '<=', '>=', '<<', '>>',
    '{', '}', '(', ')', '[', ']', ',', ';', ':', '.', '=', '<', '>',
    '+', '-', '*', '/', '%', '&', '|', '^', '?',
]


ESCAPES = {'n': 10, 't': 9, 'r': 13, '0': 0, '\\': 92, '"': 34, "'": 39}


# Letters and digits are ASCII only: str.isalpha and isdigit also accept other scripts.
DIGITS = '0123456789'
HEX = '0123456789abcdefABCDEF'


def is_alpha(c):
    return 'a' <= c <= 'z' or 'A' <= c <= 'Z' or c == '_'


def is_alnum(c):
    return is_alpha(c) or c in DIGITS


def show_char(c):
    """A character in a message: 'c', '\\xNN' for an ASCII control character, and the code point
    after a non-ASCII one, which may be invisible."""
    o = ord(c)
    if o < 32 or o == 127:
        return f"'\\x{o:02x}'"
    if c == '\\':
        return "'\\\\'"
    if o < 128:
        return f"'{c}'"
    return f"'{c}' (U+{o:04X})"


def lex(src, file=None, comments=None):
    """The tokens of src. If comments is a list, appends (line, col, end line, end col) of each
    comment to it."""
    toks = _lex(src, file, comments)
    for t in toks:
        t.file = file
    return toks


def _lex(src, file, comments):
    toks = []
    i, n = 0, len(src)
    line, col = 1, 1
    nl = True

    def err(msg):
        raise CompileError(msg, (line, col, file))

    def char_at(j, quote):
        """Decode one (possibly escaped) character of a literal at j -> (byte, next j)."""
        if j >= n or src[j] == '\n':
            err('unterminated literal')
        ch = src[j]
        if ch != '\\':
            if ord(ch) > 127:
                err(f'non-ASCII character {show_char(ch)} in literal; use a \\x escape')
            return ord(ch), j + 1
        if j + 1 >= n:
            err('unterminated literal')
        e = src[j + 1]
        if e in ESCAPES:
            return ESCAPES[e], j + 2
        if e == 'x':
            hx = src[j + 2:j + 4]
            if len(hx) != 2 or any(h not in HEX for h in hx):
                err('\\x needs two hex digits')
            return int(hx, 16), j + 4
        err(f'unknown escape \\{e}')

    while i < n:
        c = src[i]
        if c == '\n':
            i += 1
            line += 1
            col = 1
            nl = True
            continue
        if c in ' \t\r':
            i += 1
            col += 1
            continue
        if src.startswith('//', i):
            start = i
            while i < n and src[i] != '\n':
                i += 1
            if comments is not None:
                comments.append((line, col, line, col + i - start))
            col += i - start
            continue
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            if j < 0:
                err('unterminated block comment')
            chunk = src[i:j + 2]
            sline, scol = line, col
            line += chunk.count('\n')
            if '\n' in chunk:
                nl = True
                col = len(chunk) - chunk.rfind('\n')
            else:
                col += len(chunk)
            if comments is not None:
                comments.append((sline, scol, line, col))
            i = j + 2
            continue

        start, scol = i, col
        if is_alpha(c):
            while i < n and is_alnum(src[i]):
                i += 1
            word = src[start:i]
            kind = 'kw' if word in KEYWORDS else 'id'
            toks.append(Tok(kind, word, line, scol, nl))
        elif c in DIGITS:
            kind = 'int'
            if src.startswith(('0x', '0X'), i) or src.startswith(('0b', '0B'), i):
                base, allowed = (16, HEX) if src[i + 1] in 'xX' else (2, '01')
                i += 2
                while i < n and (src[i] in allowed or src[i] == '_'):
                    i += 1
                digits = src[start + 2:i].replace('_', '')
                if not digits:
                    err('invalid number literal')
                val = int(digits, base)
            else:
                while i < n and (src[i] in DIGITS or src[i] == '_'):
                    i += 1
                if i + 1 < n and src[i] == '.' and src[i + 1] in DIGITS:
                    kind = 'float'
                    i += 1
                    while i < n and (src[i] in DIGITS or src[i] == '_'):
                        i += 1
                if i < n and src[i] in 'eE':
                    j = i + 1
                    if j < n and src[j] in '+-':
                        j += 1
                    if j < n and src[j] in DIGITS:
                        kind = 'float'
                        i = j
                        while i < n and src[i] in DIGITS:
                            i += 1
                text = src[start:i].replace('_', '')
                val = float(text) if kind == 'float' else int(text)
            if i < n and is_alpha(src[i]):
                err('invalid number literal')
            toks.append(Tok(kind, val, line, scol, nl))
        elif c == '"':
            j, data = i + 1, bytearray()
            while True:
                if j < n and src[j] == '"':
                    break
                b, j = char_at(j, '"')
                data.append(b)
            i = j + 1
            toks.append(Tok('str', bytes(data), line, scol, nl))
        elif c == "'":
            if src.startswith("'", i + 1):          # '' and ''': a quote must be escaped
                err('a character literal holds exactly one character')
            b, j = char_at(i + 1, "'")
            if j >= n or src[j] != "'":
                err('a character literal holds exactly one character')
            i = j + 1
            toks.append(Tok('char', b, line, scol, nl))
        elif c == '@':
            i += 1
            while i < n and is_alnum(src[i]):
                i += 1
            if i == start + 1:
                err("expected a builtin name after '@'")
            toks.append(Tok('builtin', src[start + 1:i], line, scol, nl))
        else:
            for op in OPS:
                if src.startswith(op, i):
                    i += len(op)
                    toks.append(Tok('op', op, line, scol, nl))
                    break
            else:
                err(f'unexpected character {show_char(c)}')
        toks[-1].width = i - start
        col += i - start
        nl = False

    toks.append(Tok('eof', None, line, col, True))
    return toks
