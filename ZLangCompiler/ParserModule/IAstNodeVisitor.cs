using ParserModule.Nodes;

namespace ParserModule;

public interface IAstNodeVisitor : IStatementNodeVisitor
{
    void VisitLiteralIntegerNode(LiteralIntegerNode node);
    void VisitLiteralBoolNode(LiteralBoolNode node);
    void VisitBinaryExpression(BinaryExpressionNode node);
    void VisitUnaryExpression(UnaryExpressionNode node);
    void VisitIdentifierNode(IdentifierNode node);
    void VisitNamedTypeNode(NamedTypeNode node);
    void VisitFunctionDeclarationNode(FunctionDefinitionNode node);
    void VisitParameterNode(ParameterNode node);
    void VisitStructImportStatementNode(StructImportStatementNode node);
    void VisitQualifiedIdentifierNode(QualifiedIdentifierNode node);
    void VisitStructDefinitionNode(StructDefinitionNode node);
    void VisitModuleDefinitionNode(ModuleDefinitionNode node);
}