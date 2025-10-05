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
        var lexeme = lexer.Lexeme;
        if (lexer.Symbols.TryGetValue(lexeme[0], out var tokenKind))
        {
            lexer.EmitToken(tokenKind);
        }
        return _states.FindNextTokenState;
    }
}