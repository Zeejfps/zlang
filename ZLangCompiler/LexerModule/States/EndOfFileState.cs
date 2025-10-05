namespace LexerModule.States;

internal sealed class EndOfFileState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        return this;
    }
}