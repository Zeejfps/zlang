namespace LexerModule.States;

internal sealed class NumberLiteralTokenReader : ITokenReader
{
    private readonly Lexer _states;

    public NumberLiteralTokenReader(Lexer states)
    {
        _states = states;
    }

    public bool TryStartReading(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        return lexer.IsDigit(nextChar);
    }

    public Token FinishReading(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        while (nextChar != -1 && lexer.IsDigit(nextChar))
        {
            lexer.ReadChar();
            nextChar = lexer.PeekChar();
        }
        return lexer.CreateToken(TokenKind.LiteralNumber);
    }
}