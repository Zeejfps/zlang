"""Tokenizer for ctxlang."""


class CompileError(Exception):
    def __init__(self, msg, pos=None):
        super().__init__(msg)
        self.msg = msg
        self.pos = pos


class Tok:
    __slots__ = ('kind', 'val', 'line', 'col', 'nl', 'ws')

    def __init__(self, kind, val, line, col, nl, ws):
        self.kind = kind   # 'id', 'kw', 'int', 'float', 'op', 'builtin', 'eof'
        self.val = val
        self.line = line
        self.col = col
        self.nl = nl       # a newline precedes this token
        self.ws = ws       # whitespace (or a newline) precedes this token

    @property
    def pos(self):
        return (self.line, self.col)

    def __repr__(self):
        return f'Tok({self.kind}, {self.val!r}, {self.line}:{self.col})'


KEYWORDS = {
    'fn', 'struct', 'union', 'type', 'const', 'namespace', 'let', 'mut',
    'if', 'else', 'while', 'match', 'return', 'and', 'or', 'not',
    'true', 'false', 'null',
}

OPS = [
    '->', '=>', '::', '..', '==', '!=', '<=', '>=',
    '{', '}', '(', ')', '[', ']', ',', ';', ':', '.', '=', '<', '>',
    '+', '-', '*', '/', '%', '&', '?',
]


def lex(src):
    toks = []
    i, n = 0, len(src)
    line, col = 1, 1
    nl, ws = True, True

    def err(msg):
        raise CompileError(msg, (line, col))

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
