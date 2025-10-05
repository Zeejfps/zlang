namespace LexerModule.States;

internal sealed class ReadDotTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        lexer.ReadChar();
        lexer.EnqueueToken(TokenKind.Dot);
        return lexer.FindNextTokenState;
    }
}