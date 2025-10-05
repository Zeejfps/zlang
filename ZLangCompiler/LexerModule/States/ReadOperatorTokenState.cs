namespace LexerModule.States;

internal sealed class ReadOperatorTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        lexer.ReadChar();
        return lexer.ProcessOperatorTokenState;
    }
}