namespace LexerModule;

public record struct Token(TokenKind Kind, string Lexeme, int Line, int Column);