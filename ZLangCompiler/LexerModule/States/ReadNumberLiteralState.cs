namespace LexerModule.States;

internal sealed class ReadNumberLiteralState : ILexerState
{
    private readonly LexerStates _states;

    public ReadNumberLiteralState(LexerStates states)
    {
        _states = states;
    }

    public bool TryEnter(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        return lexer.IsDigit(nextChar);
    }

    public ILexerState Update(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (!lexer.IsDigit(nextChar))
        {
            lexer.EmitToken(TokenKind.LiteralNumber);
            return _states.FindNextTokenState;
        }
        
        lexer.ReadChar();
        return this;
    }
}