using LexerModule;
using ParserModule.Nodes;

namespace ParserModule;

public sealed class TokenReader(IEnumerable<Token> tokens)
{
    public Token Peek()
    {
        throw new NotImplementedException();
    }

    public Token Read()
    {
        throw new NotImplementedException();
    }
}

public sealed class Parser
{
    public static Ast Parse(IEnumerable<Token> tokens)
    {
        throw new NotImplementedException();
    }

    public static PrimaryExpressionNode ParsePrimaryExpression(TokenReader tokenReader)
    {
        var token = tokenReader.Read();
        if (token.Kind == TokenKind.LiteralInteger)
        {
            return new PrimaryExpressionNode
            {
                
            };
        }

        throw new Exception("Invalid token: " + token.Lexeme + "");
    }
}