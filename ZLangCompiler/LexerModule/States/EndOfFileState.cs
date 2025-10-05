namespace LexerModule.States;

internal sealed class EndOfFileState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        lexer.EnqueueToken(TokenKind.Eof);
        lexer.SkipChar();
        return this;
    }
}