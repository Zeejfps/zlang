namespace LexerModule.States;

internal sealed class ReadSymbolState : ILexerState
{
    private readonly Lexer _states;
    
    private TokenKind _tokenKind;

    public ReadSymbolState(Lexer states)
    {
        _states = states;
    }

    public bool TryStartReading(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (lexer.Symbols.TryGetValue((char)nextChar, out var tokenKind))
        {
            lexer.ReadChar();
            _tokenKind = tokenKind;
            return true;
        }
        return false;
    }
    
    public Token FinishReading(Lexer lexer)
    {
        return lexer.CreateToken(_tokenKind);
    }
}