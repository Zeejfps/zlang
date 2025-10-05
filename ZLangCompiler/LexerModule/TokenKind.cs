namespace LexerModule;

public enum TokenKind
{
    Identifier,
    
    // Keywords
    KeywordModule,
    KeywordStruct,
    
    // Symbols
    SymbolEquals,
    SymbolDot,
    SymbolLessThan,
    SymbolGreaterThan,
    SymbolSemicolon,
    
    Eof,
}