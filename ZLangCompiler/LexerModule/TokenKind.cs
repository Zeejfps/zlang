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
    KeywordReturn,
    
    // One Char Symbols
    SymbolEquals, // =
    SymbolDot, // .
    SymbolComma, // ,
    SymbolLessThan,  // <
    SymbolGreaterThan, // >
    SymbolSemicolon, // ;
    SymbolColon, // :
    SymbolLeftParen,  // (
    SymbolRightParen, // )
    SymbolLeftCurlyBrace,  // {
    SymbolRightCurlyBrace, // }
    SymbolLeftSquareBracket,  // [
    SymbolRightSquareBracket, // ]
    SymbolStar,         // *
    SymbolPlus,         // +
    SymbolMinus,        // -
    SymbolForwardSlash, // /
    SymbolExclamation,  // !
    
    // Two Char Symbols
    SymbolReturnArrow, // ->
    SymbolPlusEquals, // +=
    SymbolEqualsEquals, // ==
    SymbolNotEquals, // ==
    SymbolGreaterThanEquals, // >=
    SymbolLessThanEquals, // <=
    
    // Literals
    LiteralInteger,
    LiteralText,
    LiteralBool,
    
    EOF,
}