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
        lexer.ReadChar();
    }

    public ILexerState Update(Lexer lexer)
    {
        throw new NotImplementedException();
    }
}