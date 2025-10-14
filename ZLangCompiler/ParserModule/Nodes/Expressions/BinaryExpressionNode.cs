using LexerModule;
using ParserModule.Visitors;

namespace ParserModule.Nodes.Expressions;

public sealed class BinaryExpressionNode : ExpressionNode
{
    public ExpressionNode Left { get; }
    public Token Op { get; }
    public ExpressionNode Right { get; }

    public BinaryExpressionNode(ExpressionNode left, Token op, ExpressionNode right)
    {
        Left = left;
        Op = op;
        Right = right;
    }

    public override void Accept(IExpressionNodeVisitor visitor)
    {
        visitor.VisitBinary(this);
    }
}