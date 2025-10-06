using LexerModule;

namespace ParserModule;

public sealed class TokenReader : IDisposable
{
    private readonly LinkedList<Token> _lookAheadBuffer = new();
    private readonly IEnumerator<Token> _tokensEnumerator;
    
    public TokenReader(IEnumerable<Token> tokens)
    {
        _tokensEnumerator = tokens.GetEnumerator();
    }
    
    public Token Peek(int offset = 0)
    {
        if (_lookAheadBuffer.Count < offset + 1)
        {
            _tokensEnumerator.MoveNext();
            var token = _tokensEnumerator.Current;
            _lookAheadBuffer.AddLast(token);
        }

        if (offset == 0)
        {
            return _lookAheadBuffer.First!.Value;       
        }
        return _lookAheadBuffer.ElementAt(offset);
    }

    public Token Read()
    {
        if (_lookAheadBuffer.Count == 0)
        {
            _tokensEnumerator.MoveNext();
            var token = _tokensEnumerator.Current;
            return token;
        }
        var first = _lookAheadBuffer.First!;
        _lookAheadBuffer.RemoveFirst();
        return first.Value;
    }

    public void Dispose()
    {
        _tokensEnumerator.Dispose();
    }
}