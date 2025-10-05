namespace LexerModule.States;

internal sealed class EndOfFileState : ILexerState
{
    public bool TryEnter(Lexer lexer)
    {
        if (lexer.PeekChar() == -1)
        {
            lexer.EmitToken(TokenKind.EOF);
            return true;
        }

        return false;
    }

    public ILexerState Update(Lexer lexer)
    {
        return this;
    }
}