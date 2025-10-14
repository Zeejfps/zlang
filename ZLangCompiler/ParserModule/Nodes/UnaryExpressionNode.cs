using LexerModule;

namespace ParserModule.Nodes;

public sealed class UnaryExpressionNode : ExpressionNode
{
    public Token Operator { get; }
    public AstNode Right { get; }

    public UnaryExpressionNode(Token @operator, AstNode right)
    {
        Operator = @operator;
        Right = right;
    }

    public override void Accept(IExpressionNodeVisitor visitor)
    {
        visitor.VisitUnary(this);
    }
}