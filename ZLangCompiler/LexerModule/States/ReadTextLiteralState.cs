namespace LexerModule.States;

internal sealed class ReadTextLiteralState : ILexerState
{
    private readonly LexerStates _states;

    public ReadTextLiteralState(LexerStates states)
    {
        _states = states;
    }

    public bool TryEnter(Lexer lexer)
    {
        if (lexer.PeekChar() == '"')
        {
            lexer.SkipChar();
            return true;
        }

        return false;
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