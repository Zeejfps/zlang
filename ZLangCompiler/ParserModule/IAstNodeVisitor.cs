using ParserModule.Nodes;

namespace ParserModule;

public interface IAstNodeVisitor
{
    void VisitLiteralIntegerNode(LiteralIntegerNode node);
    void VisitLiteralBoolNode(LiteralBoolNode node);
    void VisitBinaryExpression(BinaryExpressionNode node);
    void VisitUnaryExpression(UnaryExpressionNode node);
    void VisitIdentifierNode(IdentifierNode node);
    void VisitVarAssignmentStatement(VarAssignmentStatementNode node);
    void VisitNamedTypeNode(NamedTypeNode node);
    void VisitBlockStatement(BlockStatementNode node);
    void VisitFunctionDeclarationNode(FunctionDefinitionNode node);
    void VisitReturnStatementNode(ReturnStatementNode node);
    void VisitParameterNode(ParameterNode node);
    void VisitStructImportNode(StructImportNode node);
    void VisitQualifiedIdentifierNode(QualifiedIdentifierNode node);
    void VisitStructDefinitionNode(StructDefinitionNode node);
    void VisitModuleDefinitionNode(ModuleDefinitionNode node);
}