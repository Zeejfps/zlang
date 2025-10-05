namespace LexerModule;

public sealed class Lexer : IDisposable
{
    public Span<char> Lexeme => _buffer.AsSpan(0, _writeHead);
    public int TokenCount => _tokens.Count;

    private int Line { get; set; } = 1;
    private int Column { get; set; } = 1;
    private int LastChar { get; set; }

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

    public bool TryDequeueToken(out Token token)
    {
        return _tokens.TryDequeue(out token);
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
    
    public static TokenStream Tokenize(TextReader reader)
    {
        var lexer = new Lexer(reader);
        return new TokenStream(lexer);
    }
}