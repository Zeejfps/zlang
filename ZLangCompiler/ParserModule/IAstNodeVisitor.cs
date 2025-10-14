using ParserModule.Nodes;

namespace ParserModule;

public interface IAstNodeVisitor :
    ITopLevelStatementVisitor,
    IModuleLevelNodeVisitor,
    IStatementNodeVisitor, 
    IExpressionNodeVisitor,
    ITypeNodeVisitor
{
    void VisitParameterNode(ParameterNode node);
    void VisitStructDefinitionNode(StructDefinitionNode node);
    void VisitModuleDefinitionNode(ModuleDefinitionNode node);
    void VisitProgram(ProgramDefinitionNode node);
}