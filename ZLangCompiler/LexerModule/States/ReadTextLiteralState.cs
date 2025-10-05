namespace LexerModule.States;

internal sealed class ReadTextLiteralState : ILexerState
{
    private readonly LexerStates _states;

    public ReadTextLiteralState(LexerStates states)
    {
        _states = states;
    }

    public bool CanEnter(Lexer lexer)
    {
        return lexer.PeekChar() == '"';
    }

    public void Enter(Lexer lexer)
    {
        lexer.SkipChar();
    }

    public ILexerState Update(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (nextChar == '"')
        {
            lexer.EmitToken(TokenKind.LiteralText);
            lexer.SkipChar();
            return _states.FindNextTokenState;
        }
        lexer.ReadChar();
        return this;
    }
}