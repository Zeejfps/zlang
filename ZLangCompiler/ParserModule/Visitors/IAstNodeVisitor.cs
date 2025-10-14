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
    void VisitProgram(ProgramDefinitionNode node);
}