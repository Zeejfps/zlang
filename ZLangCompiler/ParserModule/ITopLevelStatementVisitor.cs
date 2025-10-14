using ParserModule.Nodes;

namespace ParserModule;

public interface ITopLevelStatementVisitor
{
    void VisitStructImportStatementNode(StructImportStatementNode node);
}