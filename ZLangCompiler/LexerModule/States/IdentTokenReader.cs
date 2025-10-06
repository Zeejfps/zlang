namespace LexerModule.States;

internal sealed class IdentTokenReader : ITokenReader
{
    private readonly Lexer _states;

    public IdentTokenReader(Lexer states)
    {
        _states = states;
    }

    public bool TryStartReading(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        //Console.WriteLine($"{(char)nextChar} isLetter: {lexer.IsLetter(nextChar)}");
        return lexer.IsLetter(nextChar);
    }

    public Token FinishReading(Lexer lexer)
    {
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