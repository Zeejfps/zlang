namespace LexerModule.States;

internal sealed class FindNextTokenState : ILexerState
{
    private readonly LexerStates _lexerStates;

    public FindNextTokenState(LexerStates lexerStates)
    {
        _lexerStates = lexerStates;
    }

    public bool TryEnter(Lexer lexer)
    {
        return false;
    }

    public ILexerState Update(Lexer lexer)
    {
        foreach (var state in _lexerStates)
        {
            if (state.TryEnter(lexer))
            {
                return state;
            }
        }
        lexer.SkipChar();
        return this;
        
        var nextChar = lexer.PeekChar();
        if (nextChar == -1)
        {
            lexer.EmitToken(TokenKind.EOF);
            return _lexerStates.EndOfFileState;
        }

        if (nextChar == '"')
        {
            return _lexerStates.ReadTextLiteralState;
        }
        
        if (lexer.IsSymbol(nextChar))
        {
            return _lexerStates.ReadSymbolTokenState;
        }

        if (lexer.IsLetter(nextChar))
        {
            return _lexerStates.ReadIdentTokenState;
        }

        if (lexer.IsDigit(nextChar))
        {
            return _lexerStates.ReadNumberLiteralState;
        }

        lexer.SkipChar();
        return this;
    }
}