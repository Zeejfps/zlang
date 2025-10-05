namespace LexerModule.States;

internal sealed class ReadNextState : ILexerState
{
    private readonly LexerStates _lexerStates;

    public ReadNextState(LexerStates lexerStates)
    {
        _lexerStates = lexerStates;
    }

    public bool TryEnter(Lexer lexer)
    {
        return false;
    }

    public ILexerState Update(Lexer lexer)
    {
        foreach (var state in _lexerStates)
        {
            if (state.TryEnter(lexer))
            {
                return state;
            }
        }
        lexer.SkipChar();
        return this;
    }
}