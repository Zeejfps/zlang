namespace LexerModule.States;

internal sealed class ProcessSymbolTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        var lexeme = lexer.Lexeme;
        if (lexeme is "=")
        {
            lexer.EnqueueToken(TokenKind.Equals);
        }

        return lexer.FindNextTokenState;
    }
}