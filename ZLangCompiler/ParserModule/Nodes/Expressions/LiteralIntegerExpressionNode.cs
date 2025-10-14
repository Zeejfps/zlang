using LexerModule;
using ParserModule.Visitors;

namespace ParserModule.Nodes.Expressions;

public sealed class LiteralIntegerExpressionNode : ExpressionNode
{
    public Token Token { get; }
    public int Value { get; }

    public LiteralIntegerExpressionNode(Token token)
    {
        Token = token;
        Value = int.Parse(token.Lexeme);
    }

    public override void Accept(IExpressionNodeVisitor visitor)
    {
        visitor.VisitLiteralInteger(this);
    }
}