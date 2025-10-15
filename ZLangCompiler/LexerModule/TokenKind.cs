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
    KeywordIf,
    KeywordElse,
    KeywordFor,
    KeywordWhile,
    KeywordAs,
    KeywordImport,
    KeywordExtern,
    KeywordFrom,
    
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
    SymbolPlusPlus, // ++
    SymbolMinsMinus, // --
    
    // Literals
    LiteralInteger,
    LiteralText,
    LiteralBool,
    
    EOF,
}