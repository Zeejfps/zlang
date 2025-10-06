namespace LexerModule.States;

internal sealed class ReadNumberLiteralState : ILexerState
{
    private readonly LexerStates _states;

    public ReadNumberLiteralState(LexerStates states)
    {
        _states = states;
    }

    public bool TryStartReading(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        return lexer.IsDigit(nextChar);
    }

    public Token FinishReading(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        while (nextChar != -1 && lexer.IsDigit(nextChar))
        {
            lexer.ReadChar();
            nextChar = lexer.PeekChar();
        }
        return lexer.CreateToken(TokenKind.LiteralNumber);
    }
}