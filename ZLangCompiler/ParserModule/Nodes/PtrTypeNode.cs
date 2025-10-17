using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class PtrTypeNode : TypeNode
{
    public TypeNode? GenericType { get; init; }
    
    public override void Accept(ITypeNodeVisitor visitor)
    {
        visitor.VisitPtrType(this);
    }
}