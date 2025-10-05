namespace LexerModule;

public record struct Token(TokenKind Kind, string Lexeme, int Line, int Column)
{
    public override string ToString()
    {
        return $"[{Kind} '{Lexeme}' {Line}:{Column}]";
    }
}