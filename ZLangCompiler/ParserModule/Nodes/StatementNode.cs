namespace ParserModule.Nodes;

public abstract class StatementNode : AstNode
{
    public override void Accept(IAstNodeVisitor visitor)
    {
        Accept(visitor);
    }

    public abstract void Accept(IStatementNodeVisitor visitor);
}