namespace LexerModule;

public enum TokenKind
{
    Identifier,
    
    // Keywords
    KeywordModule,
    KeywordStruct,
    KeywordVar,
    
    // Symbols
    SymbolEquals,
    SymbolDot,
    SymbolLessThan,
    SymbolGreaterThan,
    SymbolSemicolon,
    SymbolColon,
    SymbolLeftParen,
    SymbolRightParen,
    
    // Literals
    LiteralNumber,
    LiteralText,
    
    EOF,
}