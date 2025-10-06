namespace LexerModule.States;

internal sealed class EndOfFileState : ILexerState
{
    public bool TryStartReading(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (nextChar == -1)
        {
            return true;
        }

        return false;
    }

    public Token FinishReading(Lexer lexer)
    {
        var token = lexer.CreateToken(TokenKind.EOF);
        lexer.SkipChar();
        return token;
    }
}