using ParserModule.Nodes;

namespace ParserModule.Visitors;

public interface IAstNodeVisitor :
    ITopLevelStatementVisitor,
    IModuleLevelNodeVisitor,
    IStatementNodeVisitor, 
    IExpressionNodeVisitor,
    ITypeNodeVisitor
{
    void VisitParameterNode(ParameterNode node);
    void VisitModuleDefinition(ModuleDefinitionNode node);
    void VisitProgram(ProgramDefinitionNode node);
}