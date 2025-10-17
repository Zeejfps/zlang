using ParserModule.Nodes;

namespace ParserModule.Visitors;

public interface ITypeNodeVisitor
{
    void VisitNamedType(NamedTypeNode node);
    void VisitPtrType(PtrTypeNode node);
}