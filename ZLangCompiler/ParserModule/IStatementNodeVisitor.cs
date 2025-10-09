using ParserModule.Nodes;

namespace ParserModule;

public interface IStatementNodeVisitor
{
    void VisitIfStatementNode(IfStatementNode node);
    void VisitBlockStatement(BlockStatementNode node);
    void VisitReturnStatementNode(ReturnStatementNode node);
    void VisitVarAssignmentStatement(VarAssignmentStatementNode node);
}