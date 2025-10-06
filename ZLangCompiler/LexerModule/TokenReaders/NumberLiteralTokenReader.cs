namespace LexerModule.TokenReaders;

internal sealed class NumberLiteralTokenReader : ITokenReader
{
    private readonly Lexer _lexer;

    public NumberLiteralTokenReader(Lexer lexer)
    {
        _lexer = lexer;
    }

    public bool TryStartReading()
    {
        var lexer = _lexer;
        var nextChar = lexer.PeekChar();
        return lexer.IsDigit(nextChar);
    }

    public Token FinishReading()
    {
        var lexer = _lexer;
        var nextChar = lexer.PeekChar();
        while (nextChar != -1 && lexer.IsDigit(nextChar))
        {
            lexer.ReadChar();
            nextChar = lexer.PeekChar();
        }
        return lexer.CreateToken(TokenKind.LiteralInteger);
    }
}