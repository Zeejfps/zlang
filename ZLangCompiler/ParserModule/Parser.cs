using LexerModule;
using ParserModule.Nodes;

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

public sealed class Parser
{
    public static Ast Parse(IEnumerable<Token> tokens)
    {
        throw new NotImplementedException();
    }

    public static PrimaryExpressionNode ParsePrimaryExpression(TokenReader tokenReader)
    {
        var token = tokenReader.Read();
        if (token.Kind == TokenKind.LiteralInteger)
        {
            return new LiteralIntegerExpression(token);
        }

        throw new Exception("Invalid token: " + token + "");
    }
}