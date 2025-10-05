namespace LexerModule;

public sealed class Lexer : IDisposable
{
    public Span<char> Lexeme => _buffer.AsSpan(0, _writeHead);

    private int Line { get; set; } = 1;
    private int Column { get; set; } = 1;
    private int LastChar { get; set; }
    
    public int TokenCount => _tokens.Count;

    private readonly TextReader _reader;
    private readonly char[] _buffer = new char[1024];
    private int _writeHead = 0;
    private readonly Queue<Token> _tokens = new();

    public Lexer(TextReader reader)
    {
        _reader = reader;
    }
    
    public void Dispose()
    {
        _reader.Dispose();
    }
    
    public void EnqueueToken(TokenKind kind)
    {
        var token = new Token(kind, Lexeme.ToString(), Line, Column);
        Column += _writeHead;
        _writeHead = 0;
        _tokens.Enqueue(token);
    }

    public bool TryDequeueToken(out Token token)
    {
        return _tokens.TryDequeue(out token);
    }

    public int PeekChar()
    {
        return _reader.Peek();
    }

    public void ReadChar()
    {
        LastChar = _reader.Read();
        _buffer[_writeHead] = (char)LastChar;
        _writeHead++;
        if (LastChar == '\n')
        {
            Line++;
            Column = 1;
        }
    }

    public void SkipChar()
    {
        LastChar = _reader.Read();
        Column++;
        if (LastChar == '\n')
        {
            Line++;
            Column = 1;
        } 
    }
    
    public static IEnumerable<Token> Tokenize(TextReader reader)
    {
        return new TokenEnumerable(reader);
    }
}