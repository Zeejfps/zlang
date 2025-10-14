using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class VarAssignmentStatementNode : StatementNode
{
    public required string Name { get; init; }
    public required ExpressionNode Value { get; init; }

    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitVarAssignment(this);
    }
}