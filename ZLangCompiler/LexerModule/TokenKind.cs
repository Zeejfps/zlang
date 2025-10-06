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
    KeywordOperator,
    KeywordUnion,
    
    // One Char Symbols
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
    SymbolStar, // *
    SymbolPlus, // +
    
    // Two Char Symbols
    SymbolReturnArrow, // ->
    SymbolPlusEquals, // +=
    
    // Literals
    LiteralInteger,
    LiteralText,
    LiteralBool,
    
    EOF,
}