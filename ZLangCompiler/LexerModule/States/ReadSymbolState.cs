namespace LexerModule.States;

internal sealed class ReadSymbolState : ILexerState
{
    private readonly LexerStates _states;

    public ReadSymbolState(LexerStates states)
    {
        _states = states;
    }

    public bool TryEnter(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        return lexer.IsSymbol(nextChar);
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