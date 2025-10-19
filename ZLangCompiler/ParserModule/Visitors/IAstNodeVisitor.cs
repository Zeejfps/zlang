namespace ParserModule.Visitors;

public interface IAstNodeVisitor :
    ITopLevelStatementVisitor,
    IModuleLevelNodeVisitor,
    IStatementNodeVisitor, 
    IExpressionNodeVisitor,
    ITypeNodeVisitor
{
}