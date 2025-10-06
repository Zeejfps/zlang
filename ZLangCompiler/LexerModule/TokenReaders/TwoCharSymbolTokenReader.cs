namespace LexerModule.TokenReaders;

internal sealed class TwoCharSymbolTokenReader : ITokenReader
{
    private readonly Lexer _lexer;
    private TokenKind _tokenKind;
    
    public TwoCharSymbolTokenReader(Lexer lexer)
    {
        _lexer = lexer;
    }

    public bool TryStartReading()
    {
        var lexer = _lexer;
        var firstChar = (char)lexer.PeekChar();
        var secondChar = (char)lexer.PeekChar(1);
        if (lexer.TwoCharSymbols.TryGetValue(new TwoCharSymbol(firstChar, secondChar), out var tokenKind))
        {
            _tokenKind = tokenKind;
            return true;
        }

        return false;
    }

    public Token FinishReading()
    {
        var lexer = _lexer;
        lexer.ReadChar();
        lexer.ReadChar();
        return lexer.CreateToken(_tokenKind);
    }
}