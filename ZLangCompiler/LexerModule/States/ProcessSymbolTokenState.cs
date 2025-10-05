namespace LexerModule.States;

internal sealed class ProcessSymbolTokenState : ILexerState
{
    private readonly LexerStates _states;

    public ProcessSymbolTokenState(LexerStates states)
    {
        _states = states;
    }
    
    public ILexerState Update(Lexer lexer)
    {
        var lexeme = lexer.Lexeme;
        if (lexer.Symbols.TryGetValue(lexeme[0], out var tokenKind))
        {
            lexer.EnqueueToken(tokenKind);
        }
        return _states.FindNextTokenState;
    }
}