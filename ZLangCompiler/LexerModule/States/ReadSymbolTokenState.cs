namespace LexerModule.States;

internal sealed class ReadSymbolTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        lexer.ReadChar();
        return lexer.ProcessOperatorTokenState;
    }
}