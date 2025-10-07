namespace ParserModule.Nodes;

public sealed class NamedTypeNode : AstNode
{
    public required string Name { get; init; }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitNamedTypeNode(this);
    }
}