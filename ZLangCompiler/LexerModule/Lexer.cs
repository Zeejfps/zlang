namespace LexerModule;

public sealed class Lexer : IDisposable
{
    public Span<char> Lexeme => _buffer.AsSpan(0, _writeHead);
    public int PrevChar { get; private set; }

    private int Line { get; set; } = 1;
    private int Column { get; set; } = 1;

    private readonly TextReader _reader;
    private readonly char[] _buffer = new char[1024];
    private readonly Queue<Token> _tokens = new();
    private readonly LexerStates _states;
    
    private ILexerState _state;
    private int _writeHead;
    private bool _disposed;

    public Lexer(TextReader reader)
    {
        _reader = reader;
        _states = new LexerStates();
        _state = _states.FindNextTokenState;
    }
    
    public void Dispose()
    {
        if (_disposed)
            return;
        
        _disposed = true;
        _reader.Dispose();
    }
    
    public void EnqueueToken(TokenKind kind)
    {
        var token = new Token(kind, Lexeme.ToString(), Line, Column);
        Column += _writeHead;
        _writeHead = 0;
        _tokens.Enqueue(token);
    }

    public Token ReadNextToken()
    {
        if (_tokens.TryDequeue(out var token))
        {
            return token;
        }
        
        if (_state == _states.EndOfFileState)
        {
            throw new Exception("Unexpected end of file");
        }
        
        _state = _state.Update(this);
        return ReadNextToken();
    }

    public bool IsSymbol(int c)
    {
        return char.IsSymbol((char)c) || c == '.' || c == ';';
    }
    
    public bool IsLetterOrDigit(int c)
    {
        return char.IsLetterOrDigit((char)c);
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
        while ((token = lexer.ReadNextToken()).Kind != TokenKind.Eof)
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