namespace LexerModule.States;

public sealed class ProcessIdentTokenState : ILexerState
{
    private readonly Dictionary<string, TokenKind> _keywords = new()
    {
        {"module",  TokenKind.KeywordModule},
    };
    
    public ILexerState Update(Lexer lexer)
    {
        var lexeme = lexer.Lexeme.ToString();
        if (_keywords.TryGetValue(lexeme, out var tokenKind))
        {
            lexer.EnqueueToken(tokenKind);
        }
        else
        {
            lexer.EnqueueToken(TokenKind.Identifier);
        }

        return lexer.FindNextTokenState;
    }
}