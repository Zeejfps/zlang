using System.Collections;

namespace LexerModule;

internal sealed class TokenEnumerable : IEnumerable<Token>
{
    private readonly TextReader _reader;

    public TokenEnumerable(TextReader reader)
    {
        _reader = reader;
    }
    
    public IEnumerator<Token> GetEnumerator()
    {
        return new TokenEnumerator(_reader);
    }

    IEnumerator IEnumerable.GetEnumerator()
    {
        return GetEnumerator();
    }
}