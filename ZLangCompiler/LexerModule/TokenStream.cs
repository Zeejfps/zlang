using System.Collections;

namespace LexerModule;

public sealed class TokenStream : IEnumerable<Token>, IDisposable
{
    private readonly Lexer _lexer;

    public TokenStream(Lexer lexer)
    {
        _lexer = lexer;
    }
    
    public IEnumerator<Token> GetEnumerator()
    {
        Token token;
        while ((token = _lexer.ReadNextToken()).Kind != TokenKind.Eof)
        {
            yield return token;
        }
        yield return token;
    }

    IEnumerator IEnumerable.GetEnumerator()
    {
        return GetEnumerator();
    }

    public void Dispose()
    {
        _lexer.Dispose();
    }
}