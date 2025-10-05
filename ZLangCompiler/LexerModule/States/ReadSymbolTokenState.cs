namespace LexerModule.States;

internal sealed class ReadSymbolTokenState : ILexerState
{
    private readonly LexerStates _states;

    public ReadSymbolTokenState(LexerStates states)
    {
        _states = states;
    }

    public ILexerState Update(Lexer lexer)
    {
        lexer.ReadChar();
        return _states.ProcessSymbolTokenState;
    }
}