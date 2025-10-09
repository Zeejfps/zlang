using ParserModule.Nodes;

namespace ParserModule;

public interface IStatementNodeVisitor
{
    void VisitIfStatementNode(IfStatementNode node);
}