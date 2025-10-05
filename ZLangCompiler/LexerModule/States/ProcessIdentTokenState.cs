namespace LexerModule.States;

internal sealed class ProcessIdentTokenState : ILexerState
{
    private readonly Dictionary<string, TokenKind> _keywords = new()
    {
        {"module",  TokenKind.KeywordModule},
        {"struct",  TokenKind.KeywordStruct},
        {"var",  TokenKind.KeywordVar},
    };
    
    private readonly LexerStates _states;

    public ProcessIdentTokenState(LexerStates states)
    {
        _states = states;
    }

    public ILexerState Update(Lexer lexer)
    {
        var lexeme = lexer.Lexeme.ToString();
        if (_keywords.TryGetValue(lexeme, out var tokenKind))
        {
            lexer.EmitToken(tokenKind);
        }
        else
        {
            lexer.EmitToken(TokenKind.Identifier);
        }

        return _states.FindNextTokenState;
    }
}