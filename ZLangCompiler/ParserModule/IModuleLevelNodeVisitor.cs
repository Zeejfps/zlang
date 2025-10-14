using ParserModule.Nodes;

namespace ParserModule;

public interface IModuleLevelNodeVisitor
{
    void VisitFunctionDefinition(FunctionDefinitionNode node);
}