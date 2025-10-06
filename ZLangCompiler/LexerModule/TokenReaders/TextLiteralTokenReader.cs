namespace LexerModule.TokenReaders;

internal sealed class TextLiteralTokenReader : ITokenReader
{
    private readonly Lexer _lexer;

    public TextLiteralTokenReader(Lexer lexer)
    {
        _lexer = lexer;
    }

    public bool TryStartReading()
    {
        var lexer = _lexer;
        if (lexer.PeekChar() == '"')
        {
            lexer.SkipChar();
            return true;
        }

        return false;
    }

    public Token FinishReading()
    {
        var lexer = _lexer;
        var nextChar = lexer.PeekChar();
        while (nextChar != -1 && nextChar != '"')
        {
            lexer.ReadChar();
            nextChar = lexer.PeekChar();
        }

        var token = lexer.CreateToken(TokenKind.LiteralText);
        if (nextChar == '"')
        {
            lexer.SkipChar();
        }

        return token;
    }
}