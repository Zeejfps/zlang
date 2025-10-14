using ParserModule.Nodes;

namespace ParserModule;

public interface ITypeNodeVisitor
{
    void VisitNamedType(NamedTypeNode node);
}