namespace LexerModule;

public sealed class Lexer : IDisposable
{
    public ILexerState ProcessWordTokenState { get; } = new ProcessWordTokenState();
    public ILexerState FindNextTokenState { get; } = new FindNextTokenState();
    public ILexerState ReadOperatorTokenState { get; } = new ReadOperatorTokenState();
    public ILexerState ReadWordTokenState { get; } = new ReadWordTokenState();
    public ILexerState ProcessOperatorTokenState { get; } = new ProcessOperatorTokenState();
    public ILexerState EndOfFileState { get; } = new EndOfFileState();
    public ILexerState ReadDotTokenState { get; } = new  ReadDotTokenState();
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
    
    public static IEnumerable<Token> Tokenize(string empty)
    {
        var reader = new StringReader(empty);
        return Tokenize(reader);
    }

    public static IEnumerable<Token> Tokenize(TextReader reader)
    {
        var lexer = new Lexer(reader);
        var state = lexer.FindNextTokenState;
        while (state != lexer.EndOfFileState)
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

public interface ILexerState
{
    ILexerState Update(Lexer lexer);
}

public sealed class ReadWordTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (nextChar == '.' || nextChar == ' ' || nextChar == '=' || nextChar == -1)
        {
            return lexer.ProcessWordTokenState;
        }
        
        lexer.ReadChar();
        return this;
    }
}

public sealed class ProcessWordTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        var lexeme = lexer.Lexeme;
        if (lexeme is "module")
        {
            lexer.EnqueueToken(TokenKind.ModuleKeyWord);
        }
        else
        {
            lexer.EnqueueToken(TokenKind.Identifier);
        }

        return lexer.FindNextTokenState;
    }
}

public sealed class FindNextTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (nextChar == -1)
        {
            return lexer.EndOfFileState;
        }
        
        if (nextChar == '=')
        {
            return lexer.ReadOperatorTokenState;
        }

        if (nextChar == '.')
        {
            return lexer.ReadDotTokenState;
        }

        if (char.IsLetter((char)nextChar))
        {
            return lexer.ReadWordTokenState;
        }

        lexer.SkipChar();
        return this;
    }
}

public sealed class ReadOperatorTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        lexer.ReadChar();
        return lexer.ProcessOperatorTokenState;
    }
}

public sealed class ProcessOperatorTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        var lexeme = lexer.Lexeme;
        if (lexeme is "=")
        {
            lexer.EnqueueToken(TokenKind.Equals);
        }

        return lexer.FindNextTokenState;
    }
}

public sealed class EndOfFileState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        lexer.EnqueueToken(TokenKind.Eof);
        lexer.SkipChar();
        return this;
    }
}

public sealed class ReadDotTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        lexer.ReadChar();
        lexer.EnqueueToken(TokenKind.Dot);
        return lexer.FindNextTokenState;
    }
}