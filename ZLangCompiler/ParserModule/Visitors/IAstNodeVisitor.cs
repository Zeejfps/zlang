using ParserModule.Nodes;

namespace ParserModule.Visitors;

public interface IAstNodeVisitor :
    ITopLevelStatementVisitor,
    IModuleLevelNodeVisitor,
    IStatementNodeVisitor, 
    IExpressionNodeVisitor,
    ITypeNodeVisitor
{
    void VisitProgram(ProgramDefinitionNode node);
}