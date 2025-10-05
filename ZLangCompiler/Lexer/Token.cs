namespace LexerModule;

public record struct Token(TokenKind Kind, string Text, int Line, int Column)
{
}