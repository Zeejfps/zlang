namespace ParserModule.Nodes;

public sealed class StructImportNode : AstNode
{
    public required string AliasName { get; init; }
    public required QualifiedIdentifierNode QualifiedIdentifier { get; init; }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitStructImportNode(this);
    }
}