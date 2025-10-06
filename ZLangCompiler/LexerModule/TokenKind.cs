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
    SymbolEquals, // =
    SymbolDot, // .
    SymbolComma, // ,
    SymbolLeftAngleBracket,  // <
    SymbolRightAngleBracket, // >
    SymbolSemicolon, // ;
    SymbolColon, // :
    SymbolLeftParen,  // (
    SymbolRightParen, // )
    SymbolLeftCurlyBrace,  // {
    SymbolRightCurlyBrace, // }
    SymbolLeftSquareBracket,  // [
    SymbolRightSquareBracket, // ]
    SymbolReturnArrow, // ->
    
    // Literals
    LiteralNumber,
    LiteralText,
    
    EOF,
}