namespace LexerModule.States;

internal sealed class EndOfFileTokenReader : ITokenReader
{
    private readonly Lexer _states;
    
    public EndOfFileTokenReader(Lexer states)
    {
        _states = states;
    }
    
    public bool TryStartReading(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (nextChar == -1)
        {
            return true;
        }

        return false;
    }

    public Token FinishReading(Lexer lexer)
    {
        var token = lexer.CreateToken(TokenKind.EOF);
        lexer.SkipChar();
        return token;
    }
}