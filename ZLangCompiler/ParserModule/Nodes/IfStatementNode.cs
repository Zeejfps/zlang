using ParserModule.Nodes.Expressions;

namespace ParserModule.Nodes;

public sealed class IfStatementNode : StatementNode
{
    public required ExpressionNode Condition { get; init; }
    public required StatementNode ThenBranch { get; init; }
    public StatementNode? ElseBranch { get; init; }
    
    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitIfStatementNode(this);
    }
}