using System.Collections;

namespace LexerModule;

public sealed class TokenSequence : IEnumerable<Token>, IDisposable
{
    private readonly TokenEnumerator _reader;

    public TokenSequence(TextReader reader)
    {
        _reader = new TokenEnumerator(reader);
    }
    
    public IEnumerator<Token> GetEnumerator()
    {
        return _reader;
    }

    IEnumerator IEnumerable.GetEnumerator()
    {
        return GetEnumerator();
    }

    public void Dispose()
    {
        _reader.Dispose();
    }
}