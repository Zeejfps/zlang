using LexerModule;

namespace ParserModule.Nodes;

public sealed class UnaryExpressionNode : ExpressionNode
{
    public required Token Operator { get; init; }
    public required AstNode Value { get; init; }
    public bool IsPrefix { get; init; }

    public override void Accept(IExpressionNodeVisitor visitor)
    {
        visitor.VisitUnary(this);
    }
}