namespace ParserModule.Nodes;

public sealed class VarAssignmentStatementNode : AstNode
{
    public required string VarName { get; init; }
    public AstNode? VarType { get; init; }
    public required AstNode VarValue { get; init; }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitVarAssignmentStatement(this);
    }
}