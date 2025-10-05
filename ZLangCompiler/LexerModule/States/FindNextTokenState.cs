namespace LexerModule.States;

public sealed class FindNextTokenState : ILexerState
{
    private readonly LexerStates _lexerStates;

    public FindNextTokenState(LexerStates lexerStates)
    {
        _lexerStates = lexerStates;
    }

    public ILexerState Update(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (nextChar == -1)
        {
            return _lexerStates.EndOfFileState;
        }
        
        if (nextChar == '=')
        {
            return _lexerStates.ReadSymbolTokenState;
        }

        if (nextChar == '.')
        {
            return _lexerStates.ReadSymbolTokenState;
        }

        if (char.IsLetter((char)nextChar))
        {
            return _lexerStates.ReadIdentTokenState;
        }

        lexer.SkipChar();
        return this;
    }
}