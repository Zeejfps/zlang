namespace LexerModule.TokenReaders;

internal sealed class OneCharSymbolTokenReader : ITokenReader
{
    private readonly Lexer _lexer;
    
    private TokenKind _tokenKind;

    public OneCharSymbolTokenReader(Lexer lexer)
    {
        _lexer = lexer;
    }

    public bool TryStartReading()
    {
        var lexer = _lexer;
        var nextChar = lexer.PeekChar();
        if (lexer.SingleCharSymbols.TryGetValue((char)nextChar, out var tokenKind))
        {
            lexer.ReadChar();
            _tokenKind = tokenKind;
            return true;
        }
        return false;
    }
    
    public Token FinishReading()
    {
        var lexer = _lexer;
        return lexer.CreateToken(_tokenKind);
    }
}