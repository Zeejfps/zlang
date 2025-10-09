namespace ParserModule.Nodes;

public sealed class IfStatementNode : AstNode
{
    public required AstNode Condition { get; init; }
    public required AstNode ThenBranch { get; init; }
    public AstNode? ElseBranch { get; init; }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitIfStatementNode(this);
    }
}