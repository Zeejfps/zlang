namespace LexerModule;

public enum TokenKind
{
    Identifier,
    
    // Keywords
    KeywordModule,
    KeywordStruct,
    
    // Symbols
    Equals,
    Dot,
    
    Eof,
}