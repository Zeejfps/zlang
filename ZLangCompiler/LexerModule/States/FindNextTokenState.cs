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
            return lexer.ReadSymbolTokenState;
        }

        if (nextChar == '.')
        {
            return lexer.ReadSymbolTokenState;
        }

        if (char.IsLetter((char)nextChar))
        {
            return lexer.ReadWordTokenState;
        }

        lexer.SkipChar();
        return this;
    }
}