using LexerModule;
using ParserModule.Nodes;

namespace ParserModule;

public sealed class Parser
{
    public static HashSet<TokenKind> Operators = [
        TokenKind.SymbolPlus
    ]; 
    
    public static Ast Parse(IEnumerable<Token> tokens)
    {
        throw new NotImplementedException();
    }

    public static AstNode ParsePrimaryExpression(TokenReader tokenReader)
    {
        var token = tokenReader.Read();
        if (token.Kind == TokenKind.LiteralInteger)
        {
            return new LiteralIntegerExpressionNode(token);
        }

        throw new Exception("Invalid token: " + token + "");
    }
    
    public static AstNode ParseExpression(TokenReader tokenReader)
    {
        var left = ParseComparison(tokenReader);
        var nextToken = tokenReader.Peek();
        while (nextToken.Kind == TokenKind.SymbolEqualsEquals ||
            nextToken.Kind == TokenKind.SymbolNotEquals)
        {
            var op = tokenReader.Read();
            var right = ParseComparison(tokenReader);
            left = new BinaryExpressionNode(left, op, right);
            nextToken = tokenReader.Peek();       
        }
        return left;
    }

    public static AstNode ParseComparison(TokenReader tokenReader)
    {
        var left = ParseTerm(tokenReader);
        var nextToken = tokenReader.Peek();
        while (nextToken.Kind == TokenKind.SymbolGreaterThan ||
            nextToken.Kind == TokenKind.SymbolLessThan ||
            nextToken.Kind == TokenKind.SymbolGreaterThanEquals ||
            nextToken.Kind == TokenKind.SymbolLessThanEquals)
        {
            var op = tokenReader.Read();
            var right = ParseTerm(tokenReader);
            left = new BinaryExpressionNode(left, op, right);       
            nextToken = tokenReader.Peek();      
        }
        return left;
    }

    public static AstNode ParseTerm(TokenReader tokenReader)
    {
        var left = ParseFactor(tokenReader);
        var nextToken = tokenReader.Peek();
        while (nextToken.Kind == TokenKind.SymbolPlus ||
               nextToken.Kind == TokenKind.SymbolMinus)
        {
            var op = tokenReader.Read();
            var right = ParseFactor(tokenReader);
            left = new BinaryExpressionNode(left, op, right);       
            nextToken = tokenReader.Peek();      
        }
        return left;
    }
    
    public static AstNode ParseFactor(TokenReader tokenReader)
    {
        var left = ParseUnary(tokenReader);
        var nextToken = tokenReader.Peek();
        while (nextToken.Kind == TokenKind.SymbolStar || 
               nextToken.Kind == TokenKind.SymbolForwardSlash)
        {
            var op = tokenReader.Read();
            var right = ParseUnary(tokenReader);
            left = new BinaryExpressionNode(left, op, right);      
            nextToken = tokenReader.Peek();      
        }
        return left;
    }
    
    public static AstNode ParseUnary(TokenReader tokenReader)
    {
        var nextToken = tokenReader.Peek();
        if (nextToken.Kind == TokenKind.SymbolExclamation ||
            nextToken.Kind == TokenKind.SymbolMinus)
        {
            var op = tokenReader.Read();
            var right = ParseUnary(tokenReader);
            return new UnaryExpressionNode(op, right);
        }
        return ParsePrimaryExpression(tokenReader);
    }
}