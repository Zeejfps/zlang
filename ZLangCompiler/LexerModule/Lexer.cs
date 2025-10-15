using LexerModule.TokenReaders;

namespace LexerModule;

public sealed class Lexer : IDisposable
{
    private const int MaxLookAhead = 2;
    
    public Span<char> Lexeme => _buffer.AsSpan(0, _writeHead);
    public Dictionary<char, TokenKind> SingleCharSymbols { get; } = new()
    {
        {'=', TokenKind.SymbolEquals},
        {'.', TokenKind.SymbolDot},
        {',', TokenKind.SymbolComma},
        {'<', TokenKind.SymbolLessThan},
        {'>', TokenKind.SymbolGreaterThan},
        {':', TokenKind.SymbolColon},
        {'(', TokenKind.SymbolLeftParen},
        {')', TokenKind.SymbolRightParen},
        {';', TokenKind.SymbolSemicolon},
        {'{', TokenKind.SymbolLeftCurlyBrace},
        {'}', TokenKind.SymbolRightCurlyBrace},
        {'[', TokenKind.SymbolLeftSquareBracket},
        {']', TokenKind.SymbolRightSquareBracket},
        {'+', TokenKind.SymbolPlus},
        {'-', TokenKind.SymbolMinus},
        {'*', TokenKind.SymbolStar},
        {'/', TokenKind.SymbolForwardSlash},
        {'!', TokenKind.SymbolExclamation},
    };
    
    public Dictionary<TwoCharSymbol, TokenKind> TwoCharSymbols { get; } = new()
    {
        {"->", TokenKind.SymbolReturnArrow},
        {"+=", TokenKind.SymbolPlusEquals},
        {"==", TokenKind.SymbolEqualsEquals},
        {"!=", TokenKind.SymbolNotEquals},
        {">=", TokenKind.SymbolGreaterThanEquals},
        {"<=", TokenKind.SymbolLessThanEquals},
        {"++", TokenKind.SymbolPlusPlus},
        {"--", TokenKind.SymbolMinsMinus},
    };
    
    public Dictionary<string, TokenKind> Keywords { get; } = new()
    {
        {"module",  TokenKind.KeywordModule},
        {"struct",  TokenKind.KeywordStruct},
        {"var",  TokenKind.KeywordVar},
        {"func",  TokenKind.KeywordFunc},
        {"defer",  TokenKind.KeywordDefer},
        {"union",  TokenKind.KeywordUnion},
        {"operator",  TokenKind.KeywordOperator},
        {"return",  TokenKind.KeywordReturn},
        {"if",  TokenKind.KeywordIf},
        {"else",  TokenKind.KeywordElse},
        {"for",  TokenKind.KeywordFor},
        {"while",  TokenKind.KeywordWhile},
        {"as",  TokenKind.KeywordAs},
        {"import",  TokenKind.KeywordImport},
    };
    
    private int Line { get; set; } = 1;
    private int Column { get; set; } = 1;

    private readonly TextReader _reader;
    private readonly char[] _buffer = new char[1024];
    private readonly ITokenReader[] _tokenReaders;
    private readonly int[] _lookAheadBuffer = new int[MaxLookAhead * 2];
    private int _peekHead;
    private int _readHead;
    
    private int _writeHead;
    private bool _disposed;

    public Lexer(TextReader reader)
    {
        _reader = reader;
        _tokenReaders = [
            new IdentTokenReader(this),
            new TwoCharSymbolTokenReader(this),
            new OneCharSymbolTokenReader(this),
            new NumberLiteralTokenReader(this),
            new TextLiteralTokenReader(this),
            new EndOfFileTokenReader(this)
        ];
    }
    
    public void Dispose()
    {
        if (_disposed)
            return;
        
        _disposed = true;
        _reader.Dispose();
    }

    public Token ReadNextToken()
    {
        while (IsComment())
        {
            SkipLine();
        }
        
        var tokenReader = StartReading();
        while (tokenReader == null)
        {
            SkipChar();
            tokenReader = StartReading();
        }
        return FinishReading(tokenReader);
    }

