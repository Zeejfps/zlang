using LexerModule;

namespace ParserModule.Nodes;

public sealed class BinaryExpressionNode : AstNode
{
    public PrimaryExpressionNode Left { get; }
    public Token Op { get; }
    public PrimaryExpressionNode Right { get; }

    public BinaryExpressionNode(PrimaryExpressionNode left, Token op, PrimaryExpressionNode right)
    {
        Left = left;
        Op = op;
        Right = right;
    }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitBinaryExpression(this);
    }
}