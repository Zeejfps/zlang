namespace LexerModule.States;

public sealed class FindNextTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (nextChar == -1)
        {
            return lexer.EndOfFileState;
        }
        
        if (nextChar == '=')
        {
            return lexer.ReadOperatorTokenState;
        }

        if (nextChar == '.')
        {
            return lexer.ReadDotTokenState;
        }

        if (char.IsLetter((char)nextChar))
        {
            return lexer.ReadWordTokenState;
        }

        lexer.SkipChar();
        return this;
    }
}