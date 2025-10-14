using LexerModule;
using ParserModule.Visitors;

namespace ParserModule.Nodes.Expressions;

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