using ParserModule.Visitors;

namespace ParserModule.Nodes;

public abstract class TopLevelStatementNode : AstNode
{
    public override void Accept(IAstNodeVisitor visitor)
    {
        Accept(visitor);
    }

    public abstract void Accept(ITopLevelStatementVisitor visitor);
}