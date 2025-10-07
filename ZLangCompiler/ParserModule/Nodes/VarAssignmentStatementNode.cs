namespace ParserModule.Nodes;

public sealed class VarAssignmentStatementNode : AstNode
{
    public required string Name { get; init; }
    public AstNode? Type { get; init; }
    public required AstNode Value { get; init; }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitVarAssignmentStatement(this);
    }
}