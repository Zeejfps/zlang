using ParserModule.Nodes;

namespace ParserModule;

public interface IAstNodeVisitor : IStatementNodeVisitor, IExpressionNodeVisitor
{
    void VisitNamedTypeNode(NamedTypeNode node);
    void VisitFunctionDeclarationNode(FunctionDefinitionNode node);
    void VisitParameterNode(ParameterNode node);
    void VisitStructImportStatementNode(StructImportStatementNode node);
    void VisitQualifiedIdentifierNode(QualifiedIdentifierNode node);
    void VisitStructDefinitionNode(StructDefinitionNode node);
    void VisitModuleDefinitionNode(ModuleDefinitionNode node);
}