    public Token CreateToken(TokenKind tokenKind)
    {
        var lexeme = Lexeme.ToString();
        return new Token(tokenKind, lexeme, Line, Column);
    }

    private bool IsComment()
    {
        var nextChar = PeekChar();
        if (nextChar == '/')
        {
            nextChar = PeekChar(1);
            if (nextChar == '/')
            {
                return true;
            }
        }
        return false;
    }

    private void SkipLine()
    {
        int c;
        while ((c = PeekChar()) != -1 && c != '\n')
        {
            SkipChar();
        }
        SkipChar();
    }
    
    private ITokenReader? StartReading()
    {
        foreach (var state in _tokenReaders)
        {
            if (state.TryStartReading())
            {
                return state;
            }
        }

        return null;
    }

    private Token FinishReading(ITokenReader tokenReader)
    {
        var token = tokenReader.FinishReading();
        Column += _writeHead;
        _writeHead = 0;
        return token;
    }

    public bool IsSymbol(int charCode)
    {
        var c = (char)charCode;
        foreach (var symbol in SingleCharSymbols.Keys)
        {
            if (c == symbol)
                return true;
        }

        return false;
    }
    
    public bool IsLetter(int nextChar)
    {
        return char.IsLetter((char)nextChar);
    }
    
    public bool IsLetterOrDigit(int c)
    {
        return char.IsLetterOrDigit((char)c);
    }
    
    public bool IsDigit(int nextChar)
    {
        return char.IsDigit((char)nextChar);
    }

    public int PeekChar(int offset = 0)
    {
        int readCount;
        if (_peekHead < _readHead)
        {
            readCount = _lookAheadBuffer.Length - _readHead - 1 + _peekHead;
        }
        else if (_peekHead > _readHead)
        {
            readCount = _peekHead - _readHead;
        }
        else
        {
            readCount = 0;
        }
        
        for (var i = readCount; i < offset + 1; i++)
        {
            _lookAheadBuffer[_peekHead] = _reader.Read();
            _peekHead++;
            if (_peekHead >= _lookAheadBuffer.Length)
            {
                _peekHead = 0;
            }
        }

        var peekIndex = (_readHead + offset) % _lookAheadBuffer.Length;
        var c = _lookAheadBuffer[peekIndex];
        //Console.WriteLine($"PeekChar: '{c}' offset: {offset}");
        return c;
    }

    public void ReadChar()
    {
        char c;
        if (_readHead == _peekHead)
        {
            c = (char)_reader.Read();
        }
        else
        {
            c = (char)_lookAheadBuffer[_readHead];
            _readHead++;
            if (_readHead >= _lookAheadBuffer.Length)
            {
                _readHead = 0;
            }
        }
        
        _buffer[_writeHead] = c;
        _writeHead++;
        if (c == '\n')
        {
            Line++;
            Column = 1;
        }
        //Console.WriteLine("Read char: " + c);
    }

    public int SkipChar()
    {
        int c;
        if (_readHead == _peekHead)
        {
            c = _reader.Read();
        }
        else
        {
            c = _lookAheadBuffer[_readHead];
            _readHead++;
            if (_readHead >= _lookAheadBuffer.Length)
            {
                _readHead = 0;
            }
        }

        if (c != -1)
        {
            Column++;
        }
        
        if (c == '\n')
        {
            Line++;
            Column = 1;
        } 
        
        //Console.WriteLine($"Skipping: {c}");
        return c;
    }
    
    public static IEnumerable<Token> Tokenize(TextReader reader)
    {
        Token token;
        using var lexer = new Lexer(reader);
        while ((token = lexer.ReadNextToken()).Kind != TokenKind.EOF)
        {
            yield return token;
        }
        yield return token;
    }
    
    public static IEnumerable<Token> Tokenize(string input)
    {
        using var reader = new StringReader(input);
        foreach (var token in Tokenize(reader))
            yield return token;
    }
    
    public static IEnumerable<Token> Tokenize(Stream stream)
    {
        using var reader = new StreamReader(stream);
        foreach (var token in Tokenize(reader))
            yield return token;
    }
}