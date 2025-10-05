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
        if (nextChar == '.' || nextChar == ' ' || nextChar == '=' || nextChar == -1)
        {
            return _states.ProcessIdentTokenState;
        }
        
        lexer.ReadChar();
        return this;
    }
}