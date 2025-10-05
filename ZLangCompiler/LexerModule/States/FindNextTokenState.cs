namespace LexerModule.States;

internal sealed class FindNextTokenState : ILexerState
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
            lexer.EnqueueToken(TokenKind.EOF);
            return _lexerStates.EndOfFileState;
        }
        
        if (lexer.IsSymbol(nextChar))
        {
            return _lexerStates.ReadSymbolTokenState;
        }

        if (lexer.IsLetter(nextChar))
        {
            return _lexerStates.ReadIdentTokenState;
        }

        lexer.SkipChar();
        return this;
    }
}