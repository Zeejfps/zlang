using ParserModule.Nodes;

namespace ParserModule;

public interface IAstNodeVisitor
{
    void VisitIntegerNumberExpression(LiteralIntegerExpressionNode node);
    void VisitLiteralBoolExpression(LiteralBoolExpressionNode node);
    void VisitBinaryExpression(BinaryExpressionNode node);
    void VisitUnaryExpression(UnaryExpressionNode node);
    void VisitIdentifierExpression(IdentifierExpressionNode node);
    void VisitVarAssignmentStatement(VarAssignmentStatementNode node);
    void VisitNamedTypeNode(NamedTypeNode node);
    void VisitBlockStatement(BlockStatementNode node);
    void VisitFunctionDeclarationNode(FunctionDeclarationNode node);
    void VisitReturnStatementNode(ReturnStatementNode node);
    void VisitParameterNode(ParameterNode node);
    void VisitStructImportNode(StructImportNode node);
    void VisitQualifiedIdentifierNode(QualifiedIdentifierNode node);
    void VisitStructDefinitionNode(StructDefinitionNode node);
}