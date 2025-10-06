namespace LexerModule.States;

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
        var max = 100;
        var i = 0;
        while (nextChar != -1 && lexer.IsLetterOrDigit(nextChar) && i < max)
        {
            lexer.ReadChar();
            nextChar = lexer.PeekChar();
            i++;
        }
        
        var lexeme = lexer.Lexeme.ToString();
        //Console.WriteLine(lexeme);
        if (lexer.Keywords.TryGetValue(lexeme, out var tokenKind))
        {
            return lexer.CreateToken(tokenKind);
        }
        
        return lexer.CreateToken(TokenKind.Identifier);
    }
}