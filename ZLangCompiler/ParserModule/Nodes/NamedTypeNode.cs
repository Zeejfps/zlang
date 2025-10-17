using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class NamedTypeNode : TypeNode
{
    public required string Identifier { get; init; }
    
    public override void Accept(ITypeNodeVisitor visitor)
    {
        visitor.VisitNamedType(this);
    }
}