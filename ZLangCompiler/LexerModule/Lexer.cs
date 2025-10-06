using LexerModule.States;

namespace LexerModule;

public sealed class Lexer : IDisposable
{
    public Span<char> Lexeme => _buffer.AsSpan(0, _writeHead);
    public int PrevChar { get; private set; }
    public Dictionary<char, TokenKind> Symbols { get; } = new()
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
        {'{', TokenKind.SymbolLeftBrace},
        {'}', TokenKind.SymbolRightBrace},
    };
    
    public Dictionary<string, TokenKind> Keywords { get; } = new()
    {
        {"module",  TokenKind.KeywordModule},
        {"struct",  TokenKind.KeywordStruct},
        {"var",  TokenKind.KeywordVar},
        {"func",  TokenKind.KeywordFunc},
        {"defer",  TokenKind.KeywordDefer},
    };
    
    private int Line { get; set; } = 1;
    private int Column { get; set; } = 1;

    private readonly TextReader _reader;
    private readonly char[] _buffer = new char[1024];
    private readonly ITokenReader[] _tokenReaders;
    
    private int _writeHead;
    private bool _disposed;

    public Lexer(TextReader reader)
    {
        _reader = reader;
        _tokenReaders = [
            new IdentTokenReader(this),
            new SymbolTokenReader(this),
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
        foreach (var symbol in Symbols.Keys)
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

    public int PeekChar()
    {
        return _reader.Peek();
    }

    public void ReadChar()
    {
        PrevChar = _reader.Read();
        _buffer[_writeHead] = (char)PrevChar;
        _writeHead++;
        if (PrevChar == '\n')
        {
            Line++;
            Column = 1;
        }
    }

    public void SkipChar()
    {
        PrevChar = _reader.Read();
        Column++;
        if (PrevChar == '\n')
        {
            Line++;
            Column = 1;
        } 
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