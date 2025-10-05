namespace LexerModule.States;

internal sealed class EndOfFileState : ILexerState
{
    public bool CanEnter(Lexer lexer)
    {
        return lexer.PeekChar() == -1;
    }

    public void Enter(Lexer lexer)
    {
        lexer.EmitToken(TokenKind.EOF);
    }

    public ILexerState Update(Lexer lexer)
    {
        return this;
    }
}