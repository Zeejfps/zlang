using ParserModule.Nodes;

namespace ParserModule;

public interface IStatementNodeVisitor
{
    void VisitIfStatementNode(IfStatementNode node);
    void VisitBlockStatement(BlockStatementNode node);
    void VisitReturnStatementNode(ReturnStatementNode node);
    void VisitForStatement(ForStatemetNode node);
    void VisitVarDefinition(VarDefinitionStatementNode node);
    void VisitVarDeclaration(VarDeclarationStatementNode node);
    void VisitVarAssignment(VarAssignmentStatementNode node);
}