namespace LexerModule.States;

internal sealed class ProcessSymbolTokenState : ILexerState
{
    private readonly Dictionary<string, TokenKind> _symbols = new()
    {
        {"=", TokenKind.Equals},
        {".",  TokenKind.Dot},
    };
    
    private readonly LexerStates _states;

    public ProcessSymbolTokenState(LexerStates states)
    {
        _states = states;
    }
    
    public ILexerState Update(Lexer lexer)
    {
        var lexeme = lexer.Lexeme.ToString();
        if (_symbols.TryGetValue(lexeme, out var tokenKind))
        {
            lexer.EnqueueToken(tokenKind);
        }
        return _states.FindNextTokenState;
    }
}