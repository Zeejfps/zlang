namespace LexerModule;

public sealed class Lexer : IDisposable
{
    public Span<char> Lexeme => _buffer.AsSpan(0, _writeHead);

    public int Line { get; private set; } = 1;
    public int Column { get; private set; } = 1;
    public int LastChar { get; private set; }

    private readonly TextReader _reader;
    private readonly char[] _buffer = new char[1024];
    private int _writeHead = 0;
    private readonly Queue<Token> _tokens = new();

    public Lexer(TextReader reader)
    {
        _reader = reader;
    }
    
    public void EnqueueToken(TokenKind kind)
    {
        var token = new Token(kind, Lexeme.ToString(), Line, Column);
        Column += _writeHead;
        _writeHead = 0;
        _tokens.Enqueue(token);
    }

    private bool TryDequeueToken(out Token token)
    {
        return _tokens.TryDequeue(out token);
    }

    public static IEnumerable<Token> Tokenize(TextReader reader)
    {
        var lexer = new Lexer(reader);
        var lexerStates = new LexerStates();
        var state = lexerStates.FindNextTokenState;
        while (state != lexerStates.EndOfFileState)
        {
            state = state.Update(lexer);
            while (lexer.TryDequeueToken(out var token))
                yield return token;
        }
        state.Update(lexer);
        while (lexer.TryDequeueToken(out var token))
            yield return token;
        
        lexer.Dispose();
    }

    public void Dispose()
    {
        _reader.Dispose();
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
}