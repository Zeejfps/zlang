namespace LexerModule.TokenReaders;

internal sealed class EndOfFileTokenReader : ITokenReader
{
    private readonly Lexer _lexer;
    
    public EndOfFileTokenReader(Lexer lexer)
    {
        _lexer = lexer;
    }
    
    public bool TryStartReading()
    {
        var lexer = _lexer;
        var nextChar = lexer.PeekChar();
        if (nextChar == -1)
        {
            return true;
        }

        return false;
    }

    public Token FinishReading()
    {
        var lexer = _lexer;
        var token = lexer.CreateToken(TokenKind.EOF);
        lexer.SkipChar();
        return token;
    }
}