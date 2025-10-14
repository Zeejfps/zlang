namespace ParserModule.Nodes;

public sealed class VarDeclarationStatementNode : StatementNode
{
    public required string Name { get; init; }
    public AstNode? Type { get; init; }

    public override void Accept(IStatementNodeVisitor visitor)
    {
        visitor.VisitVarDeclaration(this);
    }
}