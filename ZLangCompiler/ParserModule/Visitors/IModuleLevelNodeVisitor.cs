using ParserModule.Nodes;

namespace ParserModule.Visitors;

public interface IModuleLevelNodeVisitor
{
    void VisitFunctionDefinition(FunctionDefinitionNode node);
    void VisitStructDefinition(StructDefinitionNode node);
    void VisitExternFunctionDeclaration(ExternFunctionDeclarationNode node);
}