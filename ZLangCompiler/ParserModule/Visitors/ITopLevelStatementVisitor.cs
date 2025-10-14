using ParserModule.Nodes;

namespace ParserModule.Visitors;

public interface ITopLevelStatementVisitor
{
    void VisitStructImport(StructImportStatementNode node);
    void VisitModuleDefinition(ModuleDefinitionNode node);
}