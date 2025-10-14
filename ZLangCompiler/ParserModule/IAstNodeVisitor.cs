using ParserModule.Nodes;

namespace ParserModule;

public interface IAstNodeVisitor : ITopLevelStatementVisitor, IStatementNodeVisitor, IExpressionNodeVisitor, ITypeNodeVisitor
{
    void VisitFunctionDeclarationNode(FunctionDefinitionNode node);
    void VisitParameterNode(ParameterNode node);
    void VisitStructDefinitionNode(StructDefinitionNode node);
    void VisitModuleDefinitionNode(ModuleDefinitionNode node);
}