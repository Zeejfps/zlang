namespace LexerModule;

public enum TokenKind
{
    Identifier,
    
    // Keywords
    KeywordModule,
    KeywordStruct,
    KeywordVar,
    KeywordFunc,
    
    // Symbols
    SymbolEquals,
    SymbolDot,
    SymbolLessThan,
    SymbolGreaterThan,
    SymbolSemicolon,
    SymbolColon,
    SymbolLeftParen,
    SymbolRightParen,
    SymbolLeftBrace,
    SymbolRightBrace,
    
    // Literals
    LiteralNumber,
    LiteralText,
    
    EOF,
}