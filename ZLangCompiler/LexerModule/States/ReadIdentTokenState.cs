namespace LexerModule.States;

internal sealed class ReadIdentTokenState : ILexerState
{
    private readonly LexerStates _states;

    public ReadIdentTokenState(LexerStates states)
    {
        _states = states;
    }
    
    public ILexerState Update(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (nextChar == -1 || !lexer.IsLetterOrDigit(nextChar))
        {
            var lexeme = lexer.Lexeme.ToString();
            if (lexer.Keywords.TryGetValue(lexeme, out var tokenKind))
            {
                lexer.EmitToken(tokenKind);
            }
            else
            {
                lexer.EmitToken(TokenKind.Identifier);
            }

            return _states.FindNextTokenState;
        }
        
        lexer.ReadChar();
        return this;
    }
}