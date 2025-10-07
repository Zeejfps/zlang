using LexerModule;

namespace ParserModule;

public class UnexpectedTokenException : Exception
{
    public TokenKind Expected { get; }
    public Token Found { get; }
    
    public UnexpectedTokenException(TokenKind expected, Token found) 
        : base($"Expected {expected}, found {found.Kind} at {found.Line}:{found.Column}")
    {
        Expected = expected;
        Found = found;
    }
}