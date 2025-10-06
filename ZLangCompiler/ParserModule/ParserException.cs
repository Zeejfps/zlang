using LexerModule;

namespace ParserModule;

public class ParserException : Exception
{
    public Token Token { get; }
    
    public ParserException(string message, Token token) : base(message)
    {
        Token = token;
    }
}