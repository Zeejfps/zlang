namespace LexerModule.TokenReaders;

internal sealed class IdentTokenReader : ITokenReader
{
    private readonly Lexer _lexer;

    public IdentTokenReader(Lexer lexer)
    {
        _lexer = lexer;
    }

    public bool TryStartReading()
    {
        var lexer = _lexer;
        var nextChar = lexer.PeekChar();
        //Console.WriteLine($"{(char)nextChar} isLetter: {lexer.IsLetter(nextChar)}");
        return lexer.IsLetter(nextChar);
    }

    public Token FinishReading()
    {
        var lexer = _lexer;
        var nextChar = lexer.PeekChar();
        while (nextChar != -1 && (lexer.IsLetterOrDigit(nextChar) || nextChar == '_'))
        {
            lexer.ReadChar();
            nextChar = lexer.PeekChar();
        }
        
        var lexeme = lexer.Lexeme.ToString();
        if (lexeme == "true" || lexeme == "false")
        {
            return lexer.CreateToken(TokenKind.LiteralBool);
        }
        
        //Console.WriteLine(lexeme);
        if (lexer.Keywords.TryGetValue(lexeme, out var tokenKind))
        {
            return lexer.CreateToken(tokenKind);
        }
        
        return lexer.CreateToken(TokenKind.Identifier);
    }
}