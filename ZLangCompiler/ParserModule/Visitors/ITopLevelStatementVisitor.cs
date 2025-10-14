using ParserModule.Nodes;

namespace ParserModule.Visitors;

public interface ITopLevelStatementVisitor
{
    void VisitStructImportStatementNode(StructImportStatementNode node);
}