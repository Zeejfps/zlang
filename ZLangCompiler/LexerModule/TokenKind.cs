namespace LexerModule;

public enum TokenKind
{
    Identifier,
    
    // Keywords
    KeywordModule,
    KeywordStruct,
    KeywordVar,
    KeywordFunc,
    KeywordDefer,
    
    // Symbols
    SymbolEquals,
    SymbolDot,
    SymbolComma,
    SymbolLeftAngleThan,
    SymbolRightAngleThan,
    SymbolSemicolon,
    SymbolColon,
    SymbolLeftParen,
    SymbolRightParen,
    SymbolLeftCurlyBrace,
    SymbolRightCurlyBrace,
    SymbolLeftSquareBracket,
    SymbolRightSquareBracket,
    
    // Literals
    LiteralNumber,
    LiteralText,
    
    EOF,
}