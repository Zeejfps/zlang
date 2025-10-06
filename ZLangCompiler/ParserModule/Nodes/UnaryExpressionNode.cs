using LexerModule;

namespace ParserModule.Nodes;

public sealed class UnaryExpressionNode : AstNode
{
    public Token Operator { get; }
    public AstNode Right { get; }

    public UnaryExpressionNode(Token @operator, AstNode right)
    {
        Operator = @operator;
        Right = right;
    }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitUnaryExpression(this);
    }
}