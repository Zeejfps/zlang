namespace ParserModule.Nodes;

public sealed class IfStatementNode : StatementNode
{
    public required AstNode Condition { get; init; }
    public required AstNode ThenBranch { get; init; }
    public AstNode? ElseBranch { get; init; }
    
    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitIfStatementNode(this);
    }
}