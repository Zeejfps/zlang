using ParserModule.Nodes.Expressions;

namespace ParserModule.Nodes;

public sealed class ForStatemetNode : StatementNode
{
    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitForStatement(this);
    }

    public required StatementNode Initializer { get; init; }
    public required ExpressionNode Condition { get; init; }
    public required ExpressionNode Incrementor { get; init; }
    public required StatementNode Body { get; init; }
}