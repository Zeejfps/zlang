namespace LexerModule.TokenReaders;

public sealed class DirectiveTokenReader : ITokenReader
{
    private readonly Lexer _lexer;

    public DirectiveTokenReader(Lexer lexer)
    {
        _lexer = lexer;
    }

    public bool TryStartReading()
    {
        if (_lexer.PeekChar() == '#')
        {
            _lexer.ReadChar();
            return true;
        }

        return false;
    }

    public Token FinishReading()
    {
        var nextChar = _lexer.PeekChar();
        while (nextChar != ' ' && nextChar > -1)
        {
            _lexer.ReadChar();
            nextChar = _lexer.PeekChar();
        }
        
        TokenKind tokenKind;
        if (_lexer.Lexeme is "#metadata")
        {
            tokenKind = TokenKind.DirectiveMetadata;    
        }
        else
        {
            throw new Exception($"Unknown directive: {_lexer.Lexeme}");   
        }
        
        _lexer.SkipChar();
        return _lexer.CreateToken(tokenKind);       
    }
}