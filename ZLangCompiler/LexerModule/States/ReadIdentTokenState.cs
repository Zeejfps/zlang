namespace LexerModule.States;

public sealed class ReadIdentTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (nextChar == '.' || nextChar == ' ' || nextChar == '=' || nextChar == -1)
        {
            return lexer.ProcessIdentTokenState;
        }
        
        lexer.ReadChar();
        return this;
    }
}