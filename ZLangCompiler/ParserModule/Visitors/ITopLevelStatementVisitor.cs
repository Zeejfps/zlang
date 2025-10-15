using ParserModule.Nodes;

namespace ParserModule.Visitors;

public interface ITopLevelStatementVisitor
{
    void VisitStructImport(ImportStatementNode node);
    void VisitModuleDefinition(ModuleDefinitionNode node);
}