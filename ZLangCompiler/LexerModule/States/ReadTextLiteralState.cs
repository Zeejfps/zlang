namespace LexerModule.States;

internal sealed class ReadTextLiteralState : ILexerState
{
    private readonly LexerStates _states;

    public ReadTextLiteralState(LexerStates states)
    {
        _states = states;
    }

    public bool TryStartReading(Lexer lexer)
    {
        if (lexer.PeekChar() == '"')
        {
            lexer.SkipChar();
            return true;
        }

        return false;
    }

    public Token FinishReading(Lexer lexer)
    {
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