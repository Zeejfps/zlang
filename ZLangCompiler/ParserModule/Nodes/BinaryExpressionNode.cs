using LexerModule;

namespace ParserModule.Nodes;

public sealed class BinaryExpressionNode : AstNode
{
    public AstNode Left { get; }
    public Token Op { get; }
    public AstNode Right { get; }

    public BinaryExpressionNode(AstNode left, Token op, AstNode right)
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