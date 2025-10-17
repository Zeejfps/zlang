using ParserModule.Nodes;

namespace ParserModule.Visitors;

public interface IStatementNodeVisitor
{
    void VisitIfStatementNode(IfStatementNode node);
    void VisitBlockStatement(BlockStatementNode node);
    void VisitReturnStatementNode(ReturnStatementNode node);
    void VisitForStatement(ForStatemetNode node);
    void VisitVarDefinition(VarDefinitionStatementNode node);
    void VisitVarDeclaration(VarDeclarationStatementNode node);
    void VisitVarAssignment(VarAssignmentStatementNode node);
    void VisitWhileStatement(WhileStatementNode node);
    void VisitExpressionStatement(ExpressionStatement node);
